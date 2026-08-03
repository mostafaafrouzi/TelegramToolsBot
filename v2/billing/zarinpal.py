"""Zarinpal payment gateway adapter (request + verify + browser callback).

Requires env ``ZARINPAL_MERCHANT_ID``. Set ``ZARINPAL_CALLBACK_URL`` (HTTPS)
to the Mini App host path ``/billing/zarinpal/callback``.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

from queue_db import QueueDB

from v2.billing.gateway import PaymentIntentResult
from v2.billing.ledger import record_initiated_payment
from v2.billing.status import FAILED, PAID
from v2.billing.webhook import VerifiedPaymentEvent, apply_verified_payment_event

_ZARINPAL_REQUEST = "https://api.zarinpal.com/pg/v4/payment/request.json"
_ZARINPAL_VERIFY = "https://api.zarinpal.com/pg/v4/payment/verify.json"
_ZARINPAL_STARTPAY = "https://www.zarinpal.com/pg/StartPay/{authority}"


def zarinpal_configured() -> bool:
    return bool((os.getenv("ZARINPAL_MERCHANT_ID") or "").strip())


def zarinpal_startpay_url(authority: str) -> str:
    return _ZARINPAL_STARTPAY.format(authority=authority)


class ZarinpalPaymentGateway:
    """Creates Zarinpal payment requests and records ``v2_payments`` rows."""

    def __init__(self, db: QueueDB, *, merchant_id: Optional[str] = None) -> None:
        self._db = db
        self._merchant = (merchant_id or os.getenv("ZARINPAL_MERCHANT_ID") or "").strip()
        self._callback = (os.getenv("ZARINPAL_CALLBACK_URL") or "").strip()
        self._name = "zarinpal"

    def create_payment_intent(
        self,
        telegram_user_id: int,
        amount: int,
        *,
        currency: str = "IRR",
        metadata: Optional[dict] = None,
        idempotency_key: Optional[str] = None,
    ) -> PaymentIntentResult:
        if not self._merchant:
            raise RuntimeError("ZARINPAL_MERCHANT_ID is not configured")
        meta = dict(metadata or {})
        description = str(meta.get("description") or f"tele2rub plan user={telegram_user_id}")[:255]
        callback = self._callback or str(meta.get("callback_url") or "")
        if not callback:
            # Offline/dev path: ledger row without live authority (operator must set callback).
            authority = f"pending-callback-{int(time.time())}-{int(telegram_user_id)}"
            meta["zarinpal_pending_callback"] = True
            pid = record_initiated_payment(
                self._db,
                int(telegram_user_id),
                self._name,
                int(amount),
                currency=currency,
                authority=authority,
                metadata=meta,
                idempotency_key=idempotency_key,
            )
            return PaymentIntentResult(payment_id=pid, gateway=self._name, authority=authority)

        payload = {
            "merchant_id": self._merchant,
            "amount": int(amount),
            "callback_url": callback,
            "description": description,
            "metadata": {"telegram_user_id": str(telegram_user_id)},
        }
        r = requests.post(_ZARINPAL_REQUEST, json=payload, timeout=25)
        data = r.json() if r.content else {}
        errors = data.get("errors")
        result = data.get("data") or {}
        code = result.get("code") if isinstance(result, dict) else None
        authority = (result.get("authority") if isinstance(result, dict) else None) or ""
        if code != 100 or not authority:
            raise RuntimeError(f"zarinpal request failed: code={code} errors={errors}")
        meta["startpay_url"] = zarinpal_startpay_url(authority)
        pid = record_initiated_payment(
            self._db,
            int(telegram_user_id),
            self._name,
            int(amount),
            currency=currency,
            authority=authority,
            metadata=meta,
            idempotency_key=idempotency_key,
        )
        return PaymentIntentResult(payment_id=pid, gateway=self._name, authority=authority)

    def verify_payment(self, authority: str, amount: int) -> tuple[bool, str]:
        if not self._merchant:
            return False, "missing_merchant"
        payload = {
            "merchant_id": self._merchant,
            "amount": int(amount),
            "authority": authority,
        }
        try:
            r = requests.post(_ZARINPAL_VERIFY, json=payload, timeout=25)
            data = r.json() if r.content else {}
        except requests.RequestException as e:
            return False, str(e)[:500]
        result = data.get("data") or {}
        code = result.get("code") if isinstance(result, dict) else None
        # 100 = first verify OK; 101 = already verified (idempotent success).
        if code in (100, 101):
            ref = result.get("ref_id")
            return True, str(ref or "ok")
        return False, f"verify_code={code} errors={data.get('errors')}"


def process_zarinpal_callback(
    db: QueueDB,
    *,
    authority: str,
    status: str,
    gateway: Optional[ZarinpalPaymentGateway] = None,
) -> tuple[bool, str]:
    """Handle browser return from Zarinpal StartPay.

    ``status`` is typically ``OK`` or ``NOK`` from query string.
    Returns ``(ok, human_detail)``.
    """
    auth = (authority or "").strip()
    if not auth:
        return False, "missing_authority"
    row = db.get_v2_payment_by_authority(auth)
    if not row:
        return False, "unknown_authority"
    pid = int(row["id"])
    current = str(row.get("status") or "").strip().lower()
    if current == PAID:
        return True, f"already_paid payment_id={pid}"
    st = (status or "").strip().upper()
    if st != "OK":
        apply_verified_payment_event(
            db,
            VerifiedPaymentEvent(payment_id=pid, status=FAILED, source="zarinpal_callback"),
        )
        return False, f"payment_not_ok status={st or 'empty'} payment_id={pid}"
    gw = gateway or ZarinpalPaymentGateway(db)
    amount = int(row.get("amount") or 0)
    ok, detail = gw.verify_payment(auth, amount)
    if not ok:
        apply_verified_payment_event(
            db,
            VerifiedPaymentEvent(
                payment_id=pid,
                status=FAILED,
                ref_id=detail[:120],
                source="zarinpal_verify",
            ),
        )
        return False, f"verify_failed: {detail}"
    apply_verified_payment_event(
        db,
        VerifiedPaymentEvent(
            payment_id=pid,
            status=PAID,
            ref_id=detail,
            source="zarinpal_verify",
        ),
    )
    return True, f"paid payment_id={pid} ref={detail}"
