import os
import uuid
import hashlib
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import json
import google.generativeai as genai

from database import get_db, init_db
import services

load_dotenv()
init_db()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-key")
AUDIO_DIR = "data/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    with get_db() as conn:
        u = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if u: return User(u['id'], u['email'])
    return None

# --- AUTH ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash('Заповніть всі поля')
            return redirect(url_for('register'))
        
        with get_db() as conn:
            exists = conn.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone()
            if exists:
                flash('Email вже зареєстровано')
                return redirect(url_for('register'))
            
            uid = str(uuid.uuid4())
            conn.execute('INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)',
                         (uid, email, generate_password_hash(password)))
            conn.commit()
        flash('Успішна реєстрація! Увійдіть.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        with get_db() as conn:
            u = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            if u and check_password_hash(u['password_hash'], password):
                login_user(User(u['id'], u['email']))
                return redirect(url_for('index'))
        flash('Невірний email або пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- APP ROUTES ---

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
@login_required
def generate():
    req = request.json
    lang = "Ukrainian" if req.get('lang') == 'ukr' else "English"
    data = services.generate_german_text(req['topic'], req['count'], req['level'], lang)
    
    tid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute('INSERT INTO texts (id, user_id, title, level, content_json) VALUES (?,?,?,?,?)',
                     (tid, current_user.id, data['title'], req['level'], json.dumps(data['sentences'])))
        conn.commit()
    return jsonify({"id": tid})

@app.route('/api/explain_grammar', methods=['POST'])
@login_required
def explain_grammar():
    req = request.json
    sentence = req.get('sentence')
    text_id = req.get('text_id')
    sentence_index = req.get('sentence_index')

    # 1. Перевіряємо кеш в базі
    if text_id and sentence_index is not None:
        with get_db() as conn:
            cached = conn.execute('SELECT explanation FROM grammar_explanations WHERE text_id = ? AND sentence_index = ?', 
                                  (text_id, sentence_index)).fetchone()
            if cached:
                return jsonify({"explanation": cached['explanation']})

    # 2. Якщо немає в кеші - генеруємо
    # Використовуємо Gemini для пояснення
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"Explain the grammar of this German sentence for a Ukrainian student. Break down cases (Nominativ, Dativ, etc.), declensions, and sentence structure. Keep it concise, clear and use formatting (bolding).  Answer in Ukrainian. Sentence: '{sentence}'"
    
    try:
        response = model.generate_content(prompt)
        explanation = response.text
        
        # 3. Зберігаємо в базу
        if text_id and sentence_index is not None:
            with get_db() as conn:
                conn.execute('INSERT OR REPLACE INTO grammar_explanations (text_id, sentence_index, explanation) VALUES (?, ?, ?)',
                             (text_id, sentence_index, explanation))
                conn.commit()
        
        return jsonify({"explanation": explanation})
    except Exception as e:
        return jsonify({"error": "Не вдалося отримати пояснення від AI"}), 500

@app.route('/library')
@login_required
def library():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM texts WHERE user_id = ? ORDER BY rowid DESC', (current_user.id,)).fetchall()
    return render_template('library.html', texts=rows)

@app.route('/view/<tid>')
@login_required
def view_text(tid):
    with get_db() as conn:
        t = conn.execute('SELECT * FROM texts WHERE id = ? AND user_id = ?', (tid, current_user.id)).fetchone()
        if not t: return "404", 404
        vocab_rows = [dict(row) for row in conn.execute('SELECT * FROM vocabulary WHERE user_id = ? AND text_id = ?', (current_user.id, tid)).fetchall()]
        
    sentences = json.loads(t['content_json'])
    
    # --- НОВА ЛОГІКА ПІДСВІТКИ (ЗА КООРДИНАТАМИ) ---
    for i, s in enumerate(sentences):
        original_text = s['de']
        
        # Знаходимо слова, які належать САМЕ ДО ЦЬОГО речення
        my_words = [v for v in vocab_rows if v['sentence_index'] == i]
        
        # Сортуємо їх з кінця до початку (reverse), 
        # щоб вставка тегів не збивала індекси попередніх слів!
        my_words.sort(key=lambda x: x['start_index'], reverse=True)
        
        # Перетворюємо рядок на список символів, бо стрічки незмінні
        # Але простіше різати стрічку
        final_html = original_text
        
        for w in my_words:
            start = w['start_index']
            end = w['end_index']
            
            # Перевірка на валідність індексів (щоб не крашнулось, якщо текст змінився)
            if start is not None and start >= 0 and end <= len(original_text):
                # Вставка тегу
                # Беремо оригінальне слово за координатами (надійніше)
                word_in_text = original_text[start:end]
                replacement = f'<span class="learned" data-wid="{w["id"]}">{word_in_text}</span>'
                
                # "Хірургічна" вставка
                # Оскільки ми йдемо з кінця, ми можемо різати final_html
                # Але final_html вже змінений... стоп.
                # Якщо ми йдемо з кінця, то індекси початку речення НЕ ЗМІНЮЮТЬСЯ.
                # Тому ми ріжемо original_text? Ні.
                
                # Правильний алгоритм з кінця:
                # final_html зараз дорівнює original_text.
                # Ми беремо [0:start] + replacement + [end:]
                # АЛЕ наступний цикл (який ближче до початку) візьме ВЖЕ ЗМІНЕНИЙ final_html?
                # Ні, індекси start/end відносяться до ОРИГІНАЛУ.
                
                # Тому краще так: ріжемо final_html? Ні.
                pass 
        
        # Переписуємо алгоритм складання рядка, щоб було надійно
        # Створюємо мапу замін
        # Але найпростіше - таки різати рядок з кінця.
        # Тільки треба пам'ятати, що start/end валідні для ORIGINAL_TEXT.
        
        # Робочий метод:
        # Розбиваємо оригінал на шматки і збираємо заново.
        last_idx = len(original_text)
        built_str = ""
        
        # Сортуємо слова з кінця (reverse=True по start_index)
        # Приклад: текст 100 симв. Слова на 80-90 і 10-20.
        # 1. Беремо слово 80-90. built_str = replacement + original[90:100]
        # last_idx стає 80.
        # 2. Беремо слово 10-20. built_str = replacement + original[20:80] + built_str
        # last_idx стає 10.
        # 3. Кінець: built_str = original[0:10] + built_str.
        
        for w in my_words:
            start = w['start_index']
            end = w['end_index']
            
            if start is not None and start >= 0:
                # Додаємо хвіст після слова
                built_str = original_text[end:last_idx] + built_str
                # Додаємо саме слово в тегу
                word_val = original_text[start:end]
                built_str = f'<span class="learned" data-wid="{w["id"]}">{word_val}</span>' + built_str
                # Зсуваємо вказівник
                last_idx = start
        
        # Додаємо початок речення
        built_str = original_text[0:last_idx] + built_str
        
        s['de_html'] = built_str
        
    return render_template('view.html', text=t, sentences=sentences, vocab=vocab_rows)

@app.route('/api/quick_translate', methods=['POST'])
@login_required
def quick_translate():
    req = request.json
    word_data = services.translate_word(req['text'], req['ctx'])
    wid = str(uuid.uuid4())
    
    # Вираховуємо індекси на сервері (це простіше і надійніше, ніж в JS з купою тегів)
    full_sentence = req['ctx']
    word = req['text']
    
    # Знаходимо де починається слово. 
    # Увага: це знайде ПЕРШЕ входження у реченні. 
    # Якщо в реченні два рази "die", виділиться перше. Це компроміс для MVP.
    start_index = full_sentence.find(word)
    end_index = start_index + len(word)
    
    sentence_index = req.get('sent_idx', 0) # Отримуємо номер речення
    
    with get_db() as conn:
        conn.execute('''INSERT INTO vocabulary 
                        (id, user_id, text_id, origin, display, ua, en, ctx, sentence_index, start_index, end_index) 
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                     (wid, current_user.id, req.get('tid'), word, 
                      word_data['display'], word_data['ua'], word_data['en'], req['ctx'],
                      sentence_index, start_index, end_index))
        conn.commit()
    return jsonify({"ok": True})

@app.route('/vocab')
@login_required
def vocab():
    with get_db() as conn:
        words = conn.execute('SELECT * FROM vocabulary WHERE user_id = ? AND is_favorite = 1 ORDER BY rowid DESC', (current_user.id,)).fetchall()
    return render_template('vocab.html', words=words)

@app.route('/api/toggle_fav', methods=['POST'])
@login_required
def toggle_fav():
    req = request.json
    with get_db() as conn:
        conn.execute('UPDATE vocabulary SET is_favorite = 1 - is_favorite WHERE id = ? AND user_id = ?', 
                     (req['id'], current_user.id))
        conn.commit()
    return jsonify({"ok": True})

@app.route('/api/remove_word', methods=['POST'])
@login_required
def remove_word():
    req = request.json
    wid = req.get('id')
    # Параметр 'from_vocab' скаже нам, звідки ми видаляємо (зі сторінки словника чи тексту)
    from_vocab = req.get('from_vocab', False) 
    
    with get_db() as conn:
        if from_vocab:
            # Якщо видаляємо зі сторінки Словника -> просто знімаємо зірочку
            # Слово залишається в базі (прив'язаним до тексту), якщо воно має text_id
            conn.execute('UPDATE vocabulary SET is_favorite = 0 WHERE id = ? AND user_id = ?', (wid, current_user.id))
            # (Опціонально) Чистка сміття: якщо слово не прив'язане до тексту і не улюблене - видаляємо зовсім
            conn.execute('DELETE FROM vocabulary WHERE id = ? AND is_favorite = 0 AND text_id IS NULL', (wid,))
        else:
            # Якщо видаляємо зі сторінки Тексту
            word = conn.execute('SELECT is_favorite FROM vocabulary WHERE id = ?', (wid,)).fetchone()
            if word and word['is_favorite'] == 1:
                # Якщо слово улюблене -> не видаляємо з бази, а лише відв'язуємо від тексту
                conn.execute('UPDATE vocabulary SET text_id = NULL WHERE id = ? AND user_id = ?', (wid, current_user.id))
            else:
                # Якщо не улюблене -> видаляємо назавжди
                conn.execute('DELETE FROM vocabulary WHERE id = ? AND user_id = ?', (wid, current_user.id))
        
        conn.commit()
    return jsonify({"ok": True})

@app.route('/api/delete_text', methods=['POST'])
@login_required
def delete_text():
    tid = request.json.get('id')
    with get_db() as conn:
        conn.execute('DELETE FROM texts WHERE id = ? AND user_id = ?', (tid, current_user.id))
        # ВИПРАВЛЕННЯ: При видаленні тексту, улюблені слова не видаляються, а просто відв'язуються (text_id = NULL)
        conn.execute('UPDATE vocabulary SET text_id = NULL WHERE text_id = ? AND user_id = ? AND is_favorite = 1', (tid, current_user.id))
        # А не улюблені видаляються
        conn.execute('DELETE FROM vocabulary WHERE text_id = ? AND user_id = ? AND is_favorite = 0', (tid, current_user.id))
        # Видаляємо кеш граматики для цього тексту
        conn.execute('DELETE FROM grammar_explanations WHERE text_id = ?', (tid,))
        conn.commit()
    return jsonify({"ok": True})

@app.route('/api/tts', methods=['POST'])
@login_required
def tts():
    tts_client = services.get_tts_client()
    if not tts_client: return jsonify({"error": "TTS not configured"}), 500
    
    text = request.json.get('text', '').split('(')[0].strip()
    file_hash = hashlib.md5(text.encode()).hexdigest()
    filename = f"{file_hash}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    if not os.path.exists(filepath):
        from google.cloud import texttospeech
        s_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(language_code="de-DE", name="de-DE-Studio-C")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        response = tts_client.synthesize_speech(input=s_input, voice=voice, audio_config=audio_config)
        with open(filepath, "wb") as out:
            out.write(response.audio_content)
            
    return jsonify({"url": f"/audio/{filename}"})

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)