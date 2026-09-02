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