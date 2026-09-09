from fastapi import APIRouter, HTTPException

from app.db import get_anon_client
from app.schemas import LoginRequest, SignupRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["인증"])


@router.post("/signup", response_model=TokenResponse, summary="회원가입")
def signup(payload: SignupRequest):
    client = get_anon_client()
    try:
        # 수파베이스 auth 테이블에 사용자 1건 등록하기
        result = client.auth.sign_up(
            {
                "email": payload.email, 
                "password": payload.password
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    access_token = result.session.access_token if result.session else None

    return TokenResponse(
        access_token=access_token,
        user_id=str(result.user.id),
        email=result.user.email,
    )


@router.post("/login", response_model=TokenResponse, summary="로그인")
def login(payload: LoginRequest):
    client = get_anon_client()
    try:
        # 수파베이스 auth 모듈의 비밀번호 로그인 호출
        result = client.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    access_token = result.session.access_token if result.session else None

    return TokenResponse(
        access_token=access_token,
        user_id=str(result.user.id),
        email=result.user.email,
    )
