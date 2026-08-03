"""Tests for error map, vault, Mini App auth, paid entitlements, upgrade CTA."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock


class ErrorMapTests(unittest.TestCase):
    def test_classify_and_format(self):
        from v2.core.error_map import classify_error, format_user_error

        self.assertEqual(classify_error("HTTP 502 Bad Gateway"), "rubika_502")
        self.assertEqual(classify_error("اینترنت بین‌الملل در دسترس نیست"), "net_down")
        text = format_user_error("timeout while uploading", lang="fa")
        self.assertIn("❌", text)
        self.assertIn("زمان", text)


class SecretVaultTests(unittest.TestCase):
    def test_seal_open_roundtrip(self):
        from v2.core import secret_vault

        with mock.patch.dict(os.environ, {"SECRET_VAULT_KEY": "unit-test-vault-key"}, clear=False):
            sealed = secret_vault.seal("super-secret-token")
            self.assertTrue(sealed.startswith("enc:"))
            self.assertEqual(secret_vault.open_secret(sealed), "super-secret-token")
            self.assertEqual(secret_vault.open_secret("legacy-plain"), "legacy-plain")


class TelegramWebAppAuthTests(unittest.TestCase):
    def test_validate_init_data_hmac(self):
        from v2.web.telegram_webapp_auth import validate_init_data

        token = "123456:ABC-DEF"
        user = json.dumps({"id": 42, "first_name": "T"}, separators=(",", ":"))
        auth_date = str(int(time.time()))
        pairs = [f"auth_date={auth_date}", f"user={user}"]
        data_check = "\n".join(sorted(pairs))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        init = urllib.parse.urlencode({"auth_date": auth_date, "user": user, "hash": h})
        ok, payload = validate_init_data(init, bot_token=token)
        self.assertTrue(ok)
        self.assertEqual(payload.get("user", {}).get("id"), 42)


class PaidEntitlementsTests(unittest.TestCase):
    def test_grant_star_and_notify_claim(self):
        from queue_db import QueueDB
        from v2.billing.ledger import record_initiated_payment
        from v2.billing.paid_entitlements import (
            claim_pending_entitlement_notifies,
            maybe_grant_plan_after_paid,
        )
        from v2.billing.status import PAID

        td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(td.cleanup)
        db_path = Path(td.name) / "q.sqlite3"
        db = QueueDB(db_path)
        uid = 900001
        with mock.patch("user_entitlements.set_user_tier") as set_tier:
            pid = record_initiated_payment(
                db,
                uid,
                "stub",
                1000,
                currency="IRR",
                authority="auth-test-1",
                idempotency_key=f"test-{uid}-{int(time.time())}",
                metadata={"grant_tier": "star", "grant_days": 7},
            )
            db.update_v2_payment_status(pid, PAID)
            granted = maybe_grant_plan_after_paid(db, pid)
            self.assertTrue(granted)
            self.assertTrue(set_tier.called)
            args = set_tier.call_args[0]
            self.assertEqual(args[0], uid)
            self.assertEqual(args[1], "star")
            self.assertGreater(int(args[2]), int(time.time()))

        pending = claim_pending_entitlement_notifies(db, limit=10)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["telegram_user_id"], uid)
        self.assertEqual(pending[0]["tier"], "star")
        self.assertEqual(claim_pending_entitlement_notifies(db, limit=10), [])
        del db


class UpgradeCtaTests(unittest.TestCase):
    def test_buy_pro_keyboard(self):
        from v2.core.upgrade_cta import buy_pro_keyboard, with_upgrade_hint

        def tr(_uid, key, **_kw):
            return key

        kb = buy_pro_keyboard(1, tr)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "imenu:purchase")
        self.assertIn("/purchase", with_upgrade_hint("limit", lang="en"))


class WizardZipPasswordApiTests(unittest.TestCase):
    def test_zip_password_deps_signature(self):
        from v2.handlers.zip_password_prompt import ZipPasswordPromptDeps

        fields = ZipPasswordPromptDeps.__dataclass_fields__
        self.assertIn("get_waiting_for_password", fields)
        self.assertIn("set_waiting_for_password", fields)


if __name__ == "__main__":
    unittest.main()
