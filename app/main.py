"""FastAPI 앱 진입점.

실행:  uv run uvicorn app.main:app --reload
확인:  http://127.0.0.1:8000/health  ·  http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI
from app.routers import auth, conversations, me, chat, analytics

app = FastAPI(title="AskHR", version="0.1.0")

app.include_router(conversations.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(analytics.router)

@app.get("/health")
def health():
    return {"status": "ok"}
