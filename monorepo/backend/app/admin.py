from sqladmin import Admin, ModelView
from sqlalchemy.orm import Session
from .models import User, Text, Sentence, Vocabulary, SentenceBatch, Feedback, TTSLog

class UserAdmin(ModelView, model=User):
    pass

class SentenceAdmin(ModelView, model=Sentence):
    pass

class TextAdmin(ModelView, model=Text):
    pass

class VocabAdmin(ModelView, model=Vocabulary):
    pass

class BatchAdmin(ModelView, model=SentenceBatch):
    pass

class TTSLogAdmin(ModelView, model=TTSLog):
    pass

def setup_admin(app, engine):
    admin = Admin(app, engine, title="German AI Tutor")
    admin.add_model_view(UserAdmin)
    admin.add_model_view(SentenceAdmin)
    admin.add_model_view(TextAdmin)
    admin.add_model_view(VocabAdmin)
    admin.add_model_view(BatchAdmin)
    admin.add_model_view(TTSLogAdmin)
