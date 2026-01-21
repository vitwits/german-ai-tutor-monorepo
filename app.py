import os
import uuid
import hashlib
import math
import json
import threading
import re
import time
import random
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory, Response, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView, BaseView, expose, helpers
from flask_admin.contrib.sqla import ModelView
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime
from markupsafe import Markup
from flask_cors import CORS

from database import get_db, init_db
import services
import billing

load_dotenv()

# Імпорт твоїх скриптів як модулів
import utils.generate_sentences as gen_sent_script
import utils.generate_audio as gen_audio_script

init_db()

app = Flask(__name__)
CORS(app) # Enable CORS for Capacitor/Mobile clients
# Налаштування SQLAlchemy для Flask-Admin
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.getcwd(), 'data', 'app.db')
# Налаштування для коректного відображення кирилиці в JSON
app.json.ensure_ascii = False 

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-key")
AUDIO_DIR = "data/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

def is_htmx():
    """Check if the request is triggered by HTMX"""
    return request.headers.get('HX-Request') == 'true'

db = SQLAlchemy(app)

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
        'voice': 'Голос',
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
        'text_deleted': 'Текст видалено',
        'word_deleted': 'Слово видалено',
        'word_added': 'Слово додано',
        'undo': 'ВІДМІНИТИ',
        'settings_saved': 'Налаштування збережено',
        'error_generic': 'Сталася помилка',
        'style_label': 'Стиль тексту',
        'style_neutral': 'Нейтральний',
        'style_formal': 'Офіційний',
        'style_conversational': 'Розмовний',
        'style_dialogue_informal': 'Неформальний діалог',
        'style_dialogue_formal': 'Офіційний діалог',
        'speaking_sentences': 'Речення',
        'speaking_small_talk': 'Розмова',
        'speaking_press_start': 'Натисніть Старт',
        'speaking_loading': 'Завантаження...',
        'speaking_cancelled': 'Скасовано. Натисніть ще раз.',
        'speaking_you': 'Ви',
        'speaking_silence': '(Тиша)',
        'speaking_mic_denied': 'Доступ до мікрофону заборонено',
        'speaking_audio_not_supported': 'Запис аудіо не підтримується',
        'speaking_error': 'Помилка: ',
        'score_pronunciation': 'Вимова',
        'score_context': 'Точність',
        'score_grammar': 'Граматика',
        'speaking_noise': '(Шум або нерозбірливо)',
        'quiz_tab': 'Квіз',
        'vocab_tab': 'Словник уроку',
        'check_btn': 'Спробувати',
        'next_btn': 'Далі',
        'done_btn': 'Готово',
        'finish_btn': 'Перевірити',
        'retry_btn': 'Спробувати ще',
        'quiz_completed': 'Квіз завершено!',
        'your_score': 'Твій результат',
        'restart_confirm_title': 'Почати спочатку?',
        'restart_confirm_msg': 'Поточний прогрес буде втрачено. Ви впевнені?',
        'abort_confirm_title': 'Завершити квіз?',
        'abort_confirm_msg': 'Прогрес не буде збережено. Вийти?',
        'abort_btn': 'Завершити',
        'exit_btn': 'Вийти',
        'vocab_words': 'Слова',
        'vocab_sentences': 'Речення',
        'sentence_added_fav': 'Речення додано в улюблені',
        'sentence_removed_fav': 'Речення видалено з улюблених',
        'selection_limited_toast': 'Переклад не більше 4 слів',
        'restart_btn': 'Спочатку',
        'translation_failed_msg': 'Не вдалося отримати переклад',
        'audio_failed_msg': 'Не вдалося згенерувати аудіо',
        'word_exists': 'Слово вже є у словнику',
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
        'voice': 'Voice',
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
        'text_deleted': 'Text deleted',
        'word_deleted': 'Word deleted',
        'word_added': 'Word added',
        'undo': 'UNDO',
        'settings_saved': 'Settings saved',
        'error_generic': 'An error occurred',
        'style_label': 'Text Style',
        'style_neutral': 'Neutral',
        'style_formal': 'Formal',
        'style_conversational': 'Conversational',
        'style_dialogue_informal': 'Informal Dialogue',
        'style_dialogue_formal': 'Formal Dialogue',
        'speaking_sentences': 'Sentences',
        'speaking_small_talk': 'Small Talk',
        'speaking_press_start': 'Press Start to begin',
        'speaking_loading': 'Loading sentences...',
        'speaking_cancelled': 'Cancelled. Tap to try again.',
        'speaking_you': 'You',
        'speaking_silence': '(Silence)',
        'speaking_mic_denied': 'Mic access denied',
        'speaking_audio_not_supported': 'Audio recording not supported',
        'speaking_error': 'Error: ',
        'score_pronunciation': 'Pronunciation',
        'score_context': 'Accuracy',
        'score_grammar': 'Grammar',
        'speaking_noise': '(Noise or unclear)',
        'quiz_tab': 'Quiz',
        'vocab_tab': 'Lesson Vocabulary',
        'check_btn': 'Try',
        'next_btn': 'Next',
        'finish_btn': 'Check',
        'retry_btn': 'Retry',
        'done_btn': 'Done',
        'quiz_completed': 'Quiz Completed!',
        'your_score': 'Your Score',
        'restart_confirm_title': 'Restart Quiz?',
        'restart_confirm_msg': 'Current progress will be lost. Are you sure?',
        'abort_confirm_title': 'Exit Quiz?',
        'abort_confirm_msg': 'Progress will be lost. Exit?',
        'abort_btn': 'Finish',
        'exit_btn': 'Exit',
        'vocab_words': 'Words',
        'vocab_sentences': 'Sentences',
        'sentence_added_fav': 'Sentence added to favorites',
        'sentence_removed_fav': 'Sentence removed from favorites',
        'selection_limited_toast': 'Translation up to 4 words',
        'restart_btn': 'Restart',
        'translation_failed_msg': 'Failed to get translation',
        'audio_failed_msg': 'Failed to generate audio',
        'word_exists': 'Word already in vocabulary',
    }
}

class User(UserMixin):
    def __init__(self, id, email, interface_language='ukr', 
                 library_view_mode='list', library_per_page=20,
                 vocab_view_mode='list', vocab_per_page=20, level='A2', credits=1000.0, is_admin=0):
        self.id = id
        self.email = email
        self.interface_language = interface_language or 'ukr'
        self.library_view_mode = library_view_mode
        self.library_per_page = library_per_page
        self.vocab_view_mode = vocab_view_mode
        self.vocab_per_page = vocab_per_page
        self.level = level
        self.credits = credits
        self.is_admin = is_admin

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
            lvl = u['level'] if 'level' in keys and u['level'] else 'A2'
            crd = u['credits'] if 'credits' in keys and u['credits'] is not None else 1000.0
            is_adm = u['is_admin'] if 'is_admin' in keys and u['is_admin'] else 0
            
            return User(u['id'], u['email'], lang, lvm, lpp, vvm, vpp, lvl, crd, is_adm)
    return None

# --- ADMIN MODELS (SQLAlchemy) ---

class UserModel(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    password_hash = db.Column(db.String, nullable=False)
    interface_language = db.Column(db.String, default='ukr')
    level = db.Column(db.String, default='A2')
    credits = db.Column(db.Float, default=1000.0)
    is_admin = db.Column(db.Integer, default=0)

class SentenceModel(db.Model):
    __tablename__ = 'sentences'
    id = db.Column(db.Integer, primary_key=True)
    text_de = db.Column(db.String)
    text_en = db.Column(db.String)
    text_uk = db.Column(db.String)
    audio_de = db.Column(db.String)
    audio_en = db.Column(db.String)
    audio_uk = db.Column(db.String)
    level = db.Column(db.String)
    topic = db.Column(db.String)
    # quiz_json is handled via raw SQL in migrations, but ideally should be here too if using ORM fully

class SentenceBatch(db.Model):
    __tablename__ = 'sentence_batches'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    level = db.Column(db.String)
    target_count = db.Column(db.Integer)
    processed_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String, default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TempSentence(db.Model):
    __tablename__ = 'temp_sentences'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('sentence_batches.id'))
    de = db.Column(db.String)
    en = db.Column(db.String)
    uk = db.Column(db.String)
    topic = db.Column(db.String)

class TTSLog(db.Model):
    __tablename__ = 'tts_logs'
    id = db.Column(db.Integer, primary_key=True)
    language = db.Column(db.String)
    chars = db.Column(db.Integer)
    source = db.Column(db.String) # 'cache' or 'api'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- ADMIN VIEWS ---

class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', 0):
            return redirect(url_for('login'))
        return super(MyAdminIndexView, self).index()

    @expose('/change_password', methods=['GET', 'POST'])
    def change_password(self):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', 0):
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            new_pass = request.form.get('new_password')
            if new_pass:
                # Оновлюємо через raw SQL для надійності (або через ORM)
                with get_db() as conn:
                    conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                                 (generate_password_hash(new_pass), current_user.id))
                    conn.commit()
                flash('Пароль адміністратора змінено!', 'success')
                return redirect(url_for('admin.index'))
        
        return self.render('admin/change_password.html')

class MyModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and getattr(current_user, 'is_admin', 0)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class SentenceView(MyModelView):
    list_template = 'admin/sentence_list.html'
    column_display_actions = False
    # Новий порядок колонок
    column_list = ['play', 'text_uk', 'text_en', 'text_de', 'id', 'level', 'topic', 'actions']
    column_labels = {
        'play': 'Play', 
        'text_uk': 'Ukrainian', 
        'text_en': 'English',
        'text_de': 'German', 
        'id': 'ID',
        'level': 'Level',
        'topic': 'Topic',
        'actions': 'Actions'
    }
    column_searchable_list = ['text_de', 'text_uk', 'topic']
    column_filters = ['level', 'topic']
    page_size = 50
    can_set_page_size = True
    # Вказуємо, які колонки можна сортувати
    column_sortable_list = ['id', 'level', 'topic', 'text_de', 'text_uk', 'text_en']

    def _actions_formatter(view, context, model, name):
        edit_url = url_for('.edit_view', id=model.id)
        delete_url = url_for('.delete_view', id=model.id)
        
        actions_html = f"""
            <div style="display: flex; gap: 8px; align-items: center; justify-content: center;">
                <a href="{edit_url}" class="btn btn-primary action-btn" title="Edit">
                    <span class="material-symbols-outlined" style="font-size: 18px;">edit</span>
                </a>
                <a href="{delete_url}" class="btn btn-danger action-btn" title="Delete">
                    <span class="material-symbols-outlined" style="font-size: 18px;">delete</span>
                </a>
            </div>
        """
        return Markup(actions_html)

    def _play_formatter(view, context, model, name):
        # Формуємо список URL для JS
        urls = [model.audio_uk, model.audio_en, model.audio_de]
        # Екрануємо лапки
        js_args = ", ".join([f"'{u}'" for u in urls if u])
        return Markup(
            f'''<button class="play-btn" onclick="playSequence(this, [{js_args}])">▶</button>'''
        )

    column_formatters = {
        'play': _play_formatter,
        'actions': _actions_formatter
    }

    def after_model_delete(self, model):
        # Видалення файлів після видалення запису з БД
        base_static = os.path.join(app.root_path, 'static', 'audio', 'sentences')
        for path in [model.audio_de, model.audio_en, model.audio_uk]:
            if path:
                full_path = os.path.join(base_static, path)
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        print(f"Deleted file: {full_path}")
                    except Exception as e:
                        print(f"Error deleting file {full_path}: {e}")

class GenerateSentencesView(BaseView):
    @expose('/')
    def index(self):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', 0):
            return redirect(url_for('login'))
        batches = SentenceBatch.query.order_by(SentenceBatch.created_at.desc()).all()
        return self.render('admin/gen_sentences.html', batches=batches)

    @expose('/start_text_gen', methods=['POST'])
    def start_text_gen(self):
        level = request.form.get('level')
        count = int(request.form.get('count', 10))
        
        name = f"{datetime.now().strftime('%d-%H-%M-%S')}_{level}_{count}"
        batch = SentenceBatch(name=name, level=level, target_count=count, status='generating_text')
        db.session.add(batch)
        db.session.commit()
        
        thread = threading.Thread(target=background_text_gen, args=(app, batch.id, level, count))
        thread.start()
        
        return redirect(url_for('.index'))

    @expose('/batch/<int:batch_id>/edit')
    def edit_batch(self, batch_id):
        batch = SentenceBatch.query.get_or_404(batch_id)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        pagination = TempSentence.query.filter_by(batch_id=batch_id).paginate(page=page, per_page=per_page)
        return self.render('admin/batch_edit.html', batch=batch, pagination=pagination, per_page=per_page)
    
    @expose('/batch/<int:batch_id>/delete', methods=['POST'])
    def delete_batch(self, batch_id):
        batch = SentenceBatch.query.get_or_404(batch_id)
        TempSentence.query.filter_by(batch_id=batch_id).delete()
        db.session.delete(batch)
        db.session.commit()
        return redirect(url_for('.index'))

    @expose('/batch/<int:batch_id>/apply', methods=['POST'])
    def apply_batch(self, batch_id):
        batch = SentenceBatch.query.get_or_404(batch_id)
        batch.status = 'generating_audio'
        batch.processed_count = 0
        db.session.commit()
        
        thread = threading.Thread(target=background_audio_gen, args=(app, batch.id))
        thread.start()
        
        return redirect(url_for('.index'))

    @expose('/api/batch_status/<int:batch_id>')
    def batch_status(self, batch_id):
        batch = SentenceBatch.query.get(batch_id)
        if not batch: return jsonify({'error': 'Not found'}), 404
        return jsonify({
            'status': batch.status,
            'processed': batch.processed_count,
            'total': batch.target_count
        })
    
    @expose('/api/update_temp_sentence', methods=['POST'])
    def update_temp_sentence(self):
        data = request.json
        ts = TempSentence.query.get(data.get('id'))
        if ts:
            field = data.get('field')
            val = data.get('value')
            if field == 'de': ts.de = val
            elif field == 'en': ts.en = val
            elif field == 'uk': ts.uk = val
            db.session.commit()
            return jsonify({'ok': True})
        return jsonify({'error': 'Not found'}), 404

    @expose('/api/delete_temp_sentence', methods=['POST'])
    def delete_temp_sentence(self):
        data = request.json
        ts = TempSentence.query.get(data.get('id'))
        if ts:
            db.session.delete(ts)
            db.session.commit()
            return jsonify({'ok': True})
        return jsonify({'error': 'Not found'}), 404

class CachingStatsView(BaseView):
    @expose('/')
    def index(self):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', 0):
            return redirect(url_for('login'))
            
        period = request.args.get('period', 'all')
        
        query = db.session.query(
            TTSLog.language,
            TTSLog.source,
            func.count(TTSLog.id),
            func.sum(TTSLog.chars)
        )
        
        if period == 'today':
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(TTSLog.created_at >= start_date)
        elif period == 'month':
            today = datetime.utcnow()
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(TTSLog.created_at >= start_date)
            
        rows = query.group_by(TTSLog.language, TTSLog.source).all()
        
        stats_map = {}
        for lang, source, count, chars in rows:
            if lang not in stats_map:
                stats_map[lang] = {'api_req': 0, 'api_chars': 0, 'cache_req': 0, 'cache_chars': 0}
            
            c_val = int(chars) if chars else 0
            if source == 'api':
                stats_map[lang]['api_req'] += count
                stats_map[lang]['api_chars'] += c_val
            else:
                stats_map[lang]['cache_req'] += count
                stats_map[lang]['cache_chars'] += c_val
        
        data = []
        grand = {'api_req': 0, 'api_chars': 0, 'cache_req': 0, 'cache_chars': 0, 'total_req': 0, 'total_chars': 0}
        
        lang_map = {'de': 'German', 'en': 'English', 'uk': 'Ukrainian'}
        
        for lang in ['de', 'en', 'uk']:
            s = stats_map.get(lang, {'api_req': 0, 'api_chars': 0, 'cache_req': 0, 'cache_chars': 0})
            
            total_req = s['api_req'] + s['cache_req']
            total_chars = s['api_chars'] + s['cache_chars']
            pct = 0
            if total_req > 0:
                pct = round((s['cache_req'] / total_req) * 100, 1)
            
            data.append({
                'lang_code': lang,
                'lang_name': lang_map.get(lang, lang.upper()),
                'api_req': s['api_req'],
                'api_chars': s['api_chars'],
                'cache_req': s['cache_req'],
                'cache_chars': s['cache_chars'],
                'total_req': total_req,
                'total_chars': total_chars,
                'pct': pct
            })
            
            grand['api_req'] += s['api_req']
            grand['api_chars'] += s['api_chars']
            grand['cache_req'] += s['cache_req']
            grand['cache_chars'] += s['cache_chars']
            grand['total_req'] += total_req
            grand['total_chars'] += total_chars
            
        grand_pct = 0
        if grand['total_req'] > 0:
            grand_pct = round((grand['cache_req'] / grand['total_req']) * 100, 1)
            
        return self.render('admin/caching_stats.html', stats=data, grand=grand, grand_pct=grand_pct, period=period)

# --- BACKGROUND TASKS ---

def background_text_gen(app_instance, batch_id, level, count):
    with app_instance.app_context():
        try:
            generated = 0
            # Використовуємо логіку вибору тем з твого скрипта
            available_topics = gen_sent_script.LEVEL_RULES.get(level, gen_sent_script.A2_TOPICS)

            while generated < count:
                chunk_size = min(20, count - generated)
                
                # Вибір тем як у твоєму скрипті
                if len(available_topics) >= chunk_size:
                    batch_topics = random.sample(available_topics, chunk_size)
                else:
                    batch_topics = random.choices(available_topics, k=chunk_size)
                
                # ВИКЛИК ТВОГО СКРИПТА
                sentences = gen_sent_script.generate_batch(level, chunk_size, batch_topics)
                
                for s in sentences:
                    ts = TempSentence(
                        batch_id=batch_id,
                        de=s.get('de'),
                        en=s.get('en'),
                        uk=s.get('uk') or s.get('ua'),
                        topic=s.get('topic', '')
                    )
                    db.session.add(ts)
                
                generated += len(sentences)
                batch = SentenceBatch.query.get(batch_id)
                batch.processed_count = generated
                db.session.commit()
                
            batch = SentenceBatch.query.get(batch_id)
            batch.status = 'text_ready'
            db.session.commit()
        except Exception as e:
            print(f"BG Text Error: {e}")
            batch = SentenceBatch.query.get(batch_id)
            batch.status = 'error'
            db.session.commit()

def background_audio_gen(app_instance, batch_id):
    with app_instance.app_context():
        try:
            batch = SentenceBatch.query.get(batch_id)
            sentences = TempSentence.query.filter_by(batch_id=batch_id).all()
            batch.target_count = len(sentences)
            
            last_sent = SentenceModel.query.order_by(SentenceModel.id.desc()).first()
            start_id = (last_sent.id if last_sent else 0) + 1
            
            base_static = os.path.join(app_instance.root_path, 'static', 'audio', 'sentences')
            
            for i, s in enumerate(sentences):
                current_id = start_id + i
                file_prefix = f"{current_id:04d}"
                rel_folder = batch.level.lower()
                
                path_de = f"{rel_folder}/{file_prefix}_de.ogg"
                path_en = f"{rel_folder}/{file_prefix}_en.ogg"
                path_uk = f"{rel_folder}/{file_prefix}_uk.ogg"
                
                # ВИКЛИК ТВОГО СКРИПТА
                gen_audio_script.generate_file(s.de, 'de', os.path.join(base_static, path_de))
                gen_audio_script.generate_file(s.en, 'en', os.path.join(base_static, path_en))
                gen_audio_script.generate_file(s.uk, 'uk', os.path.join(base_static, path_uk))
                
                new_sent = SentenceModel(id=current_id, text_de=s.de, text_en=s.en, text_uk=s.uk, audio_de=path_de, audio_en=path_en, audio_uk=path_uk, level=batch.level, topic=s.topic)
                db.session.add(new_sent)
                
                batch.processed_count = i + 1
                if i % 5 == 0: db.session.commit()
            
            TempSentence.query.filter_by(batch_id=batch_id).delete()
            db.session.delete(batch)
            db.session.commit()
        except Exception as e:
            print(f"BG Audio Error: {e}")
            batch = SentenceBatch.query.get(batch_id)
            batch.status = 'error'
            db.session.commit()

# Ініціалізація Адмінки
admin = Admin(app, name='DE Tutor Admin', index_view=MyAdminIndexView())
admin.add_view(MyModelView(UserModel, db.session, name='Users'))
admin.add_view(SentenceView(SentenceModel, db.session, name='Sentences'))
admin.add_view(GenerateSentencesView(name='Generate Sentences', endpoint='generate'))
admin.add_view(CachingStatsView(name='Caching', endpoint='caching'))

# Створення адміна при запуску
def create_admin_user():
    with app.app_context():
        # Перевіряємо чи існує адмін
        admin_email = "admin@admin.com"
        existing = UserModel.query.filter_by(email=admin_email).first()
        if not existing:
            print("Creating admin user...")
            uid = str(uuid.uuid4())
            # Пароль за замовчуванням: admin
            new_admin = UserModel(
                id=uid,
                email=admin_email,
                password_hash=generate_password_hash("admin"),
                is_admin=1,
                level='C2'
            )
            db.session.add(new_admin)
            db.session.commit()
            print(f"Admin created: {admin_email} / admin")
        else:
            # Переконуємось, що він має права адміна
            if existing.is_admin != 1:
                existing.is_admin = 1
                db.session.commit()

# Викликаємо створення адміна одразу при ініціалізації, щоб працювало і з 'flask run'
with app.app_context():
    create_admin_user()

@app.context_processor
def inject_ui():
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
            conn.execute('INSERT INTO users (id, email, password_hash, interface_language, level, credits) VALUES (?, ?, ?, ?, ?, ?)',
                         (uid, email, generate_password_hash(password), 'ukr', 'A2', 1000.0))
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
                login_user(load_user(u['id'])) # Використовуємо load_user для повного завантаження полів
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

@app.route('/api/update_level', methods=['POST'])
@login_required
def update_level():
    data = request.get_json(silent=True) or request.form
    new_level = data.get('level')
    if new_level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
        with get_db() as conn:
            conn.execute('UPDATE users SET level = ? WHERE id = ?', (new_level, current_user.id))
            conn.commit()
        current_user.level = new_level
        
        if is_htmx():
            return render_template('partials/level_tiles.html')
        return jsonify({"ok": True})
    return jsonify({"error": "Invalid level"}), 400

@app.route('/api/generate', methods=['POST'])
@login_required
def generate():
    # Support both JSON and Form Data
    req = request.json if request.is_json else request.form
    
    topic = req.get('topic')
    level = req.get('level', current_user.level)
    style = req.get('style', 'neutral')
    
    # Logic to determine count based on size (S/M/L) if 'count' is not provided directly
    count = req.get('count')
    if not count:
        size = req.get('size', 'M')
        # Map: Level -> Size -> Count
        sentence_map = {
            'A1': {'S': 5, 'M': 8, 'L': 12},
            'A2': {'S': 6, 'M': 8, 'L': 11},
            'B1': {'S': 5, 'M': 7, 'L': 10},
            'B2': {'S': 5, 'M': 7, 'L': 10},
            'C1': {'S': 6, 'M': 8, 'L': 9},
            'C2': {'S': 6, 'M': 7, 'L': 8}
        }
        # Fallback to A2/M if something is wrong
        count = sentence_map.get(level, sentence_map['A2']).get(size, 8)
    else:
        count = int(count)
    
    # BILLING: Списання за генерацію уроку
    new_bal = billing.deduct_credits(current_user.id, billing.PRICING['lesson_generation'])
    current_user.credits = new_bal # Оновлюємо сесію

    # Передаємо параметр style
    data = services.generate_german_text(topic, count, level, style)
    
    title_json = json.dumps({'de': data.get('title_de', topic), 'ukr': data['title_ua'], 'eng': data['title_en']})
    tid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute('INSERT INTO texts (id, user_id, title, level, content_json, quiz_json) VALUES (?,?,?,?,?,?)',
                     (tid, current_user.id, title_json, level, json.dumps(data['sentences']), json.dumps(data.get('quiz', []))))
        conn.commit()
        
    if is_htmx():
        resp = Response()
        resp.headers['HX-Redirect'] = f'/view/{tid}'
        return resp
        
    return jsonify({"id": tid, "credits": new_bal})

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

    # --- ФОРМУВАННЯ ПРОМПТА ТУТ, А ВИКЛИК ЧЕРЕЗ СЕРВІС ---
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

    # Викликаємо функцію з services
    explanation = services.explain_grammar_text(prompt)
    
    if explanation:
        # Кешування
        if text_id and sentence_index is not None:
            with get_db() as conn:
                conn.execute('INSERT OR REPLACE INTO grammar_explanations (text_id, sentence_index, language, explanation) VALUES (?, ?, ?, ?)',
                             (text_id, sentence_index, lang, explanation))
                conn.commit()
        
        # BILLING
        new_bal = billing.deduct_credits(current_user.id, billing.PRICING['grammar_explanation'])
        current_user.credits = new_bal
        
        return jsonify({"explanation": explanation, "credits": new_bal})
    else:
        return jsonify({"error": "Error generating explanation"}), 500
    
@app.route('/library')
@login_required
def library():
    # Фіксовані налаштування вигляду
    view_mode = 'grid'
    per_page = 18
    
    # Фільтри
    show_fav = request.args.get('fav') == '1'
    levels_arg = request.args.get('levels')
    selected_levels = levels_arg.split(',') if levels_arg else []
    # Валідація рівнів
    valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    selected_levels = [l for l in selected_levels if l in valid_levels]
    
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * per_page

    query_base = 'FROM texts WHERE user_id = ?'
    params = [current_user.id]

    if show_fav:
        query_base += ' AND is_favorite = 1'

    if selected_levels:
        placeholders = ','.join(['?'] * len(selected_levels))
        query_base += f' AND level IN ({placeholders})'
        params.extend(selected_levels)

    query_count = f'SELECT COUNT(*) {query_base}'
    query_rows = f'SELECT * {query_base} ORDER BY rowid DESC LIMIT ? OFFSET ?'
    
    with get_db() as conn:
        total_count = conn.execute(query_count, params).fetchone()[0]
        # params дублюються для count і rows, але для rows треба додати limit/offset
        db_rows = conn.execute(query_rows, params + [per_page, offset]).fetchall()

    total_pages = math.ceil(total_count / per_page)
    texts = []
    for row in db_rows:
        r = dict(row)
        try:
            titles = json.loads(r['title'])
            lang_key = current_user.interface_language
            
            r['display_title'] = titles.get('de', r['title'])
            r['trans_title'] = titles.get(lang_key, '')
        except (json.JSONDecodeError, TypeError):
            r['display_title'] = r['title']
            r['trans_title'] = ""
        texts.append(r)
        
    if is_htmx() and request.headers.get('HX-Target') == 'library-container':
        return render_template('partials/library_list.html', texts=texts, page=page, per_page=per_page, total_pages=total_pages, view_mode=view_mode, show_fav=show_fav, selected_levels=selected_levels)

    return render_template('library.html', texts=texts, page=page, per_page=per_page, total_pages=total_pages, view_mode=view_mode, show_fav=show_fav, selected_levels=selected_levels)

@app.route('/view/<tid>')
@login_required
def view_text(tid):
    with get_db() as conn:
        t = conn.execute('SELECT * FROM texts WHERE id = ? AND user_id = ?', (tid, current_user.id)).fetchone()
        if not t: return "404", 404
        
        # Оновлений запит: перевіряємо, чи є слово улюбленим ГЛОБАЛЬНО (в будь-якому тексті)
        # Це дозволяє підсвічувати зірочку, навіть якщо в цьому конкретному тексті is_favorite=0
        vocab_query = '''
            SELECT v.*, 
                   (SELECT COUNT(*) FROM vocabulary v2 WHERE v2.user_id = v.user_id AND v2.display = v.display AND v2.is_favorite = 1) > 0 as is_global_fav
            FROM vocabulary v 
            WHERE v.user_id = ? AND v.text_id = ?
        '''
        vocab_rows = [dict(row) for row in conn.execute(vocab_query, (current_user.id, tid)).fetchall()]
        
        # Переписуємо локальний is_favorite на глобальний для коректного відображення в шаблоні
        for v in vocab_rows:
            v['is_favorite'] = 1 if v['is_global_fav'] else 0
        
        # Pre-fetch grammar cache indices
        grammar_indices = set()
        g_rows = conn.execute('SELECT sentence_index FROM grammar_explanations WHERE text_id = ? AND language = ?', (tid, current_user.interface_language)).fetchall()
        for r in g_rows:
            grammar_indices.add(r['sentence_index'])
        
    sentences = json.loads(t['content_json'])
    
    lang_key = 'ua' if current_user.interface_language == 'ukr' else 'en'
    for s in sentences:
        s['trans'] = s.get(lang_key, s.get('trans', ''))

    display_title = t['title'] 
    trans_title = ""
    try:
        titles = json.loads(t['title'])
        display_title = titles.get('de', titles.get('ukr', t['title']))
        trans_title = titles.get(current_user.interface_language, '')
    except (json.JSONDecodeError, TypeError): pass

    for i, s in enumerate(sentences):
        original_text = s['de']
        
        s['has_grammar'] = i in grammar_indices
        
        my_words = [v for v in vocab_rows if v['sentence_index'] == i]
        my_words.sort(key=lambda x: x.get('start_index') or 0, reverse=True)
        
        last_idx = len(original_text)
        built_str = ""
        
        for w in my_words:
            start = w['start_index']
            end = w['end_index']
            
            if start is not None and start >= 0 and end <= len(original_text):
                built_str = original_text[end:last_idx] + built_str
                word_val = original_text[start:end]
                built_str = f'<span class="learned" data-wid="{w["id"]}">{word_val}</span>' + built_str
                last_idx = start
        
        built_str = original_text[0:last_idx] + built_str
        s['de_html'] = built_str
        
    # Load Quiz Data
    quiz_data = []
    if t['quiz_json']:
        try:
            quiz_data = json.loads(t['quiz_json'])
        except: pass
        
    # Load last quiz result
    last_quiz_result = None
    res = conn.execute(
        'SELECT score, total_questions FROM quiz_results WHERE user_id = ? AND text_id = ? ORDER BY created_at DESC LIMIT 1',
        (current_user.id, tid)
    ).fetchone()
    if res:
        last_quiz_result = dict(res)
        
    return render_template('view.html', text=t, sentences=sentences, vocab=vocab_rows, display_title=display_title, trans_title=trans_title, quiz_data=quiz_data, last_quiz_result=last_quiz_result)

@app.route('/api/save_quiz_result', methods=['POST'])
@login_required
def save_quiz_result():
    req = request.json
    with get_db() as conn:
        # Перевіряємо, чи є вже результат для цього тексту
        cur = conn.execute('SELECT id FROM quiz_results WHERE user_id = ? AND text_id = ?', (current_user.id, req['text_id']))
        row = cur.fetchone()
        
        if row:
            conn.execute('UPDATE quiz_results SET score = ?, total_questions = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?',
                         (req['score'], req['total'], row['id']))
        else:
            conn.execute('INSERT INTO quiz_results (user_id, text_id, score, total_questions) VALUES (?, ?, ?, ?)',
                         (current_user.id, req['text_id'], req['score'], req['total']))
        conn.commit()
    return jsonify({"ok": True})

@app.route('/api/quick_translate', methods=['POST'])
@login_required
def quick_translate():
    req = request.json
    original_text = req.get('text', '').strip()
    text_id = req.get('tid')
    start_char_index = req.get('start_char_index') # Get the new field

    if not original_text:
        return jsonify({"error": "Empty text"}), 400

    words = original_text.split()
    if len(words) > 4:
        # Повертаємо контрольовану помилку з ключем для UI, щоб фронтенд показав правильний тост
        return jsonify({"ok": False, "error_key": "selection_limited_toast"})
        
    # DUPLICATE CHECK 1: Check by exact selection (origin) to save resources
    with get_db() as conn:
        dup = conn.execute('SELECT 1 FROM vocabulary WHERE user_id = ? AND text_id = ? AND origin = ?', (current_user.id, text_id, original_text)).fetchone()
        if dup:
            return jsonify({"ok": False, "error_key": "word_exists"})

    text_for_translation = original_text
    
    # REUSE LOGIC: Check if user has this word elsewhere to reuse translation
    word_data = None
    with get_db() as conn:
        # Prioritize favorite entries (is_favorite DESC), then most recent
        existing = conn.execute('SELECT display, ua, en, level, is_favorite FROM vocabulary WHERE user_id = ? AND origin = ? ORDER BY is_favorite DESC, rowid DESC LIMIT 1', (current_user.id, original_text)).fetchone()
        if existing:
            word_data = {
                'display': existing['display'],
                'ua': existing['ua'],
                'en': existing['en'],
                'level': existing['level']
            }

    # 1. Translate (if not reused)
    if not word_data:
        word_data = services.translate_word(text_for_translation, req['ctx'])
    
    # Validate Translation
    if not word_data or word_data.get('ua') == 'Error' or word_data.get('en') == 'Error':
        return jsonify({"ok": False, "error_key": "translation_failed"}), 500
        
    # --- NEW: Видалення дублікатів з перекладу (наприклад, "моя, моя, моє") ---
    def remove_duplicate_parts(translation_string):
        if not translation_string:
            return ""
        # Розділяємо рядок, прибираємо зайві пробіли
        parts = [part.strip() for part in translation_string.split(',')]
        parts = [p for p in parts if p]
        
        # 1. Прибираємо точні дублікати
        unique_list = []
        seen = set()
        for p in parts:
            if p not in seen:
                unique_list.append(p)
                seen.add(p)
        
        # 2. Логіка: якщо перше слово співпадає, залишаємо довший варіант
        final_parts = []
        for i, p_a in enumerate(unique_list):
            words_a = p_a.split()
            if not words_a: continue
            first_a = words_a[0].lower()
            
            is_redundant = False
            for j, p_b in enumerate(unique_list):
                if i == j: continue
                words_b = p_b.split()
                if not words_b: continue
                
                if words_b[0].lower() == first_a and len(words_b) > len(words_a):
                    is_redundant = True
                    break
            
            if not is_redundant:
                final_parts.append(p_a)
                
        return ', '.join(final_parts)

    word_data['ua'] = remove_duplicate_parts(word_data.get('ua'))
    word_data['en'] = remove_duplicate_parts(word_data.get('en'))

    # DUPLICATE CHECK 2: Check by canonical form (display) after translation
    with get_db() as conn:
        dup_display = conn.execute('SELECT 1 FROM vocabulary WHERE user_id = ? AND text_id = ? AND display = ?', (current_user.id, text_id, word_data['display'])).fetchone()
        if dup_display:
            return jsonify({"ok": False, "error_key": "word_exists"})

    # 2. Generate Audio (German)
    if not get_cached_or_generate_tts(text_for_translation, 'de'):
        return jsonify({"ok": False, "error_key": "audio_failed"}), 500

    # 3. Generate Audio (Translation)
    target_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
    trans_text = word_data.get('ua') if target_lang == 'uk' else word_data.get('en')
    
    if trans_text:
        parts = [p.strip() for p in re.split(r'[,;]', trans_text) if p.strip()]
        for part in parts:
            if not get_cached_or_generate_tts(part, target_lang):
                return jsonify({"ok": False, "error_key": "audio_failed"}), 500

    # BILLING (Translation cost)
    cost = billing.calculate_translation_cost(text_for_translation)
    new_bal = billing.deduct_credits(current_user.id, cost)
    current_user.credits = new_bal

    wid = str(uuid.uuid4())
    
    full_sentence = req['ctx']
    word_to_store_and_highlight = text_for_translation # Використовуємо валідний текст
    
    # --- REVISED INDEXING LOGIC ---
    start_index = -1
    if start_char_index is not None:
        # Search for the word starting from the index provided by the frontend.
        # This is much more reliable. We search from a bit before the reported index
        # to account for any minor discrepancies in whitespace handling between JS and Python.
        search_start = max(0, start_char_index - 5)
        start_index = full_sentence.find(word_to_store_and_highlight, search_start)

    # Fallback to the old (less reliable) method if the new one fails for any reason
    if start_index == -1:
        start_index = full_sentence.find(word_to_store_and_highlight)
    
    end_index = start_index + len(word_to_store_and_highlight) if start_index != -1 else -1
    sentence_index = req.get('sent_idx', 0)
    
    with get_db() as conn:
        conn.execute('''INSERT INTO vocabulary 
                        (id, user_id, text_id, origin, display, ua, en, ctx, sentence_index, start_index, end_index, level) 
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                     (wid, current_user.id, req.get('tid'), word_to_store_and_highlight,
                      word_data['display'], word_data['ua'], word_data['en'], req['ctx'],
                      sentence_index, start_index, end_index, word_data.get('level') or word_data.get('Level')))
        conn.commit()
    return jsonify({"ok": True, "credits": new_bal})

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
        conn.execute(f'UPDATE vocabulary SET {col} = ? WHERE id = ? AND user_id = ?', (new_trans, wid, current_user.id))
        conn.commit()
    return jsonify({"ok": True})

@app.route('/vocab')
@login_required
def vocab():
    lang = current_user.interface_language
    
    # Tab switching: words vs sentences
    mode = request.args.get('mode', 'words')
    
    # --- SENTENCES MODE ---
    if mode == 'sentences':
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        query_count = '''
            SELECT COUNT(*) FROM user_favorite_sentences 
            WHERE user_id = ?
        '''
        query_rows = '''
            SELECT s.*, ufs.id as fav_id, ufs.created_at 
            FROM user_favorite_sentences ufs
            JOIN sentences s ON ufs.sentence_id = s.id
            WHERE ufs.user_id = ?
            ORDER BY ufs.created_at DESC
            LIMIT ? OFFSET ?
        '''
        
        with get_db() as conn:
            total_count = conn.execute(query_count, (current_user.id,)).fetchone()[0]
            rows = conn.execute(query_rows, (current_user.id, per_page, offset)).fetchall()
            
        sentences = []
        lang_key = 'text_uk' if lang == 'ukr' else 'text_en'
        audio_key = 'audio_uk' if lang == 'ukr' else 'audio_en'
        
        for r in rows:
            s = dict(r)
            s['display_trans'] = s.get(lang_key) or s.get('text_en')
            s['display_audio'] = s.get(audio_key)
            sentences.append(s)
            
        total_pages = math.ceil(total_count / per_page)
        
        # Для запитів пагінації повертаємо лише частковий шаблон.
        if is_htmx() and request.headers.get('HX-Target') == 'vocab-container':
            return render_template('partials/fav_sentences_list.html', sentences=sentences, page=page, total_pages=total_pages)
        
        # Для повного завантаження або перемикання вкладок повертаємо повний шаблон.
        return render_template('vocab.html', mode='sentences', sentences=sentences, page=page, total_pages=total_pages)

    # --- WORDS MODE (Existing Logic) ---
    arg_view = request.args.get('view')
    
    view_mode = arg_view if arg_view else current_user.vocab_view_mode
    per_page = 36 # Фіксована кількість, як ви просили раніше
    
    if arg_view and arg_view != current_user.vocab_view_mode:
        with get_db() as conn:
            conn.execute('UPDATE users SET vocab_view_mode = ? WHERE id = ?', (view_mode, current_user.id))
            conn.commit()
        current_user.vocab_view_mode = view_mode

    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * per_page
    
    # Search logic
    q = request.args.get('q', '').strip()
    
    # --- Level Filter Logic ---
    levels_arg = request.args.get('levels')
    selected_levels = levels_arg.split(',') if levels_arg else []
    valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    selected_levels = [l for l in selected_levels if l in valid_levels]
    
    query_base = 'FROM vocabulary WHERE user_id = ? AND is_favorite = 1'
    params = [current_user.id]
    
    if q:
        query_base += ' AND (display LIKE ? OR ua LIKE ? OR en LIKE ?)'
        search_term = f'%{q}%'
        params.extend([search_term, search_term, search_term])
    
    if selected_levels:
        placeholders = ','.join(['?'] * len(selected_levels))
        query_base += f' AND level IN ({placeholders})'
        params.extend(selected_levels)
        
    query_count = f'SELECT COUNT(*) {query_base}'
    query_rows = f'SELECT * {query_base} ORDER BY rowid DESC LIMIT ? OFFSET ?'

    with get_db() as conn:
        total_count = conn.execute(query_count, params).fetchone()[0]
        db_words = conn.execute(query_rows, params + [per_page, offset]).fetchall()
    
    total_pages = math.ceil(total_count / per_page)
    words = []
    for row in db_words:
        w = dict(row)
        w['display_trans'] = w['ua'] if lang == 'ukr' else w['en']
        words.append(w)
        
    if is_htmx() and request.headers.get('HX-Target') == 'vocab-container':
        return render_template('partials/vocab_list.html', words=words, page=page, per_page=per_page, total_pages=total_pages, view_mode=view_mode, q=q, selected_levels=selected_levels, mode=mode)
        
    return render_template('vocab.html', mode='words', words=words, page=page, per_page=per_page, total_pages=total_pages, view_mode=view_mode, q=q, selected_levels=selected_levels)

@app.route('/api/toggle_fav', methods=['POST'])
@login_required
def toggle_fav():
    req = request.json
    wid = req['id']
    with get_db() as conn:
        # 1. Отримуємо display слова, яке клікнули
        target = conn.execute('SELECT display FROM vocabulary WHERE id = ?', (wid,)).fetchone()
        if not target: return jsonify({"ok": False})
        
        display_val = target['display']
        
        # 2. Перевіряємо, чи є вже улюблені слова з таким display (глобально)
        existing_fav = conn.execute('SELECT 1 FROM vocabulary WHERE user_id = ? AND display = ? AND is_favorite = 1', (current_user.id, display_val)).fetchone()
        
        if existing_fav:
            # Якщо Є -> Вимикаємо ВСІ (щоб прибрати з улюблених або підготувати до перемикання)
            conn.execute('UPDATE vocabulary SET is_favorite = 0 WHERE user_id = ? AND display = ?', (current_user.id, display_val))
        else:
            # Якщо НЕМАЄ -> Вмикаємо ТІЛЬКИ ЦЕЙ (щоб зберегти саме цей контекст)
            conn.execute('UPDATE vocabulary SET is_favorite = 1 WHERE id = ?', (wid,))
            
        conn.commit()
    return jsonify({"ok": True})

@app.route('/api/remove_word', methods=['POST'])
@login_required
def remove_word():
    req = request.json if request.is_json else request.form
    wid = req.get('id')
    # Handle boolean from JSON or string from Form
    from_vocab = req.get('from_vocab')
    if isinstance(from_vocab, str):
        from_vocab = from_vocab.lower() == 'true'
    
    with get_db() as conn:
        if from_vocab:
            conn.execute('UPDATE vocabulary SET is_favorite = 0 WHERE id = ? AND user_id = ?', (wid, current_user.id))
            conn.execute('DELETE FROM vocabulary WHERE id = ? AND is_favorite = 0 AND text_id IS NULL', (wid,))
        else:
            word = conn.execute('SELECT is_favorite FROM vocabulary WHERE id = ?', (wid,)).fetchone()
            if word and word['is_favorite'] == 1:
                conn.execute('UPDATE vocabulary SET text_id = NULL WHERE id = ? AND user_id = ?', (wid, current_user.id))
            else:
                conn.execute('DELETE FROM vocabulary WHERE id = ? AND user_id = ?', (wid, current_user.id))
        
        conn.commit()
        
    if is_htmx():
        return "" # Return empty string to remove element from DOM
        
    return jsonify({"ok": True})

@app.route('/api/toggle_text_fav', methods=['POST'])
@login_required
def toggle_text_fav():
    tid = request.json.get('id')
    with get_db() as conn:
        conn.execute('UPDATE texts SET is_favorite = 1 - COALESCE(is_favorite, 0) WHERE id = ? AND user_id = ?', (tid, current_user.id))
        conn.commit()
    return jsonify({"ok": True})

@app.route('/api/delete_text', methods=['POST'])
@login_required
def delete_text():
    # Support both JSON (fetch) and Form Data (HTMX)
    tid = request.json.get('id') if request.is_json else request.form.get('id')
    
    with get_db() as conn:
        conn.execute('DELETE FROM texts WHERE id = ? AND user_id = ?', (tid, current_user.id))
        conn.execute('UPDATE vocabulary SET text_id = NULL WHERE text_id = ? AND user_id = ? AND is_favorite = 1', (tid, current_user.id))
        conn.execute('DELETE FROM vocabulary WHERE text_id = ? AND user_id = ? AND is_favorite = 0', (tid, current_user.id))
        conn.execute('DELETE FROM grammar_explanations WHERE text_id = ?', (tid,))
        conn.commit()
        
    if is_htmx():
        return "" # Return empty string to remove element from DOM
        
    return jsonify({"ok": True})

@app.route('/api/toggle_sentence_fav', methods=['POST'])
@login_required
def toggle_sentence_fav():
    sid = request.form.get('id')
    if not sid: return jsonify({"error": "No ID"}), 400
    
    msg = ""
    is_fav = False
    
    with get_db() as conn:
        exists = conn.execute('SELECT id FROM user_favorite_sentences WHERE user_id = ? AND sentence_id = ?', (current_user.id, sid)).fetchone()
        if exists:
            conn.execute('DELETE FROM user_favorite_sentences WHERE id = ?', (exists['id'],))
            msg = UI_STRINGS[current_user.interface_language]['sentence_removed_fav']
            is_fav = False
        else:
            conn.execute('INSERT INTO user_favorite_sentences (user_id, sentence_id) VALUES (?, ?)', (current_user.id, sid))
            msg = UI_STRINGS[current_user.interface_language]['sentence_added_fav']
            is_fav = True
        conn.commit()
    
    # Return HTMX trigger to show toast and update UI state
    resp = jsonify({"ok": True})
    resp.headers['HX-Trigger'] = json.dumps({"showMessage": {"msg": msg, "type": "success"}, "favToggled": {"id": sid, "state": is_fav}})
    return resp

@app.route('/api/remove_fav_sentence', methods=['POST'])
@login_required
def remove_fav_sentence():
    fav_id = request.form.get('id')
    with get_db() as conn:
        conn.execute('DELETE FROM user_favorite_sentences WHERE id = ? AND user_id = ?', (fav_id, current_user.id))
        conn.commit()
    
    if is_htmx():
        resp = make_response("")
        msg = UI_STRINGS[current_user.interface_language]['sentence_removed_fav']
        resp.headers['HX-Trigger'] = json.dumps({"showMessage": {"msg": msg, "type": "success"}})
        return resp
    return jsonify({"ok": True})

def get_cached_or_generate_tts(text, lang):
    """Helper function to reuse TTS logic. Returns url or None."""
    if not text: return None
    
    # 1. Normalization
    clean_text = text.lower().strip()
    
    # 2. Hashing
    file_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    
    # 3. Sharding
    shard = file_hash[:2]
    
    # 4. Path Strategy
    # static/audio/cache/{lang}/{shard}/{file_hash}.ogg
    base_dir = os.path.join(app.root_path, 'static', 'audio', 'cache')
    target_dir = os.path.join(base_dir, lang, shard)
    filename = f"{file_hash}.ogg"
    filepath = os.path.join(target_dir, filename)
    
    web_path = f"/static/audio/cache/{lang}/{shard}/{filename}"
    
    char_count = len(text)
    
    # --- STATS UPDATE ---
    if os.path.exists(filepath):
        try:
            db.session.add(TTSLog(language=lang, chars=char_count, source='cache'))
            db.session.commit()
        except Exception as e:
            print(f"Log Error: {e}")
        return web_path
    
    # 5. Generate if missing
    # Use original text for generation to preserve casing/intonation
    audio_content = services.get_tts_audio(text, lang)
    
    if audio_content:
        # BILLING
        provider = 'google'
        cost = billing.calculate_tts_cost(text, provider)
        new_bal = billing.deduct_credits(current_user.id, cost)
        current_user.credits = new_bal
        
        os.makedirs(target_dir, exist_ok=True)
        with open(filepath, "wb") as out:
            out.write(audio_content)
            
        try:
            db.session.add(TTSLog(language=lang, chars=char_count, source='api'))
            db.session.commit() # Commit stats and billing
        except Exception as e:
            print(f"Log Error: {e}")
        return web_path
        
    return None

@app.route('/api/tts_pair', methods=['POST'])
@login_required
def tts_pair():
    de_text = request.json.get('de_text', '').strip()
    trans_text = request.json.get('trans_text', '').strip()
    
    urls = []
    
    # 1. German audio
    de_url = get_cached_or_generate_tts(de_text, 'de')
    if de_url:
        urls.append(de_url)
        
    # 2. Translation audio
    if trans_text:
        trans_parts = [part.strip() for part in re.split(r'[,;]', trans_text) if part.strip()]
        trans_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
        for part in trans_parts:
            trans_url = get_cached_or_generate_tts(part, trans_lang)
            if trans_url: urls.append(trans_url)
    return jsonify({"urls": urls, "credits": current_user.credits})

@app.route('/api/tts', methods=['POST'])
@login_required
def tts():
    text = request.json.get('text', '').strip()
    lang = request.json.get('lang', 'de')
    
    url = get_cached_or_generate_tts(text, lang)
    
    if not url:
        return jsonify({"error": "TTS failed"}), 500
            
    return jsonify({"url": url, "credits": current_user.credits})

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route('/speaking')
@login_required
def speaking():
    return render_template('speaking.html')

@app.route('/speaking/next', methods=['GET'])
@login_required
def speaking_next():
    """Returns the next sentence card as HTML partial"""
    with get_db() as conn:
        # Get a random sentence for the user's level
        row = conn.execute('SELECT * FROM sentences WHERE level = ? ORDER BY RANDOM() LIMIT 1', (current_user.level,)).fetchone()
        if not row:
            # Fallback
            row = conn.execute('SELECT * FROM sentences ORDER BY RANDOM() LIMIT 1').fetchone()
            
    if not row:
        return "<div class='task-text'>No sentences found. Please generate content in Admin.</div>"
        
    sentence = dict(row)
    
    # Determine text to display based on interface language
    lang_key = 'text_uk' if current_user.interface_language == 'ukr' else 'text_en'
    source_text = sentence.get(lang_key) or sentence.get('text_en')
    audio_key = 'audio_uk' if current_user.interface_language == 'ukr' else 'audio_en'
    
    # Check if favorite
    is_fav = False
    with get_db() as conn:
        if conn.execute('SELECT 1 FROM user_favorite_sentences WHERE user_id = ? AND sentence_id = ?', (current_user.id, sentence['id'])).fetchone():
            is_fav = True

    resp = make_response(render_template('partials/speaking_card.html', 
                           sentence=sentence, 
                           source_text=source_text,
                           audio_src=sentence.get(audio_key)))
    
    # Send ID and Fav state to frontend via header
    resp.headers['HX-Trigger'] = json.dumps({
        'sentenceLoaded': {'id': sentence['id'], 'isFav': is_fav}
    })
    
    return resp

@app.route('/api/evaluate_audio', methods=['POST'])
@login_required
def evaluate_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
        
    audio_file = request.files['audio']
    original_text = request.form.get('original_text', '')
    
    mime_type = audio_file.content_type or 'audio/webm'
    audio_data = audio_file.read()
    
    if len(audio_data) == 0:
        return jsonify({"error": "Empty audio file"}), 400
    
    lang_code = 'uk' if current_user.interface_language == 'ukr' else 'en'
    
    result = services.evaluate_audio_with_gemini(original_text, audio_data, lang_code, mime_type)
    
    # Розрахунок середнього балу
    p_score = result.get('pronunciation_score', 0)
    c_score = result.get('context_score', 0)
    g_score = result.get('grammar_score', 0)
    avg_score = int((p_score + c_score + g_score) / 3)
    result['average_score'] = avg_score

    # Вибір аудіо фідбеку з бази
    with get_db() as conn:
        # Шукаємо файл, де середній бал входить в діапазон [min_score, max_score]
        fb_row = conn.execute('''
            SELECT file_path FROM feedback 
            WHERE language = ? AND category = 'common' AND ? >= min_score AND ? <= max_score 
            ORDER BY RANDOM() LIMIT 1
        ''', (lang_code, avg_score, avg_score)).fetchone()
    
    if fb_row:
        result['feedback_audio_url'] = f"/static/audio/{fb_row['file_path']}"

    # BILLING
    new_bal = billing.deduct_credits(current_user.id, billing.PRICING['speaking_evaluation'])
    current_user.credits = new_bal
    result['credits'] = new_bal # Додаємо баланс у відповідь
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)