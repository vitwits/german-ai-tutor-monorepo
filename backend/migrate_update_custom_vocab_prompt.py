#!/usr/bin/env python3
"""
Migration script to update 'add_custom_vocab' prompt in the database with improved rules.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Load environment
MONOREPO_ROOT = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(MONOREPO_ROOT, ".env"))

# Add app to path
sys.path.insert(0, os.path.join(MONOREPO_ROOT, "app"))

from app.models import ModelPrompt
from app.database import DATABASE_URL

# Define the updated prompt
UPDATED_PROMPT = """Translate the German word or phrase: "{text}". Context: "{ctx}".  
The input "{text}" has {word_count} words.  

STRICT GRAMMAR RULES (NO EXCEPTIONS):  
0. PRIORITY ORDER: First determine if input is phrase (2+ words) or single word (exactly 1 word). Then apply rules.  

1. COLLOQUIALISMS, SLANG, CONTRACTIONS (HIGHEST PRIORITY):  
   - If input is spoken contraction ("hast'e", "hab's", "bist'e", "gib's", "mach's") or slang ("nix", "ne"):  
   - YOU MUST PRESERVE colloquial spelling in 'display' field.  
   - DO NOT expand to standard German ("hast'e" ≠ "hast du").  
   - Format: "colloquial_form (standard_form)".  
   - Examples: "hast'e" → "hast'e (hast du)", "hab's" → "hab's (habe es)", "nix" → "nix (nichts)".  

2. PHRASES (2+ words):  
   - Convert to Nominative Singular: "die kontinuierliche Innovation".  
   - NEVER use brackets "()" or dashes "(-)" for phrases.  
   - Result MUST be clean text only.  
   - NO "die kontinuierliche Innovation (die kontinuierlichen Innovationen)" — ONLY "die kontinuierliche Innovation".  

3. SINGLE WORDS — Nouns:  
   - MUST include correct definite article (der/die/das) in nominative singular + plural in brackets.  
   - Example: "das Haus (die Häuser)".  
   - Pluraletantum: "Leute (Pl.)".  
   - Singularetantum: "das Obst (-)".  

4. SINGLE WORDS — Verbs, Adjectives, Pronouns, Adverbs etc.:  
   - Provide ONLY base/infinitive form.  
   - FORBIDDEN: declensions, comparatives, endings in brackets.  
   - Examples: "mein" → "mein", "langsam" → "langsam", "machen" → "machen".  

5. TRANSLATIONS: 1–2 main meanings. Clean text only.  

6. CEFR LEVEL (CRITICAL):  
   - Output EXACTLY ONE of: "A1", "A2", "B1", "B2", "C1", "C2".  
   - NEVER ranges ("A1-C2").  
   - Examples: "Haus" → "A1", "Argument" → "B1".  

7. VALIDATION:
   - Check if input is valid German (word or phrase)
   - If NOT German or invalid, return: {{"valid": false, "error": "Invalid German word or phrase"}}

IF VALID GERMAN:
Return ONLY minified JSON on a single line:
{{"display":"Correct German form (No brackets for 2+ words)","ua":"Meanings in Ukrainian","en":"Meanings in English","level":"A1-C2","context":"Example sentence in German only"}}"""

async def migrate():
    """Update the custom vocab prompt in database"""
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Find the prompt
        result = await session.execute(
            select(ModelPrompt).where(ModelPrompt.name == "add_custom_vocab")
        )
        prompt = result.scalar_one_or_none()
        
        if not prompt:
            print("❌ Prompt 'add_custom_vocab' not found in database")
            print("   Run migrate_add_custom_vocab_prompt.py first")
            return
        
        # Update the prompt
        await session.execute(
            update(ModelPrompt)
            .where(ModelPrompt.name == "add_custom_vocab")
            .values(prompt=UPDATED_PROMPT)
        )
        await session.commit()
        
        print("🚀 Migrating 'add_custom_vocab' prompt to updated version...")
        print("\n✅ Successfully updated 'add_custom_vocab' prompt in database")
        print(f"   Name: add_custom_vocab")
        print(f"   Page: words")
        print(f"   ID: {prompt.id}")
        print(f"   Length: {len(UPDATED_PROMPT)} characters")
        
        print("\n✨ Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
