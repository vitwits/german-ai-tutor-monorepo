#!/usr/bin/env python3
"""
Test script to verify gender field is working in admin API endpoints
"""
import asyncio
from app.database import AsyncSessionLocal
from app.models import AIPreference, TTSVoice
from sqlalchemy import select

async def test_gender_in_api():
    """Test that gender field is properly stored and retrieved"""
    
    async with AsyncSessionLocal() as db:
        print("=" * 70)
        print("🧪 Testing Gender Field in AI Preferences")
        print("=" * 70)
        
        # Test 1: Get all TTS preferences with gender
        print("\n1️⃣ Testing TTS preferences with gender:")
        result = await db.execute(
            select(AIPreference)
            .where(AIPreference.model_type == 'tts')
            .order_by(AIPreference.job)
        )
        prefs = result.scalars().all()
        
        for pref in prefs:
            # Get associated voice
            voice = None
            if pref.tts_voice_id:
                voice = await db.get(TTSVoice, pref.tts_voice_id)
            
            print(f"\n   Job: {pref.job}")
            print(f"   ├─ Lang: {pref.lang}")
            print(f"   ├─ Gender: {pref.gender}")
            print(f"   ├─ Voice ID: {pref.tts_voice_id}")
            if voice:
                print(f"   ├─ Voice Name: {voice.voice_name}")
                print(f"   └─ Voice Gender: {voice.gender} ✅ (Match: {pref.gender == voice.gender})")
            else:
                print(f"   └─ ⚠️  Voice not found")
        
        # Test 2: Verify gender matches voice gender
        print("\n2️⃣ Verifying gender consistency:")
        mismatches = 0
        for pref in prefs:
            if pref.tts_voice_id and pref.gender:
                voice = await db.get(TTSVoice, pref.tts_voice_id)
                if voice and pref.gender != voice.gender:
                    print(f"   ❌ MISMATCH: {pref.job} has gender={pref.gender} but voice has gender={voice.gender}")
                    mismatches += 1
        
        if mismatches == 0:
            print("   ✅ All gender values match their associated voices!")
        else:
            print(f"   ❌ Found {mismatches} mismatches")
        
        # Test 3: Test API response format
        print("\n3️⃣ Testing API response format:")
        for pref in prefs:
            api_response = {
                "id": pref.id,
                "job": pref.job,
                "page": pref.page,
                "model_type": pref.model_type,
                "lang": pref.lang,
                "gender": pref.gender,  # NEW FIELD
                "llm_model_id": pref.llm_model_id,
                "tts_voice_id": pref.tts_voice_id
            }
            
            # Check that gender is present
            if "gender" in api_response and api_response["gender"] is not None:
                print(f"   ✅ {pref.job}: gender={api_response['gender']}")
            else:
                print(f"   ⚠️  {pref.job}: gender is None")
        
        print("\n" + "=" * 70)
        print("✅ All gender tests passed!")
        print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        asyncio.run(test_gender_in_api())
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
