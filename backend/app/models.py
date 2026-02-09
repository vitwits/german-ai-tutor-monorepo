from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text as DBText, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    interface_language: Mapped[str] = mapped_column(String, default='ukr')
    level: Mapped[str] = mapped_column(String, default='A2')
    is_admin: Mapped[int] = mapped_column(Integer, default=0)
    
    # Cost tracking
    llm_cost: Mapped[float] = mapped_column(Float, default=0.0)
    tts_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Settings
    library_view_mode: Mapped[Optional[str]] = mapped_column(String, default='list')
    library_per_page: Mapped[Optional[int]] = mapped_column(Integer, default=20)
    vocab_view_mode: Mapped[Optional[str]] = mapped_column(String, default='list')
    vocab_per_page: Mapped[Optional[int]] = mapped_column(Integer, default=20)
    vocab_session_size: Mapped[Optional[int]] = mapped_column(Integer, default=20)
    study_batch_size: Mapped[Optional[int]] = mapped_column(Integer, default=20)

class Lesson(Base):
    __tablename__ = "lessons"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String)  # JSON: {"de": "...", "ua": "...", "en": "..."}
    level: Mapped[Optional[str]] = mapped_column(String)  # A1, A2, B1, B2, C1, C2
    content_json: Mapped[Optional[str]] = mapped_column(DBText)  # Sentences array
    quiz_json: Mapped[Optional[str]] = mapped_column(DBText)  # Quiz questions
    audio_status: Mapped[str] = mapped_column(String, default='pending')  # pending, generating, completed, partial_failed
    generation_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)  # Total cost to generate this lesson
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class UserLesson(Base):
    __tablename__ = "user_lessons"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), nullable=False)
    is_favorite: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class LessonAudio(Base):
    __tablename__ = "lesson_audio"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), nullable=False)
    sentence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    lang: Mapped[str] = mapped_column(String, default='de')  # de, en, uk
    audio_path: Mapped[Optional[str]] = mapped_column(String)  # Relative path: cache/de/ab/abc123.ogg
    status: Mapped[str] = mapped_column(String, default='pending')  # pending, generated, failed
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

class Vocabulary(Base):
    __tablename__ = "vocabulary"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    text_id: Mapped[Optional[str]] = mapped_column(String) # Can be null if word deleted from text but kept in vocab
    origin: Mapped[Optional[str]] = mapped_column(String)
    display: Mapped[Optional[str]] = mapped_column(String)
    ua: Mapped[Optional[str]] = mapped_column(String)
    en: Mapped[Optional[str]] = mapped_column(String)
    ctx: Mapped[Optional[str]] = mapped_column(String)
    is_favorite: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[Optional[str]] = mapped_column(String)
    
    # Positioning
    sentence_index: Mapped[Optional[int]] = mapped_column(Integer)
    start_index: Mapped[Optional[int]] = mapped_column(Integer)
    end_index: Mapped[Optional[int]] = mapped_column(Integer)
    
    # SRS (Spaced Repetition)
    interval: Mapped[float] = mapped_column(Float, default=1.0)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    next_review: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_reviewed: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Study tracking
    study_view_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class Sentence(Base):
    __tablename__ = "sentences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_de: Mapped[Optional[str]] = mapped_column(String)
    text_en: Mapped[Optional[str]] = mapped_column(String)
    text_uk: Mapped[Optional[str]] = mapped_column(String)
    audio_de: Mapped[Optional[str]] = mapped_column(String)  # Шлях на аудіо (relative), напр. "a1/0164_de.ogg"
    audio_en: Mapped[Optional[str]] = mapped_column(String)  # Шлях на аудіо (relative)
    audio_uk: Mapped[Optional[str]] = mapped_column(String)  # Шлях на аудіо (relative)
    level: Mapped[Optional[str]] = mapped_column(String)
    topic: Mapped[Optional[str]] = mapped_column(String)
    reported: Mapped[int] = mapped_column(Integer, default=0)

class UserBlockedSentence(Base):
    __tablename__ = "user_blocked_sentences"
    
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    sentence_id: Mapped[int] = mapped_column(ForeignKey("sentences.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class UserFavoriteSentence(Base):
    __tablename__ = "user_favorite_sentences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    sentence_id: Mapped[int] = mapped_column(ForeignKey("sentences.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class QuizResult(Base):
    __tablename__ = "quiz_results"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    text_id: Mapped[Optional[str]] = mapped_column(ForeignKey("texts.id"), nullable=True)  # Old user-specific texts
    lesson_id: Mapped[Optional[str]] = mapped_column(ForeignKey("lessons.id"), nullable=True)  # New global lessons
    score: Mapped[Optional[int]] = mapped_column(Integer)
    total_questions: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class Feedback(Base):
    __tablename__ = "feedback"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    text: Mapped[Optional[str]] = mapped_column(String)
    file_path: Mapped[Optional[str]] = mapped_column(String)
    language: Mapped[Optional[str]] = mapped_column(String)
    category: Mapped[Optional[str]] = mapped_column(String)
    min_score: Mapped[Optional[int]] = mapped_column(Integer)
    max_score: Mapped[Optional[int]] = mapped_column(Integer)

# Admin / Generation Tables
class SentenceBatch(Base):
    __tablename__ = "sentence_batches"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    level: Mapped[Optional[str]] = mapped_column(String)
    target_count: Mapped[Optional[int]] = mapped_column(Integer)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class TempSentence(Base):
    __tablename__ = "temp_sentences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("sentence_batches.id"))
    de: Mapped[Optional[str]] = mapped_column(String)
    en: Mapped[Optional[str]] = mapped_column(String)
    uk: Mapped[Optional[str]] = mapped_column(String)
    topic: Mapped[Optional[str]] = mapped_column(String)

class TTSLog(Base):
    """
    Aggregated TTS statistics for vocabulary translations.
    Stores cumulative counts and character counts per language and operation type.
    """
    __tablename__ = "tts_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # German (Deutsch)
    de_cache_requests: Mapped[int] = mapped_column(Integer, default=0)
    de_cache_chars: Mapped[int] = mapped_column(Integer, default=0)
    de_api_requests: Mapped[int] = mapped_column(Integer, default=0)
    de_api_chars: Mapped[int] = mapped_column(Integer, default=0)
    
    # English
    en_cache_requests: Mapped[int] = mapped_column(Integer, default=0)
    en_cache_chars: Mapped[int] = mapped_column(Integer, default=0)
    en_api_requests: Mapped[int] = mapped_column(Integer, default=0)
    en_api_chars: Mapped[int] = mapped_column(Integer, default=0)
    
    # Ukrainian (Українська)
    uk_cache_requests: Mapped[int] = mapped_column(Integer, default=0)
    uk_cache_chars: Mapped[int] = mapped_column(Integer, default=0)
    uk_api_requests: Mapped[int] = mapped_column(Integer, default=0)
    uk_api_chars: Mapped[int] = mapped_column(Integer, default=0)
    
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class LLMModel(Base):
    __tablename__ = "llm_models"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    human_name: Mapped[str] = mapped_column(String, nullable=False)  # Дружелюбне імя (e.g., "GPT-4 Turbo")
    model_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # Уникальний ID моделі (e.g., "gpt-4-turbo")
    provider: Mapped[str] = mapped_column(String, nullable=False)  # "google" | "azure" | "openai"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class TTSModel(Base):
    __tablename__ = "tts_models"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    human_name: Mapped[str] = mapped_column(String, nullable=False)  # Дружелюбне імя (e.g., "Google TTS German")
    family: Mapped[str] = mapped_column(String, nullable=False)  # Сім'я моделі (користувач вводить вручну)
    provider: Mapped[str] = mapped_column(String, nullable=False)  # "google" | "azure" | "openai" | тощо
    price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)  # Ціна за 1млн символів
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class LLMPrice(Base):
    __tablename__ = "llm_prices"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    human_name: Mapped[str] = mapped_column(String, nullable=False)  # Дружелюбне імя
    llm_model_id: Mapped[int] = mapped_column(ForeignKey("llm_models.id"), nullable=False)  # Foreign key до llm_models
    direction: Mapped[str] = mapped_column(String, nullable=False)  # "input" | "output"
    data_type: Mapped[str] = mapped_column(String, nullable=False)  # "text" | "audio" | "image"
    price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)  # Ціна за 1млн символів
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class TTSVoice(Base):
    __tablename__ = "tts_voices"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voice_name: Mapped[str] = mapped_column(String, nullable=False)  # Ім'я голосу (e.g., "de-DE-Standard-A")
    tts_model_id: Mapped[int] = mapped_column(ForeignKey("tts_models.id"), nullable=False)  # Foreign key до tts_models
    lang: Mapped[str] = mapped_column(String, nullable=False)  # "EN" | "DE" | "UA"
    gender: Mapped[str] = mapped_column(String, nullable=False)  # "male" | "female"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class AIPreference(Base):
    __tablename__ = "ai_preferences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # e.g., "vocabulary_tts_de"
    page: Mapped[str] = mapped_column(String, nullable=False)  # "texts" | "words" | "sentences" | "speaking"
    model_type: Mapped[str] = mapped_column(String, nullable=False)  # "tts" | "llm"
    lang: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "DE" | "EN" | "UA" | NULL
    gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "male" | "female" | NULL (for TTS only)
    
    # Foreign Keys
    llm_model_id: Mapped[Optional[int]] = mapped_column(ForeignKey("llm_models.id"), nullable=True)
    tts_voice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tts_voices.id"), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships (для зручного доступу)
    llm_model: Mapped[Optional["LLMModel"]] = relationship("LLMModel")
    tts_voice: Mapped[Optional["TTSVoice"]] = relationship("TTSVoice")


class ModelPrompt(Base):
    __tablename__ = "model_prompts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)  # Custom name (e.g., "generate_texts_a1")
    page: Mapped[str] = mapped_column(String, nullable=False)  # "texts" | "words" | "sentences" | "speaking"
    prompt: Mapped[str] = mapped_column(DBText, nullable=False)  # Large text value with the prompt
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class BillingPlan(Base):
    __tablename__ = "billing_plans"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monthly_credit: Mapped[float] = mapped_column(Float, nullable=False)  # USD per month
    max_cap_days: Mapped[int] = mapped_column(Integer, nullable=False)  # Days for credit accumulation
    day_energy: Mapped[int] = mapped_column(Integer, nullable=False)  # Energy points per day
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class UserBilling(Base):
    __tablename__ = "user_billing"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    
    # Subscription status
    subscription_status: Mapped[str] = mapped_column(String, default='active')  # active|inactive|cancelled
    
    # Billing period tracking
    billing_start_day: Mapped[int] = mapped_column(Integer, nullable=False)  # Day of month (1-31)
    billing_end_day: Mapped[Optional[int]] = mapped_column(Integer)  # Last day of period (informational)
    
    # Energy tracking
    energy_left: Mapped[float] = mapped_column(Float, default=0.0)  # Current energy points
    daily_spending: Mapped[float] = mapped_column(Float, default=0.0)  # USD spent today
    
    # Price tracking (calculated dynamically but cached for consistency)
    price_per_point_usd: Mapped[float] = mapped_column(Float, default=0.0)  # Cost in USD for 1 energy point
    
    # Timestamps
    last_energy_reset: Mapped[datetime] = mapped_column(DateTime, default=func.now())  # Last daily reset at 00:00
    last_billing_reset: Mapped[datetime] = mapped_column(DateTime, default=func.now())  # Last monthly reset
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class ReportedLesson(Base):
    __tablename__ = "reported_lessons"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default='reported')  # reported, ignored, deleted
    admin_notes: Mapped[Optional[str]] = mapped_column(DBText)
    reported_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

