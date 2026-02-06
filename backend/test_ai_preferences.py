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
        print("🧪 Testing LLM Model Selection (Text Generation)")
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
            ORDER BY ap.job
        """))
        for row in result:
            print(f"   - {row[0]}: {row[1]} ({row[2]})")

async def test_vocabulary_llm_models():
    """Test if translate_vocabulary uses correct model"""
    
    async with AsyncSessionLocal() as db:
        print("\n" + "=" * 60)
        print("🧪 Testing LLM Model Selection (Vocabulary Translation)")
        print("=" * 60)
        
        print("\n1️⃣ Testing get_llm_model_for_job('translate_vocabulary', db):")
        model_for_vocab = await services.get_llm_model_for_job('translate_vocabulary', db)
        print(f"   ✅ Result: {model_for_vocab}")
        
        # Check database
        print("\n2️⃣ Database verification:")
        result = await db.execute(text("""
            SELECT ap.job, m.model_id, m.human_name
            FROM ai_preferences ap
            JOIN llm_models m ON ap.llm_model_id = m.id
            WHERE ap.job = 'translate_vocabulary' AND m.is_active = 1
        """))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"   - {row[0]}: {row[1]} ({row[2]})")
        else:
            print("   ⚠️  No translate_vocabulary job found in ai_preferences")

async def test_tts_voice():
    """Test if get_tts_audio uses correct voice"""
    
    async with AsyncSessionLocal() as db:
        print("\n\n" + "=" * 60)
        print("🧪 Testing TTS Voice Selection (Text Audio)")
        print("=" * 60)
        
        print("\n1️⃣ Testing get_tts_voice_for_job('generate_text_audio', 'DE', db):")
        voice_for_audio = await services.get_tts_voice_for_job('generate_text_audio', 'DE', db)
        print(f"   ✅ Result: {voice_for_audio}")
        
        print("\n2️⃣ Database verification:")
        result = await db.execute(text("""
            SELECT ap.job, v.voice_name, v.lang, v.id
            FROM ai_preferences ap
            JOIN tts_voices v ON ap.tts_voice_id = v.id
            WHERE ap.job = 'generate_text_audio' AND v.is_active = 1
        """))
        for row in result:
            print(f"   - {row[0]}: {row[1]} (lang={row[2]}, ID={row[3]})")

async def test_vocabulary_tts_voices():
    """Test if vocabulary TTS uses correct voices"""
    
    async with AsyncSessionLocal() as db:
        print("\n" + "=" * 60)
        print("🧪 Testing TTS Voice Selection (Vocabulary Audio)")
        print("=" * 60)
        
        vocab_jobs = ['vocabulary_tts_de', 'vocabulary_tts_ua', 'vocabulary_tts_en']
        lang_map = {'vocabulary_tts_de': 'DE', 'vocabulary_tts_ua': 'UA', 'vocabulary_tts_en': 'EN'}
        
        for job in vocab_jobs:
            lang = lang_map[job]
            print(f"\n1️⃣ Testing get_tts_voice_for_job('{job}', '{lang}', db):")
            voice = await services.get_tts_voice_for_job(job, lang, db)
            print(f"   ✅ Result: {voice}")
        
        # Check database
        print("\n2️⃣ Database verification:")
        result = await db.execute(text("""
            SELECT ap.job, v.voice_name, v.lang
            FROM ai_preferences ap
            JOIN tts_voices v ON ap.tts_voice_id = v.id
            WHERE ap.job IN ('vocabulary_tts_de', 'vocabulary_tts_ua', 'vocabulary_tts_en')
            AND v.is_active = 1
            ORDER BY ap.job
        """))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"   - {row[0]}: {row[1]} (lang={row[2]})")
        else:
            print("   ⚠️  No vocabulary_tts jobs found in ai_preferences")

async def main():
    print("\n" + "=" * 80)
    print("🚀 AI PREFERENCES COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    try:
        await test_llm_models()
        await test_vocabulary_llm_models()
        await test_tts_voice()
        await test_vocabulary_tts_voices()
        
        print("\n\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
        print("\n📋 MANUAL TESTING INSTRUCTIONS:")
        print("-" * 80)
        print("1. Go to Admin Panel → AI Preferences")
        print("\n2. For Text Generation:")
        print("   - Change 'generate_texts' model to a different one")
        print("   - Verify library.py calls use the new model")
        
        print("\n3. For Vocabulary Translation:")
        print("   - Set 'translate_vocabulary' in ai_preferences")
        print("   - Change model and verify vocabulary.py uses it")
        
        print("\n4. For TTS Audio:")
        print("   - Change 'generate_text_audio' voice")
        print("   - Change 'vocabulary_tts_de/ua/en' voices")
        print("   - Verify audio uses new voices")
        
        print("\n5. Run tests again after changes:")
        print(f"   cd /Users/omicron/Desktop/german_ai_tutor/monorepo/backend")
        print(f"   python test_ai_preferences.py")
        print("-" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
