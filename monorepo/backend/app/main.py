from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from .routers import auth, library, vocabulary, speaking, tts

app = FastAPI(title="German AI Tutor API")

# CORS для Svelte (який буде на порту 5173)
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Підключення статики (аудіо) з папки backend/static
# monorepo/backend/app -> monorepo/backend -> static
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../static"))
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth.router)
app.include_router(library.router)
app.include_router(vocabulary.router)
app.include_router(speaking.router)
app.include_router(tts.router)

@app.get("/")
def read_root():
    return {"message": "German AI Tutor API is running"}
