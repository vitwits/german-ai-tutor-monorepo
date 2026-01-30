#!/usr/bin/env python3
"""
Test script to verify AI preferences are being used correctly
"""
import asyncio
from app.database import AsyncSessionLocal
from app import services
from sqlalchemy import text

async def test_llm_models():
    """Test if generate_german_text and explain_grammar_text use correct models"""
    
    async with AsyncSessionLocal() as db:
        print("=" * 60)
        print("🧪 Testing LLM Model Selection")
        print("=" * 60)
        
        # Test 1: get_llm_model_for_job for text generation
        print("\n1️⃣ Testing get_llm_model_for_job('generate_texts', db):")
        model_for_texts = await services.get_llm_model_for_job('generate_texts', db)
        print(f"   ✅ Result: {model_for_texts}")
        
        # Test 2: get_llm_model_for_job for grammar
        print("\n2️⃣ Testing get_llm_model_for_job('generate_text_grammar', db):")
        model_for_grammar = await services.get_llm_model_for_job('generate_text_grammar', db)
        print(f"   ✅ Result: {model_for_grammar}")
        
        # Test 3: Check database directly to confirm
        print("\n3️⃣ Database verification:")
        result = await db.execute(text("""
            SELECT ap.job, m.model_id, m.human_name
            FROM ai_preferences ap
            JOIN llm_models m ON ap.llm_model_id = m.id
            WHERE ap.model_type = 'llm' AND m.is_active = 1
        """))
        for row in result:
            print(f"   - {row[0]}: {row[1]} ({row[2]})")
        
        print("\n" + "=" * 60)
        print("✅ Tests completed!")
        print("=" * 60)
        
        # Instructions for manual testing
        print("\n📋 Manual Testing Instructions:")
        print("-" * 60)
        print("1. Go to Admin Panel → AI Preferences")
        print("2. Change 'generate_texts' model to 'Gemini Flash 2.0' (llm_model_id=1)")
        print("3. Save the change")
        print("4. Run this test again - you should see:")
        print("   - generate_texts returns: gemini-2.0-flash")
        print("   - generate_text_grammar returns: gemini-2.5-flash-lite (unchanged)")
        print("\n5. Then change 'generate_text_grammar' to 'Gemini Flash 2.0'")
        print("6. Run this test again - both should return gemini-2.0-flash")
        print("-" * 60)

async def test_tts_voice():
    """Test if get_tts_audio uses correct voice"""
    
    async with AsyncSessionLocal() as db:
        print("\n\n" + "=" * 60)
        print("🧪 Testing TTS Voice Selection")
        print("=" * 60)
        
        print("\n1️⃣ Testing get_tts_voice_for_job('generate_text_audio', 'DE', db):")
        voice_for_audio = await services.get_tts_voice_for_job('generate_text_audio', 'DE', db)
        print(f"   ✅ Result: {voice_for_audio}")
        
        print("\n2️⃣ Database verification:")
        result = await db.execute(text("""
            SELECT ap.job, v.voice_name, v.id
            FROM ai_preferences ap
            JOIN tts_voices v ON ap.tts_voice_id = v.id
            WHERE ap.job = 'generate_text_audio' AND v.is_active = 1
        """))
        for row in result:
            print(f"   - {row[0]}: {row[1]} (ID={row[2]})")
        
        print("\n" + "=" * 60)
        print("✅ Tests completed!")
        print("=" * 60)
        
        print("\n📋 Manual Testing Instructions:")
        print("-" * 60)
        print("1. Go to Admin Panel → AI Preferences → Words tab")
        print("2. Change TTS voice to 'de-DE-Neural2-A'")
        print("3. Save the change")
        print("4. Run this test again - you should see:")
        print("   - Result: de-DE-Neural2-A")
        print("-" * 60)

if __name__ == "__main__":
    print("\n🚀 Starting AI Preferences Test\n")
    asyncio.run(test_llm_models())
    asyncio.run(test_tts_voice())
