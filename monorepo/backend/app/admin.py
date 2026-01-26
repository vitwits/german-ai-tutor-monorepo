from sqladmin import Admin, ModelView
from .models import User, Text, Sentence, Vocabulary, SentenceBatch, Feedback, TTSLog

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.level, User.credits, User.is_admin]
    column_searchable_list = [User.email]
    icon = "fa-solid fa-user"

class SentenceAdmin(ModelView, model=Sentence):
    column_list = [Sentence.id, Sentence.text_de, Sentence.text_uk, Sentence.level, Sentence.reported]
    column_searchable_list = [Sentence.text_de, Sentence.text_uk]
    column_filters = [Sentence.level, Sentence.reported]
    icon = "fa-solid fa-align-left"

class TextAdmin(ModelView, model=Text):
    column_list = [Text.id, Text.level, Text.is_favorite]
    icon = "fa-solid fa-book"

class VocabAdmin(ModelView, model=Vocabulary):
    column_list = [Vocabulary.display, Vocabulary.ua, Vocabulary.level, Vocabulary.user_id]
    column_searchable_list = [Vocabulary.display, Vocabulary.ua]
    icon = "fa-solid fa-language"

class BatchAdmin(ModelView, model=SentenceBatch):
    column_list = [SentenceBatch.id, SentenceBatch.name, SentenceBatch.status, SentenceBatch.processed_count]
    icon = "fa-solid fa-layer-group"

class TTSLogAdmin(ModelView, model=TTSLog):
    column_list = [TTSLog.created_at, TTSLog.language, TTSLog.source, TTSLog.chars]
    column_default_sort = ("created_at", True)
    icon = "fa-solid fa-chart-bar"

def setup_admin(app, engine):
    admin = Admin(app, engine, title="German AI Tutor")
    admin.add_view(UserAdmin)
    admin.add_view(SentenceAdmin)
    admin.add_view(TextAdmin)
    admin.add_view(VocabAdmin)
    admin.add_view(BatchAdmin)
    admin.add_view(TTSLogAdmin)
