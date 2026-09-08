import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.routers import conversations
from app.schemas import MessageCreate


class ConversationTitleTests(unittest.TestCase):
    def setUp(self):
        self.cid = UUID("00000000-0000-0000-0000-000000000001")
        db_patch = patch.object(conversations, "supabase")
        self.db = db_patch.start()
        self.addCleanup(db_patch.stop)
        self.query = MagicMock()
        self.db.table.return_value = self.query
        for method in ("select", "eq", "order", "limit", "update", "insert"):
            getattr(self.query, method).return_value = self.query

    def test_first_user_message_normalizes_and_limits_title(self):
        self.query.execute.return_value.data = [{"id": "first"}]
        content = "  연차\n 문의  " + "가" * 60
        conversations._update_first_message_title(
            self.cid, {"id": "first", "content": content}
        )
        self.query.update.assert_called_once_with(
            {"title": " ".join(content.split())[:50]}
        )
        self.query.eq.assert_any_call("role", "user")

    def test_later_message_keeps_title(self):
        self.query.execute.return_value.data = [{"id": "first"}]
        conversations._update_first_message_title(
            self.cid, {"id": "second", "content": "후속 질문"}
        )
        self.query.update.assert_not_called()

    @patch.object(conversations, "cache_delete")
    @patch.object(conversations, "_update_first_message_title")
    def test_only_saved_user_messages_update_title(self, update_title, cache_delete):
        self.query.execute.return_value.data = [{"id": "first", "content": "질문"}]
        for role in ("assistant", "system"):
            conversations.create_message(self.cid, MessageCreate(role=role, content="내용"))
        update_title.assert_not_called()
        conversations.create_message(self.cid, MessageCreate(role="user", content="질문"))
        update_title.assert_called_once_with(self.cid, {"id": "first", "content": "질문"})
