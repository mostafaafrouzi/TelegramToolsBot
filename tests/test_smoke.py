"""Minimal smoke tests (stdlib unittest — no pytest required)."""

from __future__ import annotations

import unittest


class ConfirmStateTests(unittest.TestCase):
    def test_pending_confirm_roundtrip(self):
        from v2.handlers.confirm_state import (
            get_pending_confirm,
            pop_pending_confirm,
            set_pending_confirm,
        )

        uid = 424242
        pop_pending_confirm(uid)
        set_pending_confirm(uid, {"type": "local_file", "path": "/tmp/x.bin"})
        task = get_pending_confirm(uid)
        self.assertIsNotNone(task)
        self.assertEqual(task.get("type"), "local_file")
        popped = pop_pending_confirm(uid)
        self.assertEqual(popped.get("path"), "/tmp/x.bin")
        self.assertIsNone(get_pending_confirm(uid))


class MenuEngineTests(unittest.TestCase):
    def test_resolve_ssh_add_help(self):
        from v2.core import menu_engine

        def tr(_uid, key, **_kw):
            return {
                "btn_ssh_add_help": "➕ افزودن سرور",
                "btn_tool_google": "🔎 Google",
            }.get(key, key)

        mapped = menu_engine.resolve_reply_button_route(
            "➕ افزودن سرور", 1, tr, menu_section="ssh"
        )
        self.assertEqual(mapped, "/ssh_add_help")


class CloudflareClientTests(unittest.TestCase):
    def test_list_zones_rows_shape_on_failure(self):
        from v2.cloudflare_client import list_zones_rows

        ok, rows = list_zones_rows("")
        self.assertFalse(ok)
        self.assertIsInstance(rows, str)


class BillingGatewayTests(unittest.TestCase):
    def test_zarinpal_configured_flag(self):
        import os

        from v2.billing import zarinpal_configured

        prev = os.environ.pop("ZARINPAL_MERCHANT_ID", None)
        try:
            self.assertFalse(zarinpal_configured())
            os.environ["ZARINPAL_MERCHANT_ID"] = "x" * 36
            self.assertTrue(zarinpal_configured())
        finally:
            if prev is None:
                os.environ.pop("ZARINPAL_MERCHANT_ID", None)
            else:
                os.environ["ZARINPAL_MERCHANT_ID"] = prev


class BaleConnectGuardTests(unittest.TestCase):
    def test_already_connected_has_return_in_source(self):
        from pathlib import Path

        src = Path(__file__).resolve().parents[1] / "v2" / "handlers" / "provider_connect_wizards.py"
        text = src.read_text(encoding="utf-8")
        # Guard: after bale_already_connected reply there must be an immediate return.
        idx = text.find("bale_already_connected")
        self.assertGreater(idx, 0)
        window = text[idx : idx + 180]
        self.assertIn("return", window)


class ZarinpalCallbackTests(unittest.TestCase):
    def test_unknown_authority_fails(self):
        from queue_db import QueueDB
        from v2.billing.zarinpal import process_zarinpal_callback

        ok, detail = process_zarinpal_callback(
            QueueDB(), authority="no-such-authority-xyz", status="OK"
        )
        self.assertFalse(ok)
        self.assertIn("unknown_authority", detail)


class CloudflareWriteApiTests(unittest.TestCase):
    def test_create_requires_token(self):
        from v2.cloudflare_client import create_dns_record, delete_dns_record

        ok, detail = create_dns_record("", "zone", type_="A", name="x", content="1.1.1.1")
        self.assertFalse(ok)
        self.assertEqual(detail, "missing_token")
        ok2, detail2 = delete_dns_record("", "zone", "rec")
        self.assertFalse(ok2)
        self.assertEqual(detail2, "missing_token")


class MiniappApiTests(unittest.TestCase):
    def test_unknown_action(self):
        from v2.web.miniapp_api import dispatch_miniapp_api

        status, ctype, body = dispatch_miniapp_api("/miniapp/api/nope", "")
        self.assertEqual(status, 404)
        self.assertIn("json", ctype)
        self.assertIn(b"unknown_action", body)


if __name__ == "__main__":
    unittest.main()
