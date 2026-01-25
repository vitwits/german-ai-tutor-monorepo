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
    
    # Settings
    library_view_mode: Mapped[Optional[str]] = mapped_column(String, default='list')
    library_per_page: Mapped[Optional[int]] = mapped_column(Integer, default=20)
    vocab_view_mode: Mapped[Optional[str]] = mapped_column(String, default='list')
    vocab_per_page: Mapped[Optional[int]] = mapped_column(Integer, default=20)
    vocab_session_size: Mapped[Optional[int]] = mapped_column(Integer, default=20)

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

class GrammarExplanation(Base):
    __tablename__ = "grammar_explanations"
    
    text_id: Mapped[str] = mapped_column(String, primary_key=True)
    sentence_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String, primary_key=True)
    explanation: Mapped[Optional[str]] = mapped_column(DBText)

class Sentence(Base):
    __tablename__ = "sentences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_de: Mapped[Optional[str]] = mapped_column(String)
    text_en: Mapped[Optional[str]] = mapped_column(String)
    text_uk: Mapped[Optional[str]] = mapped_column(String)
    audio_de: Mapped[Optional[str]] = mapped_column(String)
    audio_en: Mapped[Optional[str]] = mapped_column(String)
    audio_uk: Mapped[Optional[str]] = mapped_column(String)
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
