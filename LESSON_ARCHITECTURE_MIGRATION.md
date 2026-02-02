# Global Lesson Architecture Migration

## Overview
Restructured the lesson storage system from **user-specific texts** to **global lessons with per-user references**. This enables:
- ✅ One lesson generated, accessible to multiple users
- ✅ Audio generated once globally (massive cost savings)
- ✅ Foundation for shared lesson library
- ✅ Scalable architecture for future features (ratings, reviews, etc.)

## Database Schema Changes

### New Tables

#### 1. **`lessons`** (Global Lesson Storage)
```sql
CREATE TABLE lessons (
    id TEXT PRIMARY KEY,
    created_by_user_id TEXT NOT NULL,      -- User who originally created lesson
    title TEXT,                             -- JSON: {"de": "...", "ua": "...", "en": "..."}
    level TEXT,                             -- A1-C2
    content_json TEXT,                      -- Sentences array
    quiz_json TEXT,                         -- Quiz questions
    audio_status TEXT DEFAULT 'pending',    -- pending/generating/completed/partial_failed
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);
```
**Purpose**: Single global lesson shared by all users who add it

#### 2. **`user_lessons`** (User-to-Lesson Junction)
```sql
CREATE TABLE user_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    lesson_id TEXT NOT NULL,
    is_favorite INTEGER DEFAULT 0,         -- 0 = normal, 1 = favorited
    added_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (lesson_id) REFERENCES lessons(id),
    UNIQUE(user_id, lesson_id)
);
```
**Purpose**: Track which lessons users have accessed/favorited

#### 3. **`lesson_audio`** (Audio Metadata per Sentence)
```sql
CREATE TABLE lesson_audio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    sentence_index INTEGER NOT NULL,
    lang TEXT DEFAULT 'de',                -- de/en/uk
    audio_path TEXT,                       -- cache/de/ab/abc123.ogg
    status TEXT DEFAULT 'pending',         -- pending/generated/failed
    generated_at DATETIME,
    FOREIGN KEY (lesson_id) REFERENCES lessons(id),
    UNIQUE(lesson_id, sentence_index, lang)
);
```
**Purpose**: Track audio generation status per sentence per language

### Modified Tables

#### **`quiz_results`**
- **Added**: `lesson_id` column (nullable, for global lessons)
- **Modified**: `text_id` now nullable (for backward compatibility)
- **Logic**: Quiz result can reference either `text_id` (old user texts) or `lesson_id` (new global lessons)

## Endpoint Changes

### POST `/api/generate`
**Before**: Saved to `texts` table (user-specific)
**After**: Saves to `lessons` table (global) + creates `user_lessons` entry

```python
# Creates global lesson
new_lesson = Lesson(
    id=tid,
    created_by_user_id=current_user.id,  # Who created it
    title=title_json,
    level=req.level,
    content_json=...,
    quiz_json=...,
    audio_status='pending'
)

# Creates user-lesson relationship
user_lesson = UserLesson(
    user_id=current_user.id,
    lesson_id=tid,
    is_favorite=0
)
```

### GET `/api/library`
**Before**: `SELECT * FROM texts WHERE user_id = ?`
**After**: `SELECT l.* FROM lessons l JOIN user_lessons ul ON l.id = ul.lesson_id WHERE ul.user_id = ?`

Benefits:
- User sees only lessons they've added
- Can filter by favorite status
- Multiple users query same lesson (scalable)

### GET `/api/texts/{text_id}`
**Before**: Query single table `texts`
**After**: 
1. Try to get from `lessons` table
2. Verify user has access via `user_lessons`
3. Fallback to old `texts` table (backward compatibility)

### POST `/api/toggle_text_fav`
**Before**: Toggle `Text.is_favorite`
**After**: Toggle `UserLesson.is_favorite`

### POST `/api/delete_text`
**Before**: Delete row from `texts` table
**After**:
1. Try to delete from `user_lessons` (removes from user's library)
2. **Does NOT delete global lesson** (other users may have access)
3. Fallback: Delete from `texts` if it's an old user-specific text

### POST `/api/save_quiz_result`
**Before**: Always save to `text_id`
**After**:
1. Determine if ID is lesson or text
2. Save to appropriate field (`lesson_id` or `text_id`)

## Cost Savings

### Before (User-Specific Texts)
```
5 users × 10 sentences each = 5 × 10 = 50 audio generations
50 sentences × 1000 chars = 50,000 chars
Cost: 50,000 / 1,000,000 × $16 = $0.80 per round
```

### After (Global Lessons)
```
1 global lesson × 10 sentences = 10 audio generations
10 sentences × 1000 chars = 10,000 chars
Cost: 10,000 / 1,000,000 × $16 = $0.16 per round
Cost savings: 80% (5x reduction)
```

## Migration Details

### Files Modified
1. **`models.py`**: Added three new ORM models
2. **`routers/library.py`**: Updated all endpoints to use new schema
3. **Migration file**: `migrate_add_lesson_tables.py` (creates tables)

### Backward Compatibility
- **Old `Text` table**: Still supported (not deleted)
- **Old endpoints**: Still work with existing user texts
- **Gradual migration**: New lessons go to `Lesson`, old texts stay in `Text`
- **Quiz results**: Can reference either table

### Data Consistency
- `user_lessons` has `UNIQUE(user_id, lesson_id)` constraint
- `lesson_audio` has `UNIQUE(lesson_id, sentence_index, lang)` constraint
- Prevents duplicate entries

## Future Enhancements

### Shared Library
Once established, could implement:
```sql
-- Global library feature
ALTER TABLE lessons ADD COLUMN is_public BOOLEAN DEFAULT 0;
ALTER TABLE lessons ADD COLUMN view_count INTEGER DEFAULT 0;
ALTER TABLE lessons ADD COLUMN rating FLOAT DEFAULT NULL;
```

### Community Lessons
```sql
CREATE TABLE lesson_ratings (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    lesson_id TEXT,
    rating INTEGER (1-5),
    comment TEXT,
    UNIQUE(user_id, lesson_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (lesson_id) REFERENCES lessons(id)
);
```

### Audio Caching Strategy
- `lesson_audio.audio_path` stores relative path: `cache/de/ab/hash.ogg`
- Generated once per language per sentence
- Multiple users serve from cache (no regeneration)
- Cost calculation only on first generation

## Testing Checklist

- [ ] Create lesson via `/api/generate`
- [ ] Verify `lesson` created in database
- [ ] Verify `user_lesson` entry created
- [ ] Query `/api/library` returns the new lesson
- [ ] Fetch lesson via `/api/texts/{id}`
- [ ] Toggle favorite via `/api/toggle_text_fav`
- [ ] Save quiz result via `/api/save_quiz_result`
- [ ] Delete lesson via `/api/delete_text` (removes from user library only)
- [ ] Verify second user can add same lesson (if shared)
- [ ] Check cost tracking in background audio generation

## Migration Execution

```bash
# 1. Create tables
python monorepo/backend/app/migrations/migrate_add_lesson_tables.py

# 2. Test new endpoints
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"topic":"Sports","level":"A1","size":"S","style":"natural"}'

# 3. Verify lesson in database
sqlite3 data/database.db "SELECT * FROM lessons LIMIT 1;"
sqlite3 data/database.db "SELECT * FROM user_lessons WHERE lesson_id = '<lesson_id>';"

# 4. Optional: Migrate old texts to lessons
# (Can implement if needed - keep old texts for now)
```

## Status

✅ **Completed**:
- Database models created (`Lesson`, `UserLesson`, `LessonAudio`)
- Migration file created and executed
- All endpoints updated to use new schema
- Backward compatibility maintained
- Syntax validated

⏳ **Next Steps**:
- Update audio generation to save to `lesson_audio` table
- Implement shared library UI (if desired)
- Monitor cost savings

