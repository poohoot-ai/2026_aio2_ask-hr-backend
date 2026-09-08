import hashlib
import json
from uuid import UUID
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_anon_client
from app.cache import cache_get, cache_set

# Swagger 의 Authorize 버튼이 여기서 온다.
bearer_scheme = HTTPBearer()

SESSION_CACHE_TTL_SECONDS = 300

@dataclass
class CurrentUser:
    id: str
    email: str
    token: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    # 클라이언트가 보낸 토큰
    token = credentials.credentials

    # 원본 토큰 > 해시 토큰
    cache_key = f"session:{hashlib.sha256(token.encode()).hexdigest()}"

    # 캐시에서 get
    cached = cache_get(cache_key)
    # hit 일 때
    if cached:
        data = json.loads(cached) # 캐시의 사용자 정보
        return CurrentUser(id=data["id"], 
                           email=data["email"], 
                           token=token
                           )

    # miss 일 때 수파베이스 서버에 보관중인 토큰과 비교해서 결과를 가져옵니다.
    client = get_anon_client()
    try:
        result = client.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    current_user = CurrentUser(id=str(result.user.id), email=result.user.email, token=token)
    cache_set(
        cache_key,
        json.dumps({"id": current_user.id, "email": current_user.email}),
        SESSION_CACHE_TTL_SECONDS,
    )
    return current_user

def require_own_conversation(
    conversation_id: UUID, current_user: CurrentUser = Depends(get_current_user)
) -> UUID:
    """이 대화가 내 것인지 확인한다. 아니면 404.

    /me/conversations 와 같은 원리다. 우리가 소유자를 비교하지 않는다.
    RLS 를 켠 클라이언트로 조회해서 0건이면 내 것이 아니다.

    없는 대화와 남의 대화를 구분하지 않고 똑같이 404 로 답한다.
    구분해서 알려주면 "그 대화는 존재한다"는 정보를 흘리게 된다.
    """
    client = get_anon_client()
    client.postgrest.auth(current_user.token)
    owned = (
        client.table("conversations")
        .select("id")
        .eq("id", str(conversation_id))
        .execute()
    )
    if not owned.data:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation_id
