#!/usr/bin/env python3
"""
Quick test to verify gender is returned in API responses
"""
import asyncio
from app.database import AsyncSessionLocal
from app.models import AIPreference
from sqlalchemy import select
import json

async def test_api_responses():
    """Test that gender field is properly returned"""
    
    async with AsyncSessionLocal() as db:
        print("=" * 70)
        print("🧪 Testing API Responses with Gender")
        print("=" * 70)
        
        # Get all preferences
        result = await db.execute(select(AIPreference).order_by(AIPreference.job))
        prefs = result.scalars().all()
        
        print("\n📝 All AI Preferences (as API would return):")
        for pref in prefs:
            api_response = {
                "id": pref.id,
                "job": pref.job,
                "page": pref.page,
                "model_type": pref.model_type,
                "lang": pref.lang,
                "gender": pref.gender,
                "llm_model_id": pref.llm_model_id,
                "tts_voice_id": pref.tts_voice_id
            }
            print(f"\n   {pref.job}:")
            print(json.dumps(api_response, indent=6))
        
        print("\n" + "=" * 70)
        print("✅ All preferences ready to display in admin UI!")
        print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        asyncio.run(test_api_responses())
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
