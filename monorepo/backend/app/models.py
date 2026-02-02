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
    credits: Mapped[float] = mapped_column(Float, default=1000.0)
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

class Text(Base):
    __tablename__ = "texts"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String)
    level: Mapped[Optional[str]] = mapped_column(String)
    content_json: Mapped[Optional[str]] = mapped_column(DBText)
    is_favorite: Mapped[int] = mapped_column(Integer, default=0)
    quiz_json: Mapped[Optional[str]] = mapped_column(DBText)

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
    text_id: Mapped[str] = mapped_column(ForeignKey("texts.id"), nullable=False)
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
    __tablename__ = "tts_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    language: Mapped[Optional[str]] = mapped_column(String)
    chars: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())



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

