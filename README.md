# AskHR - BackEnd

## 준비 (uv 설치)
```powershell
pip install uv
```
```powershell
uv --version
```

## 실행
```powershell
uv sync
```

```powershell
uv run uvicorn app.main:app --reload
```

## 확인
* http://127.0.0.1:8000/health
* http://127.0.0.1:8000/docs

## 메서드
| 메서드 | 주소 | 하는 일 | 성공 코드 |
| --- | --- | --- | --- |
| `GET` | `/health` | 서버 상태 확인 | 200 |

## 주의

- `pydantic[email]`이 없으면 `EmailStr` 때문에 서버가 시작되지 않는다. `pyproject.toml`에 있다.
- `.env`는 커밋하지 않는다.
- `app` 폴더를 파이썬 패키지로 인식시키는 빈 `__init__.py`가 필요하다.

## 분석 대시보드 API

모든 분석 API는 로그인 토큰 `Authorization: Bearer <access_token>`이 필요하며 전체 사용자의 로그를 조회한다.
로그인한 모든 사용자가 접근할 수 있으며 별도의 관리자 등록은 필요하지 않다.
기존 일반 사용자 대화 API의 소유자 제한은 변경하지 않는다.
Swagger `/docs`에서 Authorize 후 테스트할 수 있다.

| 메서드 | 주소 | 용도 |
| --- | --- | --- |
| GET | `/analytics/summary` | 요청 수, 토큰 합계, 평균·p95 응답 시간, 대화 수 |
| GET | `/analytics/timeseries` | UTC 시간별·일별 추이 (빈 구간 포함) |
| GET | `/analytics/conversations` | 대화별 통계, 요청 수 내림차순 |
| GET | `/analytics/logs` | 로그 상세 목록, 기록 시각 내림차순 |

공통 쿼리:

- `start`, `end`: 시간대가 포함된 ISO 8601 시각. `start` 포함, `end` 제외.
  생략하면 `end`는 현재, `start`는 `end`의 30일 전이다. 최대 조회 기간은 366일이다.
- `conversation_id`: 선택적 대화 UUID. 소유자 제한 없이 조회하며 DB와 Redis 모두에 없는 대화는 404.
- `/timeseries`의 `interval`: `day`(기본) 또는 `hour`. UTC로 구간을 나눈다.
  첫·마지막 구간은 조회 기간과 겹치는 부분만 집계한다.
- `/logs`, `/conversations`의 `limit`: 기본 50, 1~200. `offset`: 기본 0, 0 이상.
  응답 `total`은 페이지를 나누기 전 결과 개수다.

예: `/analytics/timeseries?start=2026-09-01T00:00:00Z&end=2026-09-08T00:00:00Z&interval=day`

통계의 `request_count`는 해당 기간에 남아 있는 성공 응답 로그 수다.
`conversation_count`는 전체 DB 대화와 Redis에만 남은 대화를 합친 수(기간 내 생성 건수가 아님),
`active_conversation_count`는 기간 내 로그가 있는 대화 수다.
대화별 목록에는 기간 내 로그가 없는 대화도 0건으로 포함된다.
토큰 합계는 알려진 값만 더하며 일부 토큰 정보가 없는 로그 수를
`missing_usage_count`로 제공한다. 빈 결과의 지연 시간은 `null`이다.
p95는 정렬한 지연 시간에서 nearest-rank 방식으로 계산한다.

### 데이터 범위와 보관

현재 Redis의 모든 `usage_log:*` 목록을 분석한다. 저장 측에서 **대화별 최근 50건**만 유지하므로 이미 삭제된 과거 로그는 복구할 수 없다. `coverage.scope`는 `all_users`다.
오래된 기록은 이미 잘려 있을 수 있으므로 전체 기간의 누적 통계로 해석하면 안 된다.
응답 `coverage.complete_history=false`와 `max_logs_per_conversation=50`으로 이 범위를 표시한다.
`requested_at`은 기존 저장 코드 기준 로그 저장 시각이며 요청 시작 시각이 아니다.
실패 요청은 수집되지 않으므로 오류율을 계산할 수 없다.
삭제된 대화도 Redis에 로그가 남아 있으면 포함하고 제목은 `삭제되었거나 정보가 없는 대화`로 표시한다. 잘못된 JSON/필드의 로그는 제외하고
`coverage.skipped_invalid_logs`에 읽은 로그 중 제외한 개수를 표시한다(기간 필터 적용 전).
Redis 장애는 503, 잘못된 쿼리는 422를 반환한다.

이번 API는 저장 방식과 TTL을 변경하지 않는다. 장기 분석에는 별도의 영구 로그 저장소가 필요하다.
조회마다 전체 대화와 Redis 사용량 로그를 읽으므로 대화가 아주 많은 경우 사전 집계가 필요하다.
요청 간 새 로그가 추가되면 페이지 결과나 각 API의 통계가 달라질 수 있다.

### 테스트

기존 의존성 환경에서 실행한다. DB와 Redis 조회는 mock으로 대체한다.

```powershell
uv run python -m unittest discover -s tests -v
```
