# API 설계 문서

## conversations
| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| POST | /conversations/{conversation_id}/messages | 대화 속 메시지 하나를 추가합니다. |
| GET | /conversations/{conversation_id}/messages | 대화 속 메시지들을 가져옵니다. |

## chat
| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| GET | /conversations/{conversation_id}/usage-logs | 사용 로그 관련 기능 |
| POST | /conversations/{conversation_id}/chat | LLM 채팅 |

## auth
| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| POST | /auth/signup | 회원가입 |
| POST | /auth/login | 로그인 |

## me
| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| GET | /me | 내 정보(이메일) 조회 |
| GET | /me/conversations | 내 대화 목록 조회 |
| POST | /me/conversations | 내 대화 생성 |
| DELETE | /me/conversations/{conversation_id} | 내 대화 삭제 |
| GET | /me/profile | 내 프로필(username) 조회 |
| POST | /me/conversations/{conversation_id}/messages | 대화 속 내 메시지 추가 |

## analytics
| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| GET | /analytics/summary |  응답 수, 지연시간, 토큰 요약 |
| GET | /analytics/logs | 최근 5회 응답 그래프, 로그 목록 |
| GET | /analytics/conversations | 대화별 통계 목록 |

## default
| Method | Endpoint | 기능 및 목적 |
| :--- | :--- | :--- |
| GET | /health | 백엔드 상태 확인 |