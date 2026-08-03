"""Admin audience / ops unit tests."""

from __future__ import annotations

import unittest


class AdminAudienceTests(unittest.TestCase):
    def test_resolve_all_and_tier(self):
        from v2.core.admin_audience import resolve_audience

        ids, label = resolve_audience(
            "all",
            list_known_chat_ids=lambda: [1, 2],
            list_activity_user_ids=lambda: [2, 3],
            list_new_user_ids=lambda _d: [],
            list_inactive_user_ids=lambda _d: [],
            list_tier_user_ids=lambda _t: [],
            list_expiring_user_ids=lambda _d: [],
            list_expired_user_ids=lambda: [],
        )
        self.assertEqual(ids, [1, 2, 3])
        self.assertEqual(label, "all_known_and_active")

        ids2, _ = resolve_audience(
            "pro",
            list_known_chat_ids=lambda: [],
            list_activity_user_ids=lambda: [],
            list_new_user_ids=lambda _d: [],
            list_inactive_user_ids=lambda _d: [],
            list_tier_user_ids=lambda t: [9] if t == "pro" else [],
            list_expiring_user_ids=lambda _d: [],
            list_expired_user_ids=lambda: [],
        )
        self.assertEqual(ids2, [9])


class MenuAdminBroadcastTests(unittest.TestCase):
    def test_broadcast_menu_builds(self):
        from v2.core import menu_engine

        def tr(_uid, key, **_kw):
            return key

        kb = menu_engine.build_admin_broadcast_menu(1, tr)
        self.assertTrue(kb.keyboard)


if __name__ == "__main__":
    unittest.main()
