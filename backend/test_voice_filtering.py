#!/usr/bin/env python3
"""
Test to verify voices are correctly filtered by language AND gender
"""
import asyncio
from app.database import AsyncSessionLocal
from app.models import TTSVoice
from sqlalchemy import select

async def test_voice_filtering():
    """Test TTS voice filtering by language and gender"""
    
    async with AsyncSessionLocal() as db:
        print("=" * 70)
        print("🎙️ Testing TTS Voice Filtering by Language & Gender")
        print("=" * 70)
        
        # Get all voices
        result = await db.execute(select(TTSVoice).order_by(TTSVoice.lang, TTSVoice.gender))
        voices = result.scalars().all()
        
        # Group by language and gender
        by_lang_gender = {}
        for voice in voices:
            key = f"{voice.lang}_{voice.gender}"
            if key not in by_lang_gender:
                by_lang_gender[key] = []
            by_lang_gender[key].append(voice)
        
        print("\n📋 Available voices by Language & Gender:\n")
        for lang_gender, voice_list in sorted(by_lang_gender.items()):
            lang, gender = lang_gender.split('_')
            print(f"   {lang} ({gender.upper()}):")
            for voice in voice_list:
                print(f"      • {voice.voice_name} (ID: {voice.id})")
        
        # Simulate admin panel filtering
        print("\n" + "=" * 70)
        print("🎯 Simulating Admin Panel Filtering:")
        print("=" * 70)
        
        test_cases = [
            ("DE", "male"),
            ("DE", "female"),
            ("DE", ""),  # No gender selected
            ("EN", "male"),
            ("EN", "female"),
            ("UA", "male"),
            ("UA", "female"),
        ]
        
        for lang, gender in test_cases:
            filtered = [
                v for v in voices 
                if v.lang == lang and (not gender or v.gender == gender)
            ]
            gender_label = f" & {gender.upper()}" if gender else " (all genders)"
            print(f"\n   Language: {lang}{gender_label}")
            if filtered:
                for voice in filtered:
                    print(f"      ✅ {voice.voice_name} ({voice.gender})")
            else:
                print(f"      ⚠️  No voices available")
        
        print("\n" + "=" * 70)
        print("✅ Voice filtering test completed!")
        print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        asyncio.run(test_voice_filtering())
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
