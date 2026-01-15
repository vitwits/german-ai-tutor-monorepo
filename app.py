import os
import uuid
import hashlib
import math
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

# --- TRANSLATIONS ---
UI_STRINGS = {
    'ukr': {
        'settings': 'Налаштування',
        'library': 'Бібліотека',
        'logout': 'Вийти',
        'generate_new': 'Створити Урок',
        'topic': 'Тема уроку',
        'level': 'Рівень',
        'count': 'Кількість речень',
        'generate_btn': 'Згенерувати',
        'vocab': 'Словник',
        'back': 'Назад',
        'topic_placeholder': 'Наприклад: Подорож, IT, Спорт...',
        'generating': 'Генерація...',
        'error_alert': 'Помилка',
        'show_translation': 'Показати переклад',
        'hide_translation': 'Приховати переклад',
        'play_all': 'ПРОГРАТИ ВСЕ',
        'stop': 'ЗУПИНИТИ',
        'add_translation': '+ ПЕРЕКЛАСТИ',
        'confirm_remove_word_from_text': 'Видалити слово з цього тексту?',
        'grammar_tooltip': 'Пояснити граматику',
        'grammar_explanation_error': 'Не вдалося отримати пояснення.',
        'lesson_vocab': 'СЛОВНИК УРОКУ',
        'empty_vocab_prompt': 'Виділіть слово в тексті, щоб додати переклад.',
        'my_vocab': 'МІЙ СЛОВНИК',
        'context': 'Контекст:',
        'go_to_text': 'Перейти до тексту',
        'confirm_remove_from_fav': 'Видалити зі списку улюблених? (Слово залишиться в тексті)',
        'save_settings': 'Зберегти',
        'interface_lang': 'Мова інтерфейсу',
        'login_header': 'Вхід',
        'login_btn': 'Увійти',
        'password': 'Пароль',
        'no_account': 'Немає аккаунту?',
        'register_link': 'Зареєструватися',
        'my_texts': 'Мої тексти',
        'read': 'Читати',
        'main': 'Головна',
        'edit_translation': 'Редагувати переклад',
        'confirm_title': 'Підтвердження',
        'confirm_delete_text_msg': 'Ви впевнені, що хочете видалити цей текст?',
        'btn_delete': 'Видалити',
        'btn_cancel': 'Скасувати',
        'confirm_title': 'Підтвердження',
        'confirm_delete_text_msg': 'Видалити цей текст? Весь прогрес по ньому буде втрачено.',
        'btn_delete': 'Видалити',
        'btn_cancel': 'Скасувати',
        'text_deleted': 'Текст видалено',
        'word_deleted': 'Слово видалено',
        'word_added': 'Слово додано',
        'undo': 'ВІДМІНИТИ',
        'settings_saved': 'Налаштування збережено',
        'error_generic': 'Сталася помилка',
    },
    'eng': {
        'settings': 'Settings',
        'library': 'Library',
        'logout': 'Logout',
        'generate_new': 'Create Lesson',
        'topic': 'Lesson Topic',
        'level': 'Level',
        'count': 'Sentence count',
        'generate_btn': 'Generate',
        'vocab': 'Vocabulary',
        'back': 'Back',
        'topic_placeholder': 'E.g.: Travel, IT, Sports...',
        'generating': 'Generating...',
        'error_alert': 'Error',
        'show_translation': 'Show translation',
        'hide_translation': 'Hide translation',
        'play_all': 'PLAY ALL',
        'stop': 'STOP',
        'add_translation': '+ TRANSLATE',
        'confirm_remove_word_from_text': 'Remove word from this text?',
        'grammar_tooltip': 'Explain grammar',
        'grammar_explanation_error': 'Failed to get explanation.',
        'lesson_vocab': 'LESSON VOCABULARY',
        'empty_vocab_prompt': 'Highlight a word in the text to add a translation.',
        'my_vocab': 'MY VOCABULARY',
        'context': 'Context:',
        'go_to_text': 'Go to text',
        'confirm_remove_from_fav': 'Remove from favorites? (The word will remain in the text)',
        'save_settings': 'Save',
        'interface_lang': 'Interface Language',
        'login_header': 'Login',
        'login_btn': 'Log In',
        'password': 'Password',
        'no_account': "Don't have an account?",
        'register_link': 'Register',
        'my_texts': 'My Texts',
        'read': 'Read',
        'main': 'Home',
        'edit_translation': 'Edit translation',
        'confirm_title': 'Confirmation',
        'confirm_delete_text_msg': 'Are you sure you want to delete this text?',
        'btn_delete': 'Delete',
        'btn_cancel': 'Cancel',
        'confirm_title': 'Confirm',
        'confirm_delete_text_msg': 'Delete this text? All progress will be lost.',
        'btn_delete': 'Delete',
        'btn_cancel': 'Cancel',
        'text_deleted': 'Text deleted',
        'word_deleted': 'Word deleted',
        'word_added': 'Word added',
        'undo': 'UNDO',
        'settings_saved': 'Settings saved',
        'error_generic': 'An error occurred',
    }
}

class User(UserMixin):
    def __init__(self, id, email, interface_language='ukr', 
                 library_view_mode='list', library_per_page=20,
                 vocab_view_mode='list', vocab_per_page=20):
        self.id = id
        self.email = email
        self.interface_language = interface_language or 'ukr'
        self.library_view_mode = library_view_mode
        self.library_per_page = library_per_page
        self.vocab_view_mode = vocab_view_mode
        self.vocab_per_page = vocab_per_page

@login_manager.user_loader
def load_user(user_id):
    with get_db() as conn:
        u = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if u:
            keys = u.keys()
            lang = u['interface_language'] if 'interface_language' in keys and u['interface_language'] else 'ukr'
            # Завантажуємо налаштування або дефолтні значення
            lvm = u['library_view_mode'] if 'library_view_mode' in keys and u['library_view_mode'] else 'list'
            lpp = u['library_per_page'] if 'library_per_page' in keys and u['library_per_page'] else 20
            vvm = u['vocab_view_mode'] if 'vocab_view_mode' in keys and u['vocab_view_mode'] else 'list'
            vpp = u['vocab_per_page'] if 'vocab_per_page' in keys and u['vocab_per_page'] else 20
            
            return User(u['id'], u['email'], lang, lvm, lpp, vvm, vpp)
    return None

@app.context_processor
def inject_ui():
    # Визначаємо мову, за замовчуванням 'ukr', якщо користувач не в системі
    lang = 'ukr'
    if current_user.is_authenticated and hasattr(current_user, 'interface_language'):
        lang = current_user.interface_language
    return dict(ui=UI_STRINGS.get(lang, UI_STRINGS['ukr']), lang=lang)

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
            conn.execute('INSERT INTO users (id, email, password_hash, interface_language) VALUES (?, ?, ?, ?)',
                         (uid, email, generate_password_hash(password), 'ukr'))
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
                lang = u['interface_language'] if 'interface_language' in u.keys() and u['interface_language'] else 'ukr'
                login_user(User(u['id'], u['email'], lang))
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

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    next_url = request.args.get('next')
    if request.method == 'POST':
        lang = request.form.get('language')
        if lang in ['ukr', 'eng']:
            with get_db() as conn:
                conn.execute('UPDATE users SET interface_language = ? WHERE id = ?', (lang, current_user.id))
                conn.commit()
            # Оновлюємо об'єкт користувача в сесії
            current_user.interface_language = lang
            flash('Налаштування збережено' if lang == 'ukr' else 'Settings saved')
            if next_url and next_url != url_for('settings'):
                return redirect(next_url)
            return redirect(url_for('index')) # Fallback
    return render_template('settings.html', next_url=next_url)

@app.route('/api/generate', methods=['POST'])
@login_required
def generate():
    req = request.json
    data = services.generate_german_text(req['topic'], req['count'], req['level'])
    title_json = json.dumps({'de': data.get('title_de', req['topic']), 'ukr': data['title_ua'], 'eng': data['title_en']})
    tid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute('INSERT INTO texts (id, user_id, title, level, content_json) VALUES (?,?,?,?,?)',
                     (tid, current_user.id, title_json, req['level'], json.dumps(data['sentences'])))
        conn.commit()
    return jsonify({"id": tid})

@app.route('/api/explain_grammar', methods=['POST'])
@login_required
def explain_grammar():
    req = request.json
    sentence = req.get('sentence')
    text_id = req.get('text_id')
    sentence_index = req.get('sentence_index')
    
    # Отримуємо рівень тексту з бази, щоб адаптувати пояснення
    text_level = "B1" # Default
    if text_id:
        with get_db() as conn:
            t = conn.execute('SELECT level FROM texts WHERE id = ?', (text_id,)).fetchone()
            if t: text_level = t['level']

    lang = current_user.interface_language

    # --- ПЕРЕВІРКА КЕШУ ---
    if text_id and sentence_index is not None:
        with get_db() as conn:
            cached = conn.execute(
                'SELECT explanation FROM grammar_explanations WHERE text_id = ? AND sentence_index = ? AND language = ?',
                (text_id, sentence_index, lang)
            ).fetchone()
            if cached:
                return jsonify({"explanation": cached['explanation']})

    target_lang_name = "Ukrainian" if lang == 'ukr' else "English"

    # --- ЯКЩО В КЕШІ НЕМАЄ, ГЕНЕРУЄМО ---
    prompt = f"""
    Act as a concise German tutor for a {target_lang_name}-speaking student.
    Analyze this German sentence (Level {text_level}): "{sentence}"

    RULES FOR EXPLANATION:
    1. KEEP IT SHORT. Maximum 3-4 bullet points. No long paragraphs. No intro, no Let's start no small talk.
    2. DO NOT define obvious words (e.g., don't say "Computer is a noun").
    3. FOCUS ONLY on grammar nuances relevant to Level {text_level}:
       - Why this specific article/ending? (Case/Gender)
       - Word order (Why is the verb here?)
       - Verb conjugations or tenses.
    4. If the sentence is very simple (A1/A2), just give 1 sentence summary like: "Standard structure: Subject + Verb + Adjective."
    5. Highlight key grammar parts in **bold**.

    Respond in {target_lang_name}.
    """

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        explanation = response.text
        
        # Кешування (якщо текст не змінюється)
        if text_id and sentence_index is not None:
            with get_db() as conn:
                conn.execute('INSERT OR REPLACE INTO grammar_explanations (text_id, sentence_index, language, explanation) VALUES (?, ?, ?, ?)',
                             (text_id, sentence_index, lang, explanation))
                conn.commit()
        
        return jsonify({"explanation": explanation})
    except Exception as e:
        print(f"Grammar error: {e}")
        return jsonify({"error": "Error generating explanation"}), 500
    
@app.route('/library')
@login_required
def library():
    # 1. Отримуємо параметри (пріоритет: URL -> DB -> Default)
    arg_view = request.args.get('view')
    arg_per_page = request.args.get('per_page', type=int)
    
    view_mode = arg_view if arg_view else current_user.library_view_mode
    per_page = arg_per_page if arg_per_page else current_user.library_per_page
    
    # 2. Якщо параметри змінилися, зберігаємо в базу
    if (arg_view and arg_view != current_user.library_view_mode) or (arg_per_page and arg_per_page != current_user.library_per_page):
        with get_db() as conn:
            conn.execute('UPDATE users SET library_view_mode = ?, library_per_page = ? WHERE id = ?', 
                         (view_mode, per_page, current_user.id))
            conn.commit()
        current_user.library_view_mode = view_mode
        current_user.library_per_page = per_page

    page = request.args.get('page', 1, type=int)
    # per_page вже визначено вище
    offset = (page - 1) * per_page

    # Отримуємо всі тексти користувача
    with get_db() as conn:
        total_count = conn.execute('SELECT COUNT(*) FROM texts WHERE user_id = ?', (current_user.id,)).fetchone()[0]
        db_rows = conn.execute('SELECT * FROM texts WHERE user_id = ? ORDER BY rowid DESC LIMIT ? OFFSET ?', (current_user.id, per_page, offset)).fetchall()

    total_pages = math.ceil(total_count / per_page)
    texts = []
    for row in db_rows:
        r = dict(row)
        try:
            # Спробувати розпарсити JSON з заголовком
            titles = json.loads(r['title'])
            # Вибираємо заголовок відповідно до мови інтерфейсу
            # Пріоритет: Мова юзера -> Українська -> Оригінал
            lang_key = current_user.interface_language
            
            r['display_title'] = titles.get('de', r['title'])
            r['trans_title'] = titles.get(lang_key, '')
        except (json.JSONDecodeError, TypeError):
            # Fallback для старих текстів, де title - це просто рядок
            r['display_title'] = r['title']
            r['trans_title'] = ""
        texts.append(r)
        
    return render_template('library.html', texts=texts, page=page, per_page=per_page, total_pages=total_pages, view_mode=view_mode)

@app.route('/view/<tid>')
@login_required
def view_text(tid):
    with get_db() as conn:
        t = conn.execute('SELECT * FROM texts WHERE id = ? AND user_id = ?', (tid, current_user.id)).fetchone()
        if not t: return "404", 404
        vocab_rows = [dict(row) for row in conn.execute('SELECT * FROM vocabulary WHERE user_id = ? AND text_id = ?', (current_user.id, tid)).fetchall()]
        
    sentences = json.loads(t['content_json'])
    
    # Адаптація перекладу під мову юзера
    lang_key = 'ua' if current_user.interface_language == 'ukr' else 'en'
    for s in sentences:
        # Створюємо поле 'trans', яке очікує шаблон, беручи потрібну мову
        s['trans'] = s.get(lang_key, s.get('trans', '')) # Fallback на старий ключ 'trans'

    # Обробка заголовка
    # За замовчуванням показуємо німецьку назву, якщо є, або оригінальний рядок
    display_title = t['title'] 
    trans_title = ""
    try:
        titles = json.loads(t['title'])
        display_title = titles.get('de', titles.get('ukr', t['title'])) # Пріоритет: DE -> UKR -> Raw
        trans_title = titles.get(current_user.interface_language, '')
    except (json.JSONDecodeError, TypeError): pass

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
        
    return render_template('view.html', text=t, sentences=sentences, vocab=vocab_rows, display_title=display_title, trans_title=trans_title)

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
                        (id, user_id, text_id, origin, display, ua, en, ctx, sentence_index, start_index, end_index, level) 
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                     (wid, current_user.id, req.get('tid'), word, 
                      word_data['display'], word_data['ua'], word_data['en'], req['ctx'],
                      sentence_index, start_index, end_index, word_data.get('level') or word_data.get('Level')))
        conn.commit()
    return jsonify({"ok": True})

@app.route('/api/update_word', methods=['POST'])
@login_required
def update_word():
    req = request.json
    wid = req.get('id')
    new_trans = req.get('translation')
    
    if not wid or new_trans is None:
        return jsonify({"error": "Invalid data"}), 400
    if len(new_trans) > 100:
        return jsonify({"error": "Too long"}), 400

    lang = current_user.interface_language
    col = 'ua' if lang == 'ukr' else 'en'
    
    with get_db() as conn:
        # Оновлюємо тільки ту колонку, яка відповідає поточній мові інтерфейсу
        conn.execute(f'UPDATE vocabulary SET {col} = ? WHERE id = ? AND user_id = ?', (new_trans, wid, current_user.id))
        conn.commit()
    return jsonify({"ok": True})

@app.route('/vocab')
@login_required
def vocab():
    lang = current_user.interface_language
    
    arg_view = request.args.get('view')
    arg_per_page = request.args.get('per_page', type=int)
    
    view_mode = arg_view if arg_view else current_user.vocab_view_mode
    per_page = arg_per_page if arg_per_page else current_user.vocab_per_page
    
    if (arg_view and arg_view != current_user.vocab_view_mode) or (arg_per_page and arg_per_page != current_user.vocab_per_page):
        with get_db() as conn:
            conn.execute('UPDATE users SET vocab_view_mode = ?, vocab_per_page = ? WHERE id = ?', 
                         (view_mode, per_page, current_user.id))
            conn.commit()
        current_user.vocab_view_mode = view_mode
        current_user.vocab_per_page = per_page

    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * per_page

    with get_db() as conn:
        total_count = conn.execute('SELECT COUNT(*) FROM vocabulary WHERE user_id = ? AND is_favorite = 1', (current_user.id,)).fetchone()[0]
        db_words = conn.execute('SELECT * FROM vocabulary WHERE user_id = ? AND is_favorite = 1 ORDER BY rowid DESC LIMIT ? OFFSET ?', (current_user.id, per_page, offset)).fetchall()
    
    total_pages = math.ceil(total_count / per_page)
    words = []
    for row in db_words:
        w = dict(row)
        # Додаємо поле display_trans, щоб уникнути подвійного перекладу в шаблоні
        w['display_trans'] = w['ua'] if lang == 'ukr' else w['en']
        words.append(w)
        
    return render_template('vocab.html', words=words, page=page, per_page=per_page, total_pages=total_pages, view_mode=view_mode)

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
        voice = texttospeech.VoiceSelectionParams(language_code="de-DE", name="de-DE-Polyglot-1")
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