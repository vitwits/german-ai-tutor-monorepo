"""
Міграція: Додати промпт texts_create_own_text для валідації користувацьких текстів.
"""

import sqlite3
import json

def migrate():
    db_path = "./data/app.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if prompt already exists
        cursor.execute("SELECT id FROM model_prompts WHERE name='texts_create_own_text'")
        exists = cursor.fetchone() is not None
        
        if exists:
            print("✅ Prompt 'texts_create_own_text' already exists")
            conn.close()
            return
        
        # Prompt for validating user-provided German text
        validation_prompt = """You are a strict validator for German language texts submitted by language learners.

Analyze the following German text provided by a user learning German at level {level}.

TEXT TO VALIDATE:
"{text}"

Validate the text based on these criteria:

1. **text_is_completely_in_german** (boolean): Is the entire text written in German? (Allow minimal English for technical terms if necessary)
2. **is_ethical** (boolean): Does the text contain appropriate, respectful content without offensive language?
3. **no_sexual_content** (boolean): Does the text avoid explicit sexual or adult content?
4. **no_prohibited_topics** (boolean): Does the text avoid violent, discriminatory, or harmful topics?
5. **is_safe_for_work** (boolean): Is the text suitable for educational/professional contexts?

Return ONLY a valid JSON object with these exact fields (no markdown, no explanation):
{{
  "text_is_completely_in_german": true/false,
  "is_ethical": true/false,
  "no_sexual_content": true/false,
  "no_prohibited_topics": true/false,
  "is_safe_for_work": true/false,
  "overall_validity": true/false
}}

Set "overall_validity" to true ONLY if ALL other conditions are true."""
        
        # Insert the prompt
        cursor.execute(
            """INSERT INTO model_prompts (name, page, prompt) 
               VALUES (?, ?, ?)""",
            ("texts_create_own_text", "texts", validation_prompt)
        )
        conn.commit()
        print("✅ Prompt 'texts_create_own_text' added successfully")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    migrate()
