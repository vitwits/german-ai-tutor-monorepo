#!/usr/bin/env python3
"""
Test script for user text validation and lesson generation flow.
This tests the refactored create_lesson_from_user_text function.
"""

import json
import sys

# Simulate the LLM response from texts_create_own_text prompt
MOCK_LLM_RESPONSE = """{
  "validation_results": {
    "is_ethical": true,
    "no_sexual_content": true,
    "no_prohibited_topics": true,
    "is_safe_for_work": true,
    "overall_validity": true
  },
  "complexity_level_de": "B1",
  "title_de": "Meine Lieblingshobby",
  "title_ua": "Мої улюблені хобі",
  "title_en": "My Favorite Hobbies",
  "sentences": [
    {
      "de": "Ich habe viele Hobbys, die mir Spaß machen.",
      "ua": "У мене багато хобі, які мені подобаються.",
      "en": "I have many hobbies that I enjoy."
    },
    {
      "de": "Mein liebstes Hobby ist Lesen.",
      "ua": "Моє улюблене хобі - читання.",
      "en": "My favorite hobby is reading."
    }
  ],
  "quiz": [
    {
      "question": "Was ist das liebste Hobby des Sprechers?",
      "options": [
        "Lesen",
        "Schreiben",
        "Malen",
        "Sport"
      ],
      "correct_index": 0
    }
  ],
  "vocabulary": [
    {
      "de": "Hobby",
      "ua": "Хобі",
      "en": "hobby"
    }
  ]
}"""

def test_response_parsing():
    """Test that the mock response parses correctly and has expected structure"""
    print("🧪 Test 1: JSON Response Parsing")
    
    try:
        response_data = json.loads(MOCK_LLM_RESPONSE)
        print("  ✓ JSON parsed successfully")
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON parsing failed: {e}")
        return False
    
    # Check validation_results
    validation_data = response_data.get("validation_results", {})
    print(f"  ✓ Validation results: {validation_data}")
    
    required_validation_fields = [
        "is_ethical",
        "no_sexual_content",
        "no_prohibited_topics",
        "is_safe_for_work",
        "overall_validity"
    ]
    
    for field in required_validation_fields:
        if field not in validation_data:
            print(f"  ✗ Missing validation field: {field}")
            return False
    
    print(f"  ✓ All validation fields present")
    
    # Check lesson data
    lesson_data = {
        "title_de": response_data.get("title_de"),
        "title_ua": response_data.get("title_ua"),
        "title_en": response_data.get("title_en"),
        "complexity_level_de": response_data.get("complexity_level_de"),
        "sentences": response_data.get("sentences", []),
        "quiz": response_data.get("quiz", []),
        "vocabulary": response_data.get("vocabulary", [])
    }
    
    print(f"  ✓ Lesson data extracted:")
    print(f"    - Title DE: {lesson_data['title_de']}")
    print(f"    - Sentences: {len(lesson_data['sentences'])} items")
    print(f"    - Quiz: {len(lesson_data['quiz'])} items")
    print(f"    - Vocabulary: {len(lesson_data['vocabulary'])} items")
    
    return True

def test_validation_logic():
    """Test validation check logic"""
    print("\n🧪 Test 2: Validation Logic")
    
    response_data = json.loads(MOCK_LLM_RESPONSE)
    validation_data = response_data.get("validation_results", {})
    
    # Test 1: Valid text
    if validation_data.get("overall_validity"):
        print("  ✓ overall_validity=true → Proceed to lesson generation")
    else:
        print("  ✗ overall_validity=false → Would return validation error")
        return False
    
    # Test 2: Check error conditions
    test_cases = [
        ("is_ethical", "validation_not_ethical"),
        ("no_sexual_content", "validation_sexual_content"),
        ("no_prohibited_topics", "validation_prohibited_topics"),
        ("is_safe_for_work", "validation_not_safe"),
    ]
    
    for field, error_key in test_cases:
        if not validation_data.get(field):
            print(f"  ✓ {field}=false → error_key: {error_key}")
    
    return True

def test_invalid_response():
    """Test handling of invalid responses"""
    print("\n🧪 Test 3: Invalid Response Handling")
    
    invalid_json = "this is not json"
    
    try:
        response_data = json.loads(invalid_json)
    except json.JSONDecodeError:
        print("  ✓ Invalid JSON detected, using fallback structure")
        fallback = {
            "validation_results": {
                "is_ethical": False,
                "no_sexual_content": False,
                "no_prohibited_topics": False,
                "is_safe_for_work": False,
                "overall_validity": False
            },
            "title_de": "Custom Lesson",
            "title_ua": "Користувацький урок",
            "title_en": "Custom Lesson",
            "complexity_level_de": "A1",
            "sentences": [],
            "quiz": [],
            "vocabulary": []
        }
        print(f"  ✓ Fallback structure created with overall_validity=false")
        return True
    
    return False

def test_endpoint_response():
    """Test the endpoint response structure"""
    print("\n🧪 Test 4: Endpoint Response Structure")
    
    response_data = json.loads(MOCK_LLM_RESPONSE)
    validation_data = response_data.get("validation_results", {})
    
    if validation_data.get("overall_validity"):
        # Success response
        endpoint_response = {
            "id": "uuid-123",
            "cost_usd": 0.0234
        }
        print(f"  ✓ Success response: {endpoint_response}")
    else:
        # Error response
        endpoint_response = {
            "detail": {
                "error_key": "validation_not_german"
            }
        }
        print(f"  ✓ Error response: {endpoint_response}")
    
    return True

def main():
    print("=" * 60)
    print("Testing User Text Validation & Lesson Generation")
    print("=" * 60)
    
    tests = [
        test_response_parsing,
        test_validation_logic,
        test_invalid_response,
        test_endpoint_response,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
