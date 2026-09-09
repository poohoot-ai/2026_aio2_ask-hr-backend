"""대화·메시지 API"""

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends

from app.db import supabase

from app.schemas import MessageCreate, MessageOut
from app.cache import cache_delete, cache_get, cache_set
from app.deps import require_own_conversation

MESSAGES_CACHE_TTL_SECONDS = 300

router = APIRouter(prefix="/conversations", tags=["대화"])

def _messages_cache_key(conversation_id: UUID) -> str:
    return f"messages:{conversation_id}"

def create_message(conversation_id: UUID, payload: MessageCreate):
    conversation = (
        supabase.table("conversations")
        .select("id")
        .eq("id", str(conversation_id))
        .execute()
    )
    if not conversation.data:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    result = (
        supabase.table("messages")
        .insert(
            {
                "conversation_id": str(conversation_id),
                "role": payload.role,
                "content": payload.content,
            }
        )
        .execute()
    )
    cache_delete(_messages_cache_key(conversation_id))   # 이 줄을 추가
    if payload.role == "user":
        _update_first_message_title(conversation_id, result.data[0])
    return result.data[0]

def _update_first_message_title(conversation_id: UUID, message: dict) -> None:
    """전체 사용자 메시지 중 첫 메시지만 대화 제목으로 사용한다."""
    first = (
        supabase.table("messages")
        .select("id")
        .eq("conversation_id", str(conversation_id))
        .eq("role", "user")
        .order("created_at")
        .order("id")
        .limit(1)
        .execute()
    )
    if not first.data or first.data[0]["id"] != message["id"]:
        return

    title = " ".join(message["content"].split())[:50] or "새 대화"
    (
        supabase.table("conversations")
        .update({"title": title})
        .eq("id", str(conversation_id))
        .execute()
    )

def list_messages(conversation_id: UUID, limit: int = 20, offset: int = 0):
    cache_key = _messages_cache_key(conversation_id)
    # 캐시에서 get
    cached = cache_get(cache_key)

    # hit
    if cached:
        return json.loads(cached)

    result = (
        supabase.table("messages")
        .select("*")
        .eq("conversation_id", str(conversation_id))
        .order("created_at", desc=False)
        .range(offset, offset + limit - 1)
        .execute()
    )

    cache_set(cache_key, json.dumps(result.data, default=str), MESSAGES_CACHE_TTL_SECONDS)

    return result.data


@router.get("/{conversation_id}/messages", response_model=list[MessageOut], summary="대화 메시지 목록 조회")
def get_messages(conversation_id: UUID = Depends(require_own_conversation)):
    return list_messages(conversation_id)
