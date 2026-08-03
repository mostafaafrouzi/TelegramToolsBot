"""FX conversion: Frankfurter for ISO majors + secondary path for IRR/IRT."""

from __future__ import annotations

import os
from typing import Optional

import requests

_IRR_CODES = frozenset({"IRR", "IRT"})


def _frankfurter(amount: float, fc: str, tc: str) -> tuple[bool, float | str]:
    try:
        r = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": fc, "to": tc, "amount": amount},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        rate = data.get("rates", {}).get(tc)
        if rate is None:
            return False, "rate_unavailable"
        return True, float(rate)
    except Exception as e:
        return False, str(e)[:300]


def _irr_usd_rate() -> tuple[bool, float | str]:
    """Return how many IRR per 1 USD (rial). Prefer open.er-api; optional override URL."""
    custom = (os.getenv("FX_IRR_PROVIDER_URL") or "").strip()
    urls = []
    if custom:
        urls.append(custom)
    urls.append("https://open.er-api.com/v6/latest/USD")
    last_err = "irr_unavailable"
    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            rates = data.get("rates") or {}
            irr = rates.get("IRR") or rates.get("IRT")
            if irr is None:
                last_err = "irr_not_in_rates"
                continue
            val = float(irr)
            # If provider returns toman-scale (~5–6 digits), convert to rial.
            if 1000 < val < 500_000:
                val *= 10
            return True, val
        except Exception as e:
            last_err = str(e)[:300]
    return False, last_err


def currency_convert(
    amount: float,
    from_cur: str,
    to_cur: str,
    *,
    lang: str = "fa",
) -> tuple[bool, str]:
    fc = (from_cur or "USD").strip().upper()[:3]
    tc = (to_cur or "IRR").strip().upper()[:3]
    if fc == tc:
        msg = (
            f"{amount:g} {fc} = {amount:g} {tc}"
            if lang == "en"
            else f"{amount:g} {fc} = {amount:g} {tc}"
        )
        return True, msg

    needs_irr = fc in _IRR_CODES or tc in _IRR_CODES
    if not needs_irr:
        ok, result = _frankfurter(amount, fc, tc)
        if not ok:
            return False, str(result)
        converted = float(result)
        unit = converted / amount if amount else converted
        if lang == "en":
            return True, f"{amount:g} {fc} = {converted:,.4f} {tc}\nRate: 1 {fc} = {unit:,.6f} {tc}"
        return True, f"{amount:g} {fc} = {converted:,.4f} {tc}\nنرخ: 1 {fc} = {unit:,.6f} {tc}"

    # Bridge via USD when IRR involved.
    ok_usd, irr_per_usd = _irr_usd_rate()
    if not ok_usd:
        detail = str(irr_per_usd)
        if lang == "en":
            return False, f"IRR rate unavailable ({detail}). Try USD EUR or set FX_IRR_PROVIDER_URL."
        return False, f"نرخ ریال در دسترس نیست ({detail}). جفت‌های بدون IRR را امتحان کن یا FX_IRR_PROVIDER_URL را تنظیم کن."

    irr_per_usd_f = float(irr_per_usd)

    def to_usd(a: float, code: str) -> tuple[bool, float | str]:
        if code == "USD":
            return True, a
        if code in _IRR_CODES:
            return True, a / irr_per_usd_f
        ok, res = _frankfurter(a, code, "USD")
        return ok, res

    def from_usd(usd: float, code: str) -> tuple[bool, float | str]:
        if code == "USD":
            return True, usd
        if code in _IRR_CODES:
            return True, usd * irr_per_usd_f
        ok, res = _frankfurter(usd, "USD", code)
        return ok, res

    ok1, usd_amt = to_usd(float(amount), fc)
    if not ok1:
        return False, str(usd_amt)
    ok2, converted = from_usd(float(usd_amt), tc)
    if not ok2:
        return False, str(converted)
    converted_f = float(converted)
    unit = converted_f / amount if amount else converted_f
    if lang == "en":
        return True, (
            f"{amount:g} {fc} = {converted_f:,.2f} {tc}\n"
            f"Rate: 1 {fc} ≈ {unit:,.4f} {tc}\n"
            f"(USD/IRR bridge ≈ {irr_per_usd_f:,.0f})"
        )
    return True, (
        f"{amount:g} {fc} = {converted_f:,.2f} {tc}\n"
        f"نرخ تقریبی: 1 {fc} ≈ {unit:,.4f} {tc}\n"
        f"(پل USD/IRR ≈ {irr_per_usd_f:,.0f})"
    )
