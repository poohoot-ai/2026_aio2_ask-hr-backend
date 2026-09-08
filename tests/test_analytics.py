import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from app.deps import CurrentUser, get_current_user
from app.routers import analytics


CID = "00000000-0000-0000-0000-000000000001"
PARAMS = {"start": "2026-09-01T00:00:00Z", "end": "2026-09-03T00:00:00Z"}


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(analytics.router)
        self.app = app
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("owner", "a@b.c", "token")
        self.client = TestClient(app)
        self.db_patch = patch.object(analytics, "supabase")
        self.db = self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.query = MagicMock()
        self.db.table.return_value = self.query
        for method in ("select", "eq", "order", "range"):
            getattr(self.query, method).return_value = self.query
        self.query.execute.return_value.data = [{"id": CID, "title": "test"}]
        self.redis_patch = patch.object(analytics, "r")
        self.redis = self.redis_patch.start()
        self.redis.scan_iter.return_value = []
        self.redis.exists.return_value = False
        self.addCleanup(self.redis_patch.stop)
        self.pipe = self.redis.pipeline.return_value.__enter__.return_value
        self.pipe.execute.return_value = [[
            self.entry("2026-09-01T00:00:00Z", 100, 10),
            self.entry("2026-09-01T23:00:00Z", 300, None),
            self.entry("2026-09-03T00:00:00Z", 900, 90),
            "invalid json",
        ]]

    @staticmethod
    def entry(timestamp, latency, tokens):
        return json.dumps(dict(requested_at=timestamp, latency_ms=latency,
                               prompt_tokens=tokens, response_tokens=tokens, total_tokens=tokens))

    def test_summary_across_all_users(self):
        response = self.client.get("/analytics/summary", params=PARAMS)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metrics"], dict(request_count=2, prompt_tokens=10,
                         response_tokens=10, total_tokens=10, missing_usage_count=1,
                         avg_latency_ms=200.0, p95_latency_ms=300))
        self.assertEqual(body["coverage"]["skipped_invalid_logs"], 1)
        self.assertFalse(body["coverage"]["complete_history"])
        self.query.eq.assert_not_called()
        self.db.postgrest.auth.assert_not_called()
        self.pipe.lrange.assert_called_once_with(f"usage_log:{CID}", 0, -1)

    def test_logs_pagination_and_exclusive_end(self):
        body = self.client.get("/analytics/logs", params={**PARAMS, "limit": 1}).json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["latency_ms"], 300)

    def test_timeseries_fills_empty_days(self):
        response = self.client.get("/analytics/timeseries", params=PARAMS)
        self.assertEqual(response.status_code, 200)
        rows = response.json()["items"]
        self.assertEqual([row["request_count"] for row in rows], [2, 0])
        self.assertIsNone(rows[1]["avg_latency_ms"])

    def test_conversation_metrics(self):
        response = self.client.get("/analytics/conversations", params=PARAMS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["request_count"], 2)

    def test_missing_conversation(self):
        self.query.execute.return_value.data = []
        response = self.client.get("/analytics/logs", params={**PARAMS, "conversation_id": CID})
        self.assertEqual(response.status_code, 404)
        self.redis.pipeline.assert_not_called()

    def test_empty_account(self):
        self.query.execute.return_value.data = []
        body = self.client.get("/analytics/summary", params=PARAMS).json()
        self.assertEqual(body["metrics"]["request_count"], 0)
        self.assertIsNone(body["metrics"]["p95_latency_ms"])

    def test_invalid_inputs(self):
        for params in ({"start": PARAMS["end"], "end": PARAMS["start"]},
                       {"start": "2020-01-01T00:00:00Z", "end": PARAMS["end"]},
                       {"start": "2026-09-01T00:00:00"},
                       {"limit": 201}, {"offset": -1}, {"conversation_id": "bad"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/analytics/logs", params=params).status_code, 422)

    def test_redis_unavailable(self):
        self.pipe.execute.side_effect = ConnectionError("offline")
        self.assertEqual(self.client.get("/analytics/logs", params=PARAMS).status_code, 503)

    def test_authentication_required(self):
        self.app.dependency_overrides.clear()
        self.assertIn(self.client.get("/analytics/summary").status_code, (401, 403))

    def test_any_authenticated_user_can_access_all_endpoints(self):
        self.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            "ordinary-user", "user@example.com", "user-token")
        for endpoint in ("summary", "logs", "timeseries", "conversations"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/analytics/{endpoint}", params=PARAMS)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["coverage"]["scope"], "all_users")
        self.query.eq.assert_not_called()

    def test_deleted_conversation_logs_are_included_once(self):
        self.query.execute.return_value.data = []
        self.redis.scan_iter.return_value = [f"usage_log:{CID}", f"usage_log:{CID}"]
        response = self.client.get("/analytics/summary", params=PARAMS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["request_count"], 2)
        self.assertEqual(response.json()["conversation_count"], 1)
        self.assertEqual(response.json()["coverage"]["scope"], "all_users")

    def test_filter_can_read_redis_only_conversation(self):
        self.query.execute.return_value.data = []
        self.redis.exists.return_value = True
        response = self.client.get("/analytics/logs", params={**PARAMS, "conversation_id": CID})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)

    def test_database_pagination(self):
        self.query.execute.side_effect = [
            type("Result", (), {"data": [{"id": CID, "title": "test"}] * 500})(),
            type("Result", (), {"data": []})(),
        ]
        self.pipe.execute.return_value = [[]] * 100
        response = self.client.get("/analytics/summary", params=PARAMS)
        self.assertEqual(response.status_code, 200)
        self.query.range.assert_any_call(500, 999)


if __name__ == "__main__":
    unittest.main()

