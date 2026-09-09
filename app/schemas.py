from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# 회원가입용 요청
class SignupRequest(BaseModel):
    email: str
    password: str

# 회원로그인용 요청
class LoginRequest(BaseModel):
    email: str
    password: str

# 회원 응답
class TokenResponse(BaseModel):
    access_token: str | None
    user_id: str
    email: str

# 프로필 응답
class ProfileOut(BaseModel):
    id: UUID
    username: str
    created_at: datetime

# ── 대화 ──────────────────────────────────────────────────────────
class ConversationOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime

class MyConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)

# ── 메시지 ────────────────────────────────────────────────────────
# 주의: role 은 Literal 로 값을 고정한다. str 로 두면 'robot' 같은 값이 그대로 통과한다.
class MessageCreate(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)

class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    content: str
    # 화면에서 고른 값. 안 보내면 None 이고, gemini_client 가 기본값으로 바꾼다.
    # 주의: 여기에 기본 문자열을 적지 않는다. 적으면 선택지 목록이 두 파일에 나뉘어
    #      한쪽만 고쳤을 때 어긋난다. 선택지는 gemini_client.py 한 곳에만 둔다.
    tone: str | None = None
    length: str | None = None


