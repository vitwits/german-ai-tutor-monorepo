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
    token_type: str

class TokenData(BaseModel):
    email: str | None = None
    user_id: str | None = None

class UserRead(UserBase):
    id: str
    level: str
    credits: float
    interface_language: str

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

class TextReadSchema(BaseModel):
    id: str
    title: Optional[str]
    level: Optional[str]
    content_json: str
    is_favorite: int
    quiz_json: Optional[str]
    display_title: Optional[str] = None
    trans_title: Optional[str] = None

    class Config:
        from_attributes = True

# --- Vocabulary Schemas ---
class VocabWordSchema(BaseModel):
    id: str
    display: Optional[str]
    ua: Optional[str]
    en: Optional[str]
    ctx: Optional[str]
    is_favorite: int
    level: Optional[str]
    text_id: Optional[str]
    sentence_index: Optional[int]
    start_index: Optional[int]
    end_index: Optional[int]
    display_trans: Optional[str] = None

    class Config:
        from_attributes = True

class QuickTranslateRequest(BaseModel):
    text: str
    ctx: str
    tid: str
    sent_idx: int
    start_char_index: int

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

class TTSPairRequest(BaseModel):
    de_text: str
    trans_text: str

class ReportSentenceRequest(BaseModel):
    id: int

class ToggleSentenceFavRequest(BaseModel):
    id: int

class RemoveFavSentenceRequest(BaseModel):
    id: int

class GrammarExplainRequest(BaseModel):
    sentence: str
    text_id: Optional[str] = None
    sentence_index: Optional[int] = None

class QuizResultRequest(BaseModel):
    text_id: str
    score: int
    total: int

class UserSettingsUpdate(BaseModel):
    interface_language: Optional[str] = None
    vocab_session_size: Optional[int] = None

class UserLevelUpdate(BaseModel):
    level: str

class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)