# python generate_sentences.py A1 100

import os
import sys
import csv
import json
import time
import random
import datetime
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Завантаження змінних середовища
# 1. Визначаємо кореневу директорію (на рівень вище utils)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR) # Додаємо в path, щоб працювали імпорти з кореня (якщо знадобляться)

# 2. Явно вказуємо шлях до .env
load_dotenv(os.path.join(BASE_DIR, '.env'))

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY not found in .env file")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# --- КОНФІГУРАЦІЯ CEFR (Локальна копія для редагування) ---
# Оновлено з розлогими інструкціями для максимальної різноманітності словникового запасу на всіх рівнях,
# особливо A1: детальні вимоги до словника, заборони на повтори, приклади слів/конструкцій.
# Для кожного рівня — акцент на широкому охопленні лексики (кольори, числа, предмети, частини тіла, одяг тощо),
# щоб уникнути вузького ядра і примітивізму. Інструкції розгорнуті для моделі.
CEFR_GUIDELINES = {
 "A1": """
Sentences strictly 4-7 words (never under 4). Only Präsens.

Maximize structural variety: 40–60% sentences NOT starting with 'Ich'
(use 'Das ist...', 'Es ist...', 'Mein/e... ist...', 'Der/Die/Das...', 
'Wo ist...?', 'Wie heißt...?', 'Hast du...?', 'Heute ist...', 'Am Morgen...').
Always include in every batch: many wh-questions (Wo?, Wie?, Was?, Welche?, 
Wie viel?, Wie spät?, Woher?, Wohin?), yes/no questions, negations (nicht/kein/keine), 
sein + Adj/Ort, haben + concrete nouns.

Mix subjects strongly: Ich, Du, Er/Sie/Es, Wir, Das Auto, Die Jacke, 
Mein Bruder, Der Apfel, Die Lampe etc.

Topics: introductions, family/pets, home, hobbies, food, weather, routine, 
shopping, birthdays.

Natural, vivid, concrete, beginner-friendly like Goethe A1 model sentences 
or textbooks (Netzwerk A1, Schritte International A1, Menschen A1).

MANDATORY wide basic vocabulary coverage:
- Colors: rot, blau, grün, gelb, weiß, schwarz, orange, rosa, violett, braun
- Numbers: eins bis zwanzig (use in context: zwei Äpfel, drei Bücher, zehn Finger)
- Time of day: morgens, mittags, abends, nachts, um acht Uhr, halb neun
- Body parts: Kopf, Hand, Fuß, Auge, Nase, Mund, Arm, Bein, Haar, Finger
- Clothes: Hose, Shirt, Schuhe, Jacke, Hut, Rock, Pullover, Socken, Schal
- Fruits/vegetables: Apfel, Banane, Orange, Birne, Tomate, Karotte, Salat, Gurke
- Furniture/home items: Tisch, Stuhl, Bett, Sofa, Lampe, Fenster, Tür, Spiegel
- Rooms: Küche, Bad, Schlafzimmer, Wohnzimmer, Garten, Balkon
- Everyday objects: Buch, Stift, Telefon, Tasche, Schlüssel, Brille, Heft
- Animals: Hund, Katze, Vogel, Fisch, Pferd, Hase, Löwe, Elefant
- Nature: Baum, Blume, Sonne, Mond, Himmel, Wolke, Regen, Schnee, Wind

At least 50% sentences must use concrete nouns OTHER THAN Brot, Kaffee, Bus, 
Hund, Mutter, Fußball, Geschenk, Wetter, Pizza, Suppe.

ULTRA-STRICT REPETITION RULES:
- Any single noun/verb/adjective (except articles, prepositions, conjunctions) 
  → max 1 appearance per 25 sentences, max 2 per 100 sentences.
- Zero tolerance for overusing: kaufe, Brot, Milch, Eier, Tomate, Geburtstag, 
  Katze, Freunde, Schwester, Mutter, spielen Fußball, lesen Buch, Sonne scheint, 
  Auto rot/schnell, Küche hell/groß, Bus fährt, Ampel rot/grün.

In every 50 sentences:
- at least 6–8 wh-questions (Wo ist...?, Welche Farbe hat...?, Wie viele...?, 
  Was machst du...?, Wie spät ist es?, Woher kommst du?, Wohin gehst du?)
- at least 5–7 sentences with body parts (mein Kopf schmerzt, deine Hände sind warm)
- at least 4–6 sentences with animals (Vogel fliegt hoch, Fisch schwimmt im Wasser)
- more numbers in context (drei rote Bälle, fünf Stühle, zwanzig Euro)

Force multi-element descriptions in 20–25% of sentences:
'ein großer roter Ball liegt unter dem Tisch', 
'meine neue blaue Jacke hängt im Schrank', 
'zwei gelbe Bananen und drei Äpfel auf dem Küchentisch'.

Vary verbs strongly: essen, trinken, gehen, fahren, laufen, sitzen, stehen, liegen, 
schlafen, lesen, schreiben, spielen, malen, singen, tanzen, schwimmen, springen, 
lachen, weinen, rufen, suchen, finden.

Style: lively, concrete, visual, like real A1 flashcards or textbook drills — 
maximum lexical variety, no predictable patterns or boring loops, 
full coverage of basic 500–650 A1 words.
""",
    "A2": """
Sentences strictly 6–11 words (never under 6, never over 11).

Grammar:
- Präsens + Perfekt only (Perfekt dominant for past actions).
- Use haben / sein correctly (sein for motion and state change: gehen, fahren, kommen, bleiben).
- Modal verbs in Präsens: können, wollen, müssen, sollen, mögen.
- Separable verbs required: aufstehen, einkaufen, ankommen, ausgehen, mitkommen, anfangen, zuhören.
- Akkusativ fully, introduce Dativ with: mit, zu, von, bei, aus, nach.

Sentence structure & connectors:
- Use connectors actively: und, aber, oder, weil.
- At least 30–40% of sentences MUST include weil + reason.
- Vary sentence starts strongly.

START VARIATION RULES (MANDATORY):
- Max 50% sentences may start with "Ich".
- At least 30% must start with:
  Am..., Gestern..., Heute..., Manchmal..., Nach der Arbeit..., 
  Zu Hause..., Mit..., Weil..., Im Park..., Auf der Straße..., Beim...
- Avoid repeating the same starter (e.g. "Am Wochenende", "Gestern") more than once per 25 sentences.

ANTI-REPETITION RULES (A2-LEVEL, STRICT):
- Any concrete noun or main verb → max 1 use per 15 sentences, max 2 per 50.
- Avoid overused A2 crutches:
  jeden Morgen, am Wochenende, ich möchte, ich mag, ich arbeite, ich gehe,
  Kaffee, Freunde, Berlin, Fahrrad, Zug, Supermarkt.
- Do NOT reuse the same city, food, hobby, or transport item in one batch.

LEXICAL EXPANSION (MANDATORY DOMAINS):
Include across the batch (not per sentence):
- Emotions & states: müde, froh, nervös, zufrieden, enttäuscht, stolz, überrascht.
- Everyday problems: zu spät, kaputt, vergessen, keine Zeit, falsch, schwierig.
- Reactions & changes: sich freuen, sich ärgern, sich erinnern, sich fühlen, sich entscheiden.
- Places beyond basics: Museum, Apotheke, Rathaus, Büro, Werkstatt, Sporthalle, Bahnhofshalle.
- Activities beyond clichés: organisieren, vorbereiten, vergleichen, reparieren, planen, ausprobieren.

TOPICS (A2-appropriate, everyday):
Daily routine, past weekend, simple travel, shopping experiences, food preferences,
health & fitness, hobbies, workday situations, small problems, simple reasons.

STYLE & QUALITY:
- Natural, spoken, everyday German (Goethe A2 / Netzwerk / Schritte style).
- No textbook loops or mechanical patterns.
- Sentences must feel like short dialogue lines or diary notes.
- Prioritize lexical variety over “safe” phrasing.

ABSOLUTE NO-GO:
- No A1-style object drills (colors, body parts, counting).
- No abstract B1+ opinions.
- No repeated sentence skeletons like:
  "Ich + Verb + gern + Objekt"
  "Ich bin ... weil ich ..."

Goal:
High-quality, non-repetitive A2 sentences that expand vocabulary horizontally,
not just grammatically.

""",
    "B1": """
Sentences 8-13 words (avoid under 8 or over 14). Mandatory subordinate clauses: weil, dass, wenn, obwohl (at least 40-60% include one). 
Dominant: Perfekt for past experiences, Präteritum for war/hatte/modals (konnte, wollte, musste). 
Basic Konjunktiv II: würde + Infinitiv for wishes; hätte/wäre/konnte for simple unreal/conditions/dreams. 
Introduce Futur I sparingly (werden + Infinitiv) for plans (10-20% max). Avoid or minimize Plusquamperfekt (only very simple like 'hatte vergessen' if needed – no complex comparisons). 
Comparative/superlative (besser als). Simple opinions: ich finde, dass...; ich träume davon, dass.... 
Vary starts: Obwohl..., Weil..., Wenn..., Ich habe..., Gestern.... 
Topics: experiences, reasons, opinions, dreams, simple future plans, everyday + light abstract. 
Natural, not overloaded – like Goethe B1 model sentences (focus on weil/dass/obwohl/wenn, basic Konjunktiv II, no heavy past-in-past).
Use wide vocabulary: emotions (freudig, traurig, wütend, ängstlich, überrascht), abstract concepts (Glück, Freiheit, Erfolg, Misserfolg), 
work/school terms (Arbeit, Schule, Lehrer, Schüler, Prüfung, Job), travel (Reise, Hotel, Flughafen, Pass, Koffer), 
health (Arzt, Krankheit, Medizin, Sport, Ernährung). Include varied nouns/adjectives/verbs to cover full B1 vocabulary (1000+ words).
""",
    "B2": """
Sentences strictly 9-14 words (enforce: no less than 9, no more than 14). Vary syntax in batches of 5–10: include Passive (werden), relative clause (der/die/das/wo/wer), multi-part connector (zwar...aber, sowohl...als auch, entweder...oder, nicht nur...sondern auch) – one or two per sentence max. 
Use Plusquamperfekt simply (hatte + Partizip II). Konjunktiv II for hypotheticals. Futur I for plans/trends. 
Include occasional idioms/fixed expressions (es ist üblich, mit sich bringen, in der Lage sein). 
Topics: technology, culture, city life, environment, work, pros/cons. 
Natural, repeatable, exam-like (Goethe/telc B2 style) – clear, pronounceable, not overloaded.
Use wide vocabulary: technology terms (Internet, Smartphone, App, Computer, Software, Hardware), environment (Umweltschutz, Klimawandel, Recycling, Nachhaltigkeit, Verschmutzung), 
culture (Tradition, Festival, Kunst, Musik, Literatur, Film), work (Karriere, Bewerbung, Meeting, Chef, Kollege), 
abstract pros/cons (Vorteil, Nachteil, Chance, Risiko). Ensure full coverage of B2 vocabulary (2000+ words) with varied terms in each sentence.
""",
    "C1": """
Sentences 12-18 words (strictly no less than 12, no more than 18). Use sophisticated structures: nominalization (die Tatsache, dass…; die Notwendigkeit; aufgrund eines Fehlers), complex subordinate clauses (In Anbetracht der Tatsache, dass…; Um…zu…, ist es unabdingbar, dass…). 
Include Konjunktiv I in reported speech or formal contexts (sei, habe). Full Passive and Zustandspassiv (wurde befreit, war befreit worden). 
Advanced connectors for cohesion and logic (insofern, folglich, zwar…dennoch, angesichts, aufgrund, infolge). 
Nuanced/fixed expressions (nicht verwunderlich, es gelingt, unabdingbar, sich Zeit nehmen). 
Topics: society, culture, work processes, environment, technology impacts, abstract pros/cons. 
Flow logical and cohesive, natural like advanced German texts or Goethe C1 models – sophisticated but not overly rhetorical yet.
Use wide, nuanced vocabulary: society (Gesellschaft, Ungleichheit, Integration, Diskriminierung, Demokratie, Diktatur), 
culture (Kulturalität, Identität, Globalisierung, Multikulturalismus, Tradition vs. Moderne), 
work (Produktivität, Motivation, Burnout, Work-Life-Balance, Karriereleiter), 
environment (Nachhaltigkeit, Klimakrise, Biodiversität, Ressourcenschonung, Ökologie). 
Ensure broad lexical coverage with specific, advanced terms in every sentence for full C1 vocabulary depth (3000+ words).
""",
    "C2": """
Sentences 14-20 words (strictly no more than 22, no less than 14). Mastery level: long, nuanced sentences with rhetorical devices (rhetorische Fragen, Ironie, Kontrastkonstruktionen, litotes, euphemism, hyperbole). 
Subtext and implicit criticism of society, trends, human nature. Use all tenses/moods fluently and stylistically (Konjunktiv I/II advanced, Futur II for assumptions, Plusquamperfekt narrative). 
Highly specific, academic, literary or journalistic vocabulary (grassierend, höhlt aus, wohlklingend, Zurschaustellung, Selbstoptimierungswelle, Muße, Kontemplation, unerschütterlich, keineswegs). 
Multi-part connectors (nicht nur … sondern auch, zwar … doch, mehr … als, allzu oft). 
Topics: social inequality, self-optimization culture, spirituality vs. reality, charity hypocrisy, human-animal relations, modern alienation. 
Flow elegant, cohesive, with critical depth – like high-level opinion articles, essays or literary commentary in German media (Zeit, FAZ Feuilleton, Philosophie Magazin).
Use extremely wide, precise vocabulary: philosophical terms (Existentialismus, Nihilismus, Hedonismus, Stoizismus), 
journalistic (Polarisierung, Populismus, Medienmanipulation, Fake News, Narrative), 
literary (Metapher, Allegorie, Ironie, Satire, Paradoxon), 
social critique (Kapitalismus, Konsumgesellschaft, Alienation, Authentizität, Empathie). 
Cover maximum lexical range with stylistic variety, academic depth, and implicit meanings in each sentence for full C2 mastery (5000+ words).
"""
}

A1_TOPICS = [
    # 🎨 Colors & visual objects
    "Colors with everyday objects (rot, blau, grün, gelb, schwarz, weiß)",
    "Describing object colors and size",
    "Matching colors with things",
    "Asking about colors (Welche Farbe?)",

    # 🔢 Numbers & quantities
    "Counting objects from one to twenty",
    "Asking and answering how many (Wie viele?)",
    "Prices and simple amounts",
    "Numbers with everyday items",

    # ⏰ Time & simple schedule
    "Time of day (morgens, mittags, abends, nachts)",
    "Clock times (um acht Uhr, halb neun)",
    "Daily moments with time words",
    "Asking for the time (Wie spät ist es?)",

    # 👕 Clothes & appearance
    "Clothes people wear today",
    "Describing clothes with colors",
    "Asking about clothes",
    "Putting on and wearing clothes",

    # 🧍 Body parts
    "Basic body parts",
    "Simple body descriptions",
    "Using body parts with adjectives",
    "Asking about body parts",

    # 🏠 Home & rooms
    "Rooms in the house",
    "Objects in each room",
    "Describing rooms simply",
    "Asking where things are (Wo ist?)",

    # 🪑 Furniture & objects
    "Furniture in the home",
    "Objects on, under, in places",
    "Describing position (auf, unter, in)",
    "Simple location questions",

    # 🍎 Food & drinks
    "Fruits and vegetables",
    "Food people eat every day",
    "Drinks people like",
    "Asking for food and drinks",

    # 🐶 Animals & nature
    "Common animals",
    "Animals and actions",
    "Nature objects around us",
    "Weather words and nature",

    # 🚶 Actions & movement
    "Simple daily actions",
    "Going and coming",
    "Sitting, standing, lying",
    "Finding and looking for things",

    # 👨‍👩‍👧 People & family
    "Family members",
    "Talking about people simply",
    "Introducing people",
    "Asking names (Wie heißt?)",

    # 🏫 Places & city
    "Places in the city",
    "Objects in public places",
    "Going to places",
    "Asking where places are",

    # 👜 Everyday objects
    "Things people carry",
    "Objects people use daily",
    "Naming common objects",
    "Asking what something is (Was ist das?)",

    # 🌦 Weather
    "Simple weather descriptions",
    "Weather today",
    "Weather with seasons",

    # 🎉 Simple events
    "Birthdays and basic parties",
    "Giving and receiving gifts",
    "Simple celebrations",

    # ❓ Questions & negation
    "Yes and no questions",
    "Negation with nicht and kein",
    "Simple answers and reactions",

    # 🗣️ Basic communication
    "Greetings and farewells",
    "Polite words",
    "Simple requests",
    "Saying thank you and sorry"

    # General vocab
    "Colors and Everyday Objects (rot, blau, grün, gelb, weiß, schwarz, orange, rosa, violett, braun)",
    "Clothes and Accessories (Hose, Shirt, Schuhe, Jacke, Hut, Rock, Pullover, Socken, Handschuhe, Schal, Tasche, Gürtel)",
    "Body Parts and Descriptions (Kopf, Hand, Fuß, Auge, Nase, Mund, Arm, Bein, Haar, Finger, Rücken, Bauch)",
    "Numbers and Counting Things (eins, zwei, drei, vier, fünf, sechs, sieben, acht, neun, zehn, elf, zwölf, dreizehn, vierzehn, fünfzehn, sechzehn, siebzehn, achtzehn, neunzehn, zwanzig)",
    "Time of Day and Clocks (morgens, mittags, abends, nachts, um acht Uhr, halb neun, Viertel nach zehn, Uhrzeit, Wecker)",
    "Fruits and Vegetables Variety (Apfel, Banane, Orange, Birne, Tomate, Karotte, Salat, Kartoffel, Zwiebel, Gurke, Traube, Erdbeere, Kirsche, Zitrone)",
    "Drinks and Beverages (not only coffee: Wasser, Saft, Tee, Milch, Limonade, Cola, Wein, Bier, Kakao, Smoothie)",
    "School Supplies and Office Items (Buch, Stift, Heft, Radiergummi, Lineal, Schere, Kleber, Mappe, Rucksack, Computer)",
    "Furniture and Home Items (Tisch, Stuhl, Bett, Sofa, Lampe, Fenster, Tür, Spiegel, Regal, Uhr, Kühlschrank, Herd)",
    "Rooms in the House and Apartment (Küche, Bad, Schlafzimmer, Wohnzimmer, Garten, Balkon, Flur, Keller, Dachboden, Garage)",
    "Daily Routine Items and Tools (Uhr, Telefon, Buch, Stift, Schlüssel, Brille, Computer, Fernseher, Radio, Spielzeug, Bürste, Zahnpasta)",
    "Simple Descriptions of People and Appearance (jung, alt, groß, klein, dick, dünn, blond, brunett, langhaarig, kurze Haare, freundlich, traurig)",
    "Different Animals and Pets (Hund, Katze, Vogel, Fisch, Pferd, Kuh, Schaf, Maus, Elefant, Giraffe, Löwe, Tiger, Affe, Hase)",
    "Nature Elements and Outdoors (Baum, Blume, Sonne, Mond, Stern, Himmel, Wolke, Regen, Schnee, Wind, Fluss, See, Berg, Wald)",
    "City Objects and Places (Ampel, Bank, Laden, Park, Straße, Haus, Brücke, Turm, Platz, Kirche, Schule, Krankenhaus)",
    "Transport Variety and Vehicles (Auto, Fahrrad, Zug, Flugzeug, Schiff, Bus, U-Bahn, Taxi, Motorrad, Roller, Boot)",
    "Weather Adjectives and Seasons (sonnig, regnerisch, windig, schneereich, heiß, kalt, warm, kühl, Frühling, Sommer, Herbst, Winter)",
    "Family Members and Relatives (Vater, Mutter, Bruder, Schwester, Oma, Opa, Onkel, Tante, Cousin, Cousine, Baby, Kind)",
    "Friends Descriptions and Activities (bester Freund, neue Freundin, zusammen spielen, besuchen, lachen, helfen, teilen, streiten, versöhnen)",
    "Simple Shopping Items in Supermarket (Milch, Eier, Käse, Wurst, Obst, Gemüse, Süßigkeiten, Getränke, Brot, Butter, Joghurt, Honig)",
    "Birthdays and Party Items (Geburtstag, Kuchen, Kerzen, Geschenke, Ballons, Party, Einladung, Musik, Tanzen, Feiern)",
    "Hobbies besides Sports (Malen, Singen, Tanzen, Lesen, Zeichnen, Basteln, Sammeln, Fotografieren, Kochen, Gärtnern)",
    "Daily Routine", "Family & Relationships", "Friendship", "Pets & Animals",
    "Food & Cooking", "Fast Food", "Shopping & Groceries", "Gifts & Presents",
    "Birthdays", "Weather & Seasons", "Hobbies & Free Time", "Housing & Furniture",
    "City Life", "Public Transport", "Travel & Transport", "Restaurants & Cafes",
    "Coffee Culture", "Cleaning & Chores", "Sleep & Dreams", "Weekend Activities",
]


A2_TOPICS = [
    # ⏰ Time & routine with variation
    "Daily routine with time expressions (jeden Tag, morgens, abends)",
    "Yesterday and last weekend activities (Perfekt)",
    "Plans for tomorrow and next week",
    "Regular habits and exceptions (oft, selten, manchmal)",
    "Changing routines and new schedules",

    # 🧠 Reasons & opinions (weil)
    "Giving reasons with weil",
    "Explaining simple decisions",
    "Likes and dislikes with explanations",
    "Choosing between two options (oder, aber)",
    "Simple opinions about daily life",

    # 🧳 Travel & movement (sein + Perfekt)
    "Travel experiences (bin gefahren, bin geflogen)",
    "Short trips and excursions",
    "Arriving, leaving, changing transport",
    "Problems during travel and solutions",
    "Asking and giving directions",

    # 🛒 Shopping & services
    "Shopping with prices and quantities",
    "Comparing products in shops",
    "Returning or exchanging items",
    "Ordering food or drinks",
    "Paying, receipts, and problems",

    # 🏠 Home & everyday problems
    "Household chores and responsibilities",
    "Problems at home and simple solutions",
    "Inviting guests and preparing the home",
    "Living alone vs with others",
    "Rules at home or in the apartment",

    # 👨‍👩‍👧 Family & social life
    "Talking about family members and their routines",
    "Visiting relatives or friends",
    "Making invitations and arrangements",
    "Accepting and refusing politely",
    "Helping others and asking for help",

    # 💼 Work & school (A2-safe)
    "A typical workday",
    "Simple tasks at work or school",
    "Meetings and schedules",
    "Talking about colleagues or classmates",
    "Problems at work or school",

    # 🏥 Health & body
    "Health problems and symptoms",
    "Doctor visits and advice",
    "Feeling better or worse",
    "Sports and physical activity",
    "Resting and recovery",

    # 🎨 Free time & hobbies
    "Hobbies with frequency",
    "Trying new activities",
    "Plans for free time",
    "Indoor vs outdoor activities",
    "Weather influence on free time",

    # 📱 Technology & communication
    "Using phones and apps daily",
    "Online communication with friends",
    "Problems with technology",
    "Learning something online",
    "Digital habits",

    # 🍽️ Food & cooking
    "Cooking simple meals",
    "Eating habits during the week",
    "Trying new food",
    "Eating out vs eating at home",
    "Talking about favorite dishes",

    # 🧠 Life situations
    "Making simple decisions",
    "Small everyday problems and solutions",
    "Explaining what went wrong",
    "Reacting to unexpected situations",
    "Talking about changes in life"
]

B1_TOPICS = [
    # 🧠 Opinions & reasons
    "Giving opinions with reasons (ich finde, dass …)",
    "Agreeing and disagreeing politely",
    "Explaining personal preferences",
    "Talking about advantages and disadvantages",
    "Changing opinions over time",

    # 🕰 Past experiences
    "Important life experiences",
    "Memorable trips and journeys",
    "First experiences (first job, first trip)",
    "Good and bad experiences",
    "Learning from past mistakes",

    # 🔮 Plans & dreams
    "Future plans and goals",
    "Dreams and ambitions",
    "Plans that may change",
    "Talking about hopes and fears",
    "Decisions about the future",

    # 🧑‍💼 Work & education
    "Work experience and responsibilities",
    "School and study experiences",
    "Exams and preparation",
    "Career choices and changes",
    "Balancing work and free time",

    # 🌍 Travel & culture
    "Travel experiences abroad",
    "Cultural differences",
    "Living in another country",
    "Language learning experiences",
    "Meeting people from other cultures",

    # 🧠 Problems & solutions
    "Everyday problems and how to solve them",
    "Unexpected situations",
    "Giving advice",
    "Talking about difficulties",
    "Finding compromises",

    # 💬 Communication & relationships
    "Friendships and conflicts",
    "Family relationships",
    "Misunderstandings and explanations",
    "Expressing feelings",
    "Talking about important conversations",

    # 🏥 Health & lifestyle
    "Health experiences",
    "Changing habits",
    "Stress and relaxation",
    "Sport and motivation",
    "Work-life balance",

    # 📱 Technology & media
    "Technology in everyday life",
    "Social media experiences",
    "Advantages and disadvantages of smartphones",
    "Digital communication",
    "Online learning",

    # 🌱 Society & environment (B1-safe)
    "Environmental awareness in daily life",
    "Small actions for the environment",
    "Living in a city vs countryside",
    "Social rules and behavior",
    "Changes in modern life",

    # 🎨 Culture & free time
    "Cultural events and experiences",
    "Books, films, and music opinions",
    "Free time activities",
    "Trying new hobbies",
    "Creative activities",

    # 🧠 Reflection & conditionals
    "What would I do differently (würde)",
    "If situations and consequences (wenn)",
    "Imagining different outcomes",
    "Lessons learned from experience",
    "Personal development"
]

B2_TOPICS = [
    "Money & Finance", "Productivity", "Time Management", "Leadership",
    "Teamwork", "Communication Skills", "Public Speaking", "News & Media",
    "Advertising", "Celebrities", "Influencers", "Privacy & Security",
    "Smartphones", "Laptops & Computers", "Artificial Intelligence", "Robots",
    "Virtual Reality", "Recycling", "Climate Change", "Nature & Environment",
    "Design", "Architecture", "Psychology & Emotions", "Conflict & Resolution",
    "Cultural Differences", "Global Economy", "Social Trends", "Innovation Ideas",
    "Ethical Dilemmas", "Media Influence", "Digital Ethics"
]

C1_TOPICS = [
    "Politics & Society", "History & Culture", "Traditions & Festivals",
    "Philosophy", "Religion & Spirituality", "Science & Innovation",
    "Space & Universe", "Global Issues", "Poverty & Wealth", "Equality",
    "Justice", "Law & Order", "Crime & Punishment", "Safety",
    "Emergency Services", "Healthcare System", "Volunteering", "Charity",
    "Art & Museums", "Countryside Life", "Painting & Drawing", "DIY & Crafts",
    "Architecture", "Social Inequality Debates", "Self-Improvement Philosophies",
    "Cultural Globalization", "Environmental Policies", "Technological Ethics",
    "Human Rights", "Mental Health Awareness", "Economic Theories", "Literary Analysis"
]

C2_TOPICS = C1_TOPICS

LEVEL_RULES = {
    "A1": A1_TOPICS,
    "A2": A2_TOPICS,
    "B1": B1_TOPICS,
    "B2": B2_TOPICS,
    "C1": C1_TOPICS,
    "C2": C2_TOPICS
}

def clean_json_response(text):
    """Очищає відповідь від Markdown блоків."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text

def generate_batch(level, count, topics_subset):
    """Генерує пакет речень."""
    
    level_rules = CEFR_GUIDELINES.get(level.upper(), CEFR_GUIDELINES["A2"])
    
    # Формуємо список тем для цього батчу
    topics_str = ", ".join(topics_subset)

    prompt = f"""
    Role: Expert German Linguist.
    Task: Generate exactly {count} unique German sentences.
    Level: {level.upper()}
    
    Use these topics (one sentence per topic if possible):
    {topics_str}
    
    STRICT CEFR RULES for {level.upper()}:
    {level_rules}
    
    Requirements:
    1. Sentences must be grammatically correct and sound natural.
    2. Provide translations in Ukrainian (uk) and English (en).
    3. Output must be a valid JSON list of objects.

    Extra for A1: Prioritize lexical diversity over repetition. Track used words and force new ones: use different nouns/adjectives/verbs/colors/numbers/objects in EVERY sentence. 
    No more than 1–2 'Ich kaufe...', 'meine Schwester/mutter/freundin' per 50 sentences. 
    Force variety in verbs: essen, trinken, gehen, fahren, laufen, sitzen, stehen, liegen, schlafen, lesen, schreiben, malen, singen, tanzen, schwimmen, springen, lachen, weinen.
    
    JSON Format:
    [
        {{
            "de": "German sentence",
            "uk": "Ukrainian translation",
            "en": "English translation",
            "topic": "Topic used"
        }}
    ]
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=1.37 if level.upper() == "A1" else 1.1,
            )
        )
        
        cleaned_text = clean_json_response(response.text)
        data = json.loads(cleaned_text)
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "sentences" in data:
            return data["sentences"]
        else:
            return []
            
    except Exception as e:
        print(f"Error generating batch: {e}")
        return []

def main():
    # 1. Парсинг аргументів
    if len(sys.argv) < 3:
        print("Usage: python generate_sentences.py <level> <count>")
        print("Example: python generate_sentences.py A2 100")
        sys.exit(1)

    level = sys.argv[1].upper()
    try:
        total_count = int(sys.argv[2])
    except ValueError:
        print("Error: Count must be a number.")
        sys.exit(1)

    if level not in CEFR_GUIDELINES:
        print(f"Warning: Level {level} not found in guidelines. Using default rules or generic prompt.")

    # Визначаємо доступні теми для рівня
    available_topics = LEVEL_RULES.get(level, A2_TOPICS)

    # 2. Підготовка файлу
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sentences_{level}_{timestamp}.csv"
    
    print(f"--- Starting generation ---")
    print(f"Level: {level}")
    print(f"Target: {total_count} sentences")
    print(f"Output file: {filename}")
    print(f"---------------------------")

    # 3. Генерація пакетами (щоб не перевантажити контекст і отримати валідний JSON)
    BATCH_SIZE = 20
    generated_count = 0
    
    # Відкриваємо файл відразу для запису
    with open(filename, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['de', 'uk', 'en', 'topic', 'level']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        while generated_count < total_count:
            # Визначаємо розмір поточного пакету (останній може бути меншим)
            current_batch_size = min(BATCH_SIZE, total_count - generated_count)
            
            # Вибираємо випадкові теми
            if len(available_topics) >= current_batch_size:
                batch_topics = random.sample(available_topics, current_batch_size)
            else:
                batch_topics = random.choices(available_topics, k=current_batch_size)
            
            print(f"Generating batch {generated_count + 1}-{generated_count + current_batch_size}...")
            
            sentences = generate_batch(level, current_batch_size, batch_topics)
            
            if not sentences:
                print("Failed to generate batch. Retrying in 2 seconds...")
                time.sleep(2)
                continue

            # Запис у файл
            for s in sentences:
                # Нормалізація ключів (іноді модель може дати 'ua' замість 'uk')
                uk_text = s.get('uk') or s.get('ua') or ""
                
                row = {
                    'de': s.get('de', ''),
                    'uk': uk_text,
                    'en': s.get('en', ''),
                    'topic': s.get('topic', ''),
                    'level': level
                }
                writer.writerow(row)
            
            generated_count += len(sentences)
            
            # Невелика пауза, щоб бути ввічливим до API
            time.sleep(0.5)

    print(f"\nDone! Successfully generated {generated_count} sentences.")
    print(f"Saved to: {os.path.abspath(filename)}")

if __name__ == "__main__":
    main()