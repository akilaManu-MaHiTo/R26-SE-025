"""Copilot session TTL and activity tracking."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_ROOT = Path(__file__).resolve().parents[3]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from Gradex_AI_Server.app.viva_copilot.session_store import SessionStore, session_ttl_seconds


class SessionTtlTests(unittest.TestCase):
    def test_default_ttl_is_four_hours(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(session_ttl_seconds(), 14400.0)

    def test_expired_session_is_removed_on_get(self):
        store = SessionStore()
        with patch(
            "Gradex_AI_Server.app.viva_copilot.session_store.session_ttl_seconds",
            return_value=60.0,
        ):
            session = store.create()
            session.last_activity_at = time.time() - 120.0
            self.assertIsNone(store.get(session.session_id))

    def test_active_session_is_returned(self):
        store = SessionStore()
        session = store.create()
        found = store.get(session.session_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.session_id, session.session_id)

    def test_is_expired_respects_ttl(self):
        store = SessionStore()
        with patch(
            "Gradex_AI_Server.app.viva_copilot.session_store.session_ttl_seconds",
            return_value=60.0,
        ):
            session = store.create()
            self.assertFalse(session.is_expired())
            session.last_activity_at = time.time() - 120.0
            self.assertTrue(session.is_expired())

    def test_expire_if_idle_removes_session(self):
        store = SessionStore()
        with patch(
            "Gradex_AI_Server.app.viva_copilot.session_store.session_ttl_seconds",
            return_value=60.0,
        ):
            session = store.create()
            session.last_activity_at = time.time() - 120.0
            self.assertTrue(store.expire_if_idle(session.session_id))
            self.assertIsNone(store.get(session.session_id))


if __name__ == "__main__":
    unittest.main()
