# API 설계 문서

## 대화

| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| GET | /conversations/{conversation_id}/messages | 대화 메시지 목록 조회 |
| POST | /conversations/{conversation_id}/chat | 채팅 응답 생성 |

## 인증

| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| POST | /auth/signup | 회원가입 |
| POST | /auth/login | 로그인 |

## 내정보

| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| GET | /me | 내 계정 정보 조회 |
| GET | /me/conversations | 내 대화 목록 조회 |
| POST | /me/conversations | 내 대화 생성 |
| DELETE | /me/conversations/{conversation_id} | 내 대화 삭제 |
| GET | /me/profile | 내 프로필 조회 |

## 대시보드

| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| GET | /analytics/summary | 사용량 통계 요약 조회 |
| GET | /analytics/logs | 사용량 로그 목록 조회 |
| GET | /analytics/conversations | 대화별 사용량 통계 조회 |

## 시스템

| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| GET | /health | 백엔드 상태 확인 |
