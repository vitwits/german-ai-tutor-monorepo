# Custom Admin Interface for FastAPI Backend

Replaces SQLAdmin with a fully featured admin panel based on the original Flask-Admin implementation.

## Features

### Dashboard (`/admin`)
- Overall statistics (total sentences, users, reported issues)
- Quick navigation to all admin sections

### Sentence Management (`/admin/sentence/list`)
- **List View** with pagination (20/50/100 items per page)
- **Audio Playback** - click play button to hear sentences in sequence (UK → EN → DE)
- **Filtering** by level and topic
- **Search** across German, Ukrainian, and Topic fields  
- **Edit** individual sentences
- **Delete** sentences (with audio file cleanup)
- **Column Selection** for future bulk operations

Features from old system:
- Playing audio for multiple sentences in sequence
- Pause/resume functionality
- Highlighted playing row
- Sortable columns
- Responsive table design

### Reported Sentences (`/admin/reported`)
- View all user-reported sentences
- Mark as un-reported
- Edit or delete problematic content

### User Management (`/admin/users`)
- View all users with statistics
- Email, level, credits, admin status
- Expandable for user editing

### Sentence Generation (`/admin/generate`)
- Start new generation batches
- Select level (A1-C2) and count
- View recent batch status
- Track processing progress

## Technical Details

- **Framework**: FastAPI with async/await
- **Database**: SQLAlchemy ORM (AsyncSession) 
- **Authentication**: JWT tokens with admin role check
- **Styling**: Bootstrap 4 for responsive UI
- **JavaScript**: Vanilla JS for audio playback and interactions

## Routes

```
GET  /admin                          - Admin dashboard
GET  /admin/sentence/list            - List sentences (with pagination, search, filters)
GET  /admin/reported                 - List reported sentences
GET  /admin/users                    - List users
GET  /admin/sentence/{id}/edit       - Edit sentence form
POST /admin/sentence/{id}/update     - Update sentence
POST /admin/sentence/{id}/delete     - Delete sentence
POST /admin/sentence/{id}/unreport   - Un-report sentence
GET  /admin/generate                 - Generation interface
POST /admin/generate/start           - Start generation batch
```

## Future Enhancements

- User editing interface
- Batch edit operations for sentences
- Advanced filtering with operators (contains, equals, etc.)
- Caching statistics dashboard
- TTS logs viewer
- Vocabulary management
