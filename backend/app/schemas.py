from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str

class TokenData(BaseModel):
    email: str | None = None
    user_id: str | None = None

class BillingDataPublic(BaseModel):
    """Public billing data shown to user (only energy_left and subscription status)"""
    energy_left: float
    subscription_status: str
    
    class Config:
        from_attributes = True

class BillingData(BaseModel):
    """Complete billing data (internal use only)"""
    energy_left: float
    daily_spending: float
    price_per_point_usd: float
    subscription_status: str
    billing_start_day: int
    
    class Config:
        from_attributes = True

class UserRead(UserBase):
    id: str
    level: str
    interface_language: str
    billing: Optional[BillingDataPublic] = None

    class Config:
        from_attributes = True

# --- Text Schemas ---
class SentenceSchema(BaseModel):
    de: str
    ua: str
    en: str

class QuizQuestionSchema(BaseModel):
    question: str
    options: List[str]
    correct_index: int

class TextGenerateRequest(BaseModel):
    topic: str
    level: str
    style: str
    size: str

class CreateOwnTextRequest(BaseModel):
    text: str

class TextReadSchema(BaseModel):
    id: str
    title: Optional[str]
    level: Optional[str]
    content_json: str
    is_favorite: int
    quiz_json: Optional[str]
    display_title: Optional[str] = None
    trans_title: Optional[str] = None
    custom_title: Optional[str] = None

    class Config:
        from_attributes = True

# --- Vocabulary Schemas ---
class VocabWordSchema(BaseModel):
    id: str
    display: Optional[str]
    ua: Optional[str]
    en: Optional[str]
    ctx: Optional[str]
    ctx_ua: Optional[str]
    ctx_en: Optional[str]
    is_favorite: int
    level: Optional[str]
    text_id: Optional[str]
    sentence_index: Optional[int]
    start_index: Optional[int]
    end_index: Optional[int]
    interval: Optional[float] = None
    ease_factor: Optional[float] = None
    next_review: Optional[datetime] = None
    last_reviewed: Optional[datetime] = None
    study_view_count: Optional[int] = 0
    display_trans: Optional[str] = None
    display_ctx_trans: Optional[str] = None
    audio_de_url: Optional[str] = None
    audio_trans_urls: Optional[list] = None

    class Config:
        from_attributes = True

class QuickTranslateRequest(BaseModel):
    text: str
    ctx: str
    tid: str
    sent_idx: int
    start_char_index: int

class ExplainWordRequest(BaseModel):
    text: str
    tid: str
    sent_idx: int
    start_char_index: int

class AddCustomWordRequest(BaseModel):
    text: str

class VocabUpdateRequest(BaseModel):
    id: str
    translation: str

class VocabRemoveRequest(BaseModel):
    id: str
    from_vocab: bool = False

class ToggleFavRequest(BaseModel):
    id: str

class VocabProgressRequest(BaseModel):
    id: str
    rating: str

class TTSRequest(BaseModel):
    text: str
    lang: str = 'de'
    source: str = 'texts'  # 'texts' або 'vocabulary'

class TTSPairRequest(BaseModel):
    de_text: str
    trans_text: str
    source: str = 'texts'  # 'texts' або 'vocabulary'

class TTSBatchRequest(BaseModel):
    sentences: List[str]  # List of German sentences
    lang: str = 'de'

class ReportSentenceRequest(BaseModel):
    id: int

class ToggleSentenceFavRequest(BaseModel):
    id: int

class RemoveFavSentenceRequest(BaseModel):
    id: int

class QuizResultRequest(BaseModel):
    text_id: str
    score: int
    total: int


class DictationCheckRequest(BaseModel):
    sentence_index: int
    user_text: str


class DictationProgressSaveRequest(BaseModel):
    order: List[int]
    cursor: int
    passed_indices: List[int]
    playback_rate: float = 0.8


class DictationProgressClearRequest(BaseModel):
    keep_completed: bool = True


class SentenceTranslationTestCheckRequest(BaseModel):
    sentence_index: int
    user_text: str
    source_text: str


class SentenceTranslationTestProgressSaveRequest(BaseModel):
    order: List[int]
    cursor: int
    passed_indices: List[int]


class SentenceTranslationTestProgressClearRequest(BaseModel):
    keep_completed: bool = True

class UserSettingsUpdate(BaseModel):
    interface_language: Optional[str] = None
    vocab_session_size: Optional[int] = None
    study_batch_size: Optional[int] = None

class UserLevelUpdate(BaseModel):
    level: str

class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)