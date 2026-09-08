"""챗봇 응답을 만드는 라우터."""
import time
import json
from datetime import datetime, timezone

from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from google.genai import types

from app.db import supabase
from app.gemini_client import (
    GEMINI_MODEL,
    build_system_prompt,
    client,
)
from app.routers.conversations import create_message, list_messages
from app.schemas import ChatRequest, RegenerateRequest, MessageCreate, MessageOut, FeedbackRequest
from app.redis_client import r
from app.deps import require_own_conversation

# 채팅을 처리하는 엔드포인트 라우트
router = APIRouter(prefix="/conversations", tags=["chat"])

# 사용자와 챗봇 메시지를 합쳐 최근 몇 개까지 모델에 보낼지.
# 20개면 대략 10번 주고받은 분량이다.
MAX_HISTORY_MESSAGES = 20

# 우리 DB 의 role 을 Gemini 의 role 로 바꾼다.
# 이 표에 없는 role(system)은 아예 보내지 않는다.
_ROLE_MAP = {"user": "user", "assistant": "model"}

MAX_USAGE_LOGS = 50


def _usage_log_key(conversation_id: UUID) -> str:
    return f"usage_log:{conversation_id}"

def _log_usage(conversation_id: UUID, started_at: float, usage) -> None:
    """언제 요청했고 얼마나 걸렸는지 남긴다.

    Redis 리스트에 넣고 최근 N건만 남긴다. 새 테이블을 만들지 않는 이유는
    이것이 서비스 데이터가 아니라 운영 기록이기 때문이다. 지워져도 서비스는 돈다.
    """
    entry = {
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "latency_ms": round((time.monotonic() - started_at) * 1000),
        "prompt_tokens": getattr(usage, "prompt_token_count", None),
        "response_tokens": getattr(usage, "candidates_token_count", None),
        "total_tokens": getattr(usage, "total_token_count", None),
    }
    key = _usage_log_key(conversation_id)
    r.lpush(key, json.dumps(entry))
    r.ltrim(key, 0, MAX_USAGE_LOGS - 1)

@router.get("/{conversation_id}/usage-logs")
def usage_logs(conversation_id: UUID = Depends(require_own_conversation)):
    raw = r.lrange(_usage_log_key(conversation_id), 0, MAX_USAGE_LOGS - 1)
    return [json.loads(item) for item in raw]

def _conversation_title(conversation_id: UUID) -> str:
    """대화 제목이 대화에 포함된다. `새 대화 시작` 에서 받은 값이다."""
    result = (
        supabase.table("conversations")
        .select("title")
        .eq("id", str(conversation_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result.data[0]["title"] or "대화 미지정"

def _build_history(conversation_id: UUID) -> list[dict]:
    """모델에게 보낼 이전 대화를 만든다.

    세 단계로 줄인다. 순서가 중요하다.
      1) 마지막 초기화 지점 이후만 남긴다
      2) 모델이 모르는 role(system)을 뺀다
      3) 최근 MAX_HISTORY_MESSAGES 개만 남긴다

    3번을 1번보다 먼저 하면, 최근 20개 안에 초기화 지점이 없을 때
    끊었던 옛날 대화가 다시 딸려 들어간다
    """
    messages = list_messages(conversation_id)  # 시간 오름차순, Redis 캐시 적용됨

    # 최근 초기화 시점 +1 다음부터 메시지를 꺼낸다.
    for index in range(len(messages) - 1, -1, -1):
        if messages[index]["role"] == "system":
            messages = messages[index + 1 :]
            break

    # 롤 매핑 & 최근 20개만 꺼내기
    usable = [m for m in messages if m["role"] in _ROLE_MAP]
    recent = usable[-MAX_HISTORY_MESSAGES:]

    return [
        {"role": _ROLE_MAP[m["role"]], "parts": [{"text": m["content"]}]}
        for m in recent
    ]

def _stream_answer(conversation_id: UUID, contents: list, system_prompt: str):
    """모델의 응답을 조각으로 흘려보내고, 끝나면 통째로 저장한다."""

    def event_stream():
        started_at = time.monotonic()
        full_text = ""
        last_usage = None
        try:
            # 3) 사용자 메시지 + 시스템 프롬프트로 제미나이 응답 호출하기
            for chunk in client.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system_prompt),
            ):
                if chunk.text:
                    full_text += chunk.text
                    # 주의: 조각 안의 줄바꿈은 그대로 보내면 SSE 형식이 깨진다.
                    #      한 이벤트는 빈 줄로 끝나기로 약속돼 있기 때문이다.
                    yield "data: " + json.dumps({"text": chunk.text}) + "\n\n"
                if chunk.usage_metadata:
                    last_usage = chunk.usage_metadata
        except Exception as e:
            # 스트림이 이미 시작돼 상태 코드를 바꿀 수 없다. 이벤트로 알린다.
            yield "data: " + json.dumps({"error": f"{type(e).__name__}: {e}"}) + "\n\n"
            return

        if not full_text:
            yield "data: " + json.dumps({"error": "모델이 빈 응답을 돌려주었습니다."}) + "\n\n"
            return

        # 다 받은 뒤에 한 번만 저장한다. 조각마다 저장하면 메시지가 수십 개로 쪼개진다.
        saved = create_message(
            conversation_id, MessageCreate(role="assistant", content=full_text)
        )
        _log_usage(conversation_id, started_at, last_usage)
        yield "data: " + json.dumps({"done": True, "message_id": saved["id"]}) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.post("/{conversation_id}/chat")
def chat(payload: ChatRequest, conversation_id: UUID = Depends(require_own_conversation)):
    conversation_title = _conversation_title(conversation_id)
    # 후속 질문의 주제도 확인할 수 있도록, 사용자 메시지 저장 전에 이력을 읽는다.
    history = _build_history(conversation_id)
    # 선택한 파일이 누락되거나 비어 있으면 모델 호출 전에 오류로 처리한다.
    try:
        system_prompt = build_system_prompt(conversation_title, payload.content, history)
    except (OSError, ValueError) as exc:
        # 파일 읽기 실패, UTF-8 해석 실패, 빈 파일을 기존 HTTPException으로 알린다.
        raise HTTPException(
            status_code=503,
            detail=(
                "선택한 규정 파일을 읽을 수 없습니다. "
                "backend/data/regulations 폴더의 해당 MD 파일과 UTF-8 저장 여부를 확인해 주세요."
            ),
        ) from exc

    # 1) 사용자 메시지를 먼저 메시지 테이블에 저장한다.
    #    모델 호출이 실패해도(429 등) 사용자가 쓴 답변은 남아야 한다.
    create_message(conversation_id, MessageCreate(role="user", content=payload.content))
    contents = history + [{"role": "user", "parts": [{"text": payload.content}]}]    

    return _stream_answer(
        conversation_id, 
        contents, 
        system_prompt)
