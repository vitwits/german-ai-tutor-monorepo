from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()
voices = client.list_voices(language_code="uk-UA")

for voice in voices.voices:
    print(f"Name: {voice.name}, Gender: {voice.ssml_gender}")