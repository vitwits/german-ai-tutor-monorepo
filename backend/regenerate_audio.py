import asyncio
import sys
sys.path.insert(0, '/Users/omicron/Desktop/german_ai_tutor/monorepo/backend')

from app.database import get_async_session
from app.utils_tts import get_cached_or_generate_tts
from sqlalchemy import select
from app.models import Vocabulary, User

async def regenerate():
    async for db in get_async_session():
        # Знаходимо юзера
        user = await db.execute(select(User).limit(1))
        user = user.scalar_one()
        user_id = user.id
        
        # Знаходимо два слова
        words = await db.execute(select(Vocabulary).where(
            Vocabulary.display.in_(["der Wunsch (die Wünsche)", "hoffen"])
        ))
        words = words.scalars().all()
        
        for word in words:
            print(f"Regenerating {word.display}...")
            url = await get_cached_or_generate_tts(word.display, 'de', user_id, db, log_stats=True)
            print(f"  Result: {url}")
        
        break

asyncio.run(regenerate())
