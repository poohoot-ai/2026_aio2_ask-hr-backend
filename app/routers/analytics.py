"""로그인한 모든 사용자를 위한 전체 Redis 사용량 로그 분석 API."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, Field, ValidationError
from redis.exceptions import RedisError

from app.db import supabase
from app.deps import CurrentUser, get_current_user
from app.redis_client import r

router = APIRouter(prefix="/analytics", tags=["analytics"])
MAX_USAGE_LOGS = 50


class UsageEntry(BaseModel):
    requested_at: AwareDatetime
    latency_ms: int = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    response_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class LogEntry(UsageEntry):
    conversation_id: UUID
    conversation_title: str


class Metrics(BaseModel):
    request_count: int
    prompt_tokens: int
    response_tokens: int
    total_tokens: int
    missing_usage_count: int
    avg_latency_ms: float | None
    p95_latency_ms: int | None


class Coverage(BaseModel):
    source: str = "redis_usage_log"
    scope: str = "all_users"
    max_logs_per_conversation: int = MAX_USAGE_LOGS
    complete_history: bool = False
    timestamp_semantics: str = "logged_at"
    successful_responses_only: bool = True
    skipped_invalid_logs: int = 0


class BaseResult(BaseModel):
    start: datetime
    end: datetime
    coverage: Coverage


class SummaryResult(BaseResult):
    conversation_count: int
    active_conversation_count: int
    metrics: Metrics


class LogsResult(BaseResult):
    total: int
    limit: int
    offset: int
    items: list[LogEntry]


class TimeBucket(Metrics):
    bucket_start: datetime


class TimeseriesResult(BaseResult):
    interval: Literal["hour", "day"]
    timezone: str = "UTC"
    items: list[TimeBucket]


class ConversationMetrics(Metrics):
    conversation_id: UUID
    conversation_title: str


class ConversationsResult(BaseResult):
    total: int
    limit: int
    offset: int
    items: list[ConversationMetrics]


def metrics(logs: list[LogEntry]) -> Metrics:
    latencies = sorted(row.latency_ms for row in logs)
    return Metrics(
        request_count=len(logs),
        prompt_tokens=sum(row.prompt_tokens or 0 for row in logs),
        response_tokens=sum(row.response_tokens or 0 for row in logs),
        total_tokens=sum(row.total_tokens or 0 for row in logs),
        missing_usage_count=sum(any(getattr(row, field) is None for field in
                                    ("prompt_tokens", "response_tokens", "total_tokens"))
                                for row in logs),
        avg_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else None,
        p95_latency_ms=latencies[ceil(len(latencies) * .95) - 1] if latencies else None,
    )


class Dataset:
    def __init__(self, start, end, conversations, logs, skipped):
        self.start, self.end = start, end
        self.conversations, self.logs = conversations, logs
        self.coverage = Coverage(skipped_invalid_logs=skipped)

    def base(self):
        return dict(start=self.start, end=self.end, coverage=self.coverage)


def load_dataset(
    start: AwareDatetime | None = Query(default=None),
    end: AwareDatetime | None = Query(default=None),
    conversation_id: UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
) -> Dataset:
    end = (end or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = (start or end - timedelta(days=30)).astimezone(timezone.utc)
    if start >= end or end - start > timedelta(days=366):
        raise HTTPException(422, "start < end이며 조회 기간은 최대 366일이어야 합니다")

    # 로그인 검증 후 서버 전용 service-role 클라이언트로 전체 대화를 조회한다.
    client = supabase
    conversations = []
    page = 0
    while True:
        query = client.table("conversations").select("id,title").order("id")
        if conversation_id:
            query = query.eq("id", str(conversation_id))
        rows = query.range(page, page + 499).execute().data
        conversations.extend(rows)
        if len(rows) < 500:
            break
        page += 500
    logs, skipped = [], 0
    try:
        # 삭제된 대화의 남은 로그도 포함한다. SCAN의 중복 키는 제거한다.
        known_ids = {row["id"] for row in conversations}
        if conversation_id:
            keys = ([f"usage_log:{conversation_id}"]
                    if r.exists(f"usage_log:{conversation_id}") else [])
        else:
            keys = r.scan_iter(match="usage_log:*", count=100)
        for key in keys:
            if isinstance(key, bytes):
                key = key.decode()
            try:
                log_id = str(UUID(key.removeprefix("usage_log:")))
            except ValueError:
                continue
            if log_id not in known_ids:
                conversations.append({"id": log_id, "title": "삭제되었거나 정보가 없는 대화"})
                known_ids.add(log_id)
        if conversation_id and not conversations:
            raise HTTPException(404, "conversation not found")
        for index in range(0, len(conversations), 100):
            batch = conversations[index:index + 100]
            with r.pipeline(transaction=False) as pipe:
                for conversation in batch:
                    pipe.lrange(f"usage_log:{conversation['id']}", 0, -1)
                results = pipe.execute()
            for conversation, raw_logs in zip(batch, results):
                for raw in raw_logs:
                    try:
                        entry = UsageEntry.model_validate_json(raw)
                    except (ValidationError, ValueError, TypeError):
                        skipped += 1
                        continue
                    if start <= entry.requested_at < end:
                        logs.append(LogEntry(**entry.model_dump(),
                                             conversation_id=conversation["id"],
                                             conversation_title=conversation["title"] or "대화 미지정"))
    except RedisError as exc:
        raise HTTPException(503, "사용량 로그 저장소에 연결할 수 없습니다") from exc
    logs.sort(key=lambda row: (row.requested_at, str(row.conversation_id)), reverse=True)
    return Dataset(start, end, conversations, logs, skipped)


@router.get("/summary", response_model=SummaryResult)
def summary(data: Dataset = Depends(load_dataset)):
    return dict(**data.base(), conversation_count=len(data.conversations),
                active_conversation_count=len({row.conversation_id for row in data.logs}),
                metrics=metrics(data.logs))


@router.get("/logs", response_model=LogsResult)
def logs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
         data: Dataset = Depends(load_dataset)):
    return dict(**data.base(), total=len(data.logs), limit=limit, offset=offset,
                items=data.logs[offset:offset + limit])


@router.get("/timeseries", response_model=TimeseriesResult)
def timeseries(interval: Literal["hour", "day"] = "day",
               data: Dataset = Depends(load_dataset)):
    def floor(value):
        value = value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        return value.replace(hour=0) if interval == "day" else value

    grouped = defaultdict(list)
    for row in data.logs:
        grouped[floor(row.requested_at)].append(row)
    cursor = floor(data.start)
    step = timedelta(days=1) if interval == "day" else timedelta(hours=1)
    items = []
    while cursor < data.end:
        items.append(TimeBucket(bucket_start=cursor, **metrics(grouped[cursor]).model_dump()))
        cursor += step
    return dict(**data.base(), interval=interval, items=items)


@router.get("/conversations", response_model=ConversationsResult)
def conversations(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                  data: Dataset = Depends(load_dataset)):
    grouped = defaultdict(list)
    for row in data.logs:
        grouped[str(row.conversation_id)].append(row)
    items = [ConversationMetrics(conversation_id=row["id"],
                                 conversation_title=row["title"] or "대화 미지정",
                                 **metrics(grouped[row["id"]]).model_dump())
             for row in data.conversations]
    items.sort(key=lambda row: (-row.request_count, str(row.conversation_id)))
    return dict(**data.base(), total=len(items), limit=limit, offset=offset,
                items=items[offset:offset + limit])
