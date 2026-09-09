from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_anon_client
from app.deps import CurrentUser, get_current_user
from app.schemas import ConversationOut, MyConversationCreate, ProfileOut

router = APIRouter(prefix="/me", tags=["내정보"])


@router.get("", summary="내 계정 정보 조회")
def read_me(current_user: CurrentUser = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}


@router.get("/conversations", response_model=list[ConversationOut], summary="내 대화 목록 조회")
def my_conversations(current_user: CurrentUser = Depends(get_current_user)):
    client = get_anon_client()
    client.postgrest.auth(current_user.token)
    result = (
        client.table("conversations")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data

@router.post("/conversations", response_model=ConversationOut, status_code=201, summary="내 대화 생성")
def create_my_conversation(
    payload: MyConversationCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    client = get_anon_client()
    client.postgrest.auth(current_user.token)
    result = (
        client.table("conversations")
        .insert({"user_id": current_user.id, "title": payload.title})
        .execute()
    )
    return result.data[0]

@router.delete("/conversations/{conversation_id}", status_code=204, summary="내 대화 삭제")
def delete_my_conversation(
    conversation_id: UUID, current_user: CurrentUser = Depends(get_current_user)
):
    client = get_anon_client()
    client.postgrest.auth(current_user.token)
    result = (
        client.table("conversations").delete().eq("id", str(conversation_id)).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="conversation not found")


@router.get("/profile", response_model=ProfileOut, summary="내 프로필 조회")
def profile(current_user: CurrentUser = Depends(get_current_user)):
    client = get_anon_client()
    client.postgrest.auth(current_user.token)
    result = (
        client.table("profiles")
        .select("*")
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")    
    return result.data[0]

# @router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201)
# def create_my_message(
#     conversation_id: UUID,
#     payload: MessageCreate,
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     client = get_anon_client()
#     client.postgrest.auth(current_user.token)
#     try:
#         result = (
#             client.table("messages")
#             .insert(
#                 {
#                     "conversation_id": str(conversation_id),
#                     "role": payload.role,
#                     "content": payload.content,
#                 }
#             )
#             .execute()
#         )
#     except Exception:
#         raise HTTPException(status_code=403, detail="이 대화에 접근할 수 없습니다")
#     return result.data[0]
