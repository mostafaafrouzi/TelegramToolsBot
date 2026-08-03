"""FX conversion: Iranian free-market IRR rates + Frankfurter for ISO majors."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

_IRR_CODES = frozenset({"IRR", "IRT", "TMN"})
_CACHE_TTL_SEC = 300
_TGJU_URL = "https://call.tgju.org/ajax.json"
_ERAPI_URL = "https://open.er-api.com/v6/latest/USD"
_NOBITEX_URL = "https://api.nobitex.ir/market/stats"

_cache: dict[str, Any] = {"ts": 0.0, "bundle": None}


@dataclass(frozen=True)
class RateBundle:
    """IRR (rial) per 1 unit of foreign currency."""

    rates: dict[str, float]
    source: str
    market: str  # free_market | custom | official
    fetched_at: float


def _parse_price(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(",", "").replace("٬", "").replace(" ", "")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_rial(val: float, *, prefer_toman_band: bool = True) -> float:
    """Normalize provider number to Iranian rial.

    Free-market USD is typically >500k rial. Values in the classic toman band
    (1k..500k) are multiplied by 10.
    """
    if prefer_toman_band and 1_000 < val < 500_000:
        return val * 10.0
    return val


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


def _tgju_pick(current: dict, *keys: str) -> Optional[float]:
    for key in keys:
        node = current.get(key)
        if isinstance(node, dict):
            p = _parse_price(node.get("p") or node.get("price"))
        else:
            p = _parse_price(node)
        if p and p > 0:
            return p
    return None


def _fetch_tgju_bundle() -> Optional[RateBundle]:
    try:
        r = requests.get(_TGJU_URL, timeout=12)
        r.raise_for_status()
        data = r.json()
        current = data.get("current") if isinstance(data, dict) else None
        if not isinstance(current, dict):
            current = data if isinstance(data, dict) else {}
        usd_raw = _tgju_pick(current, "price_dollar_rl", "price_dollar_dt", "price_dollar_sm")
        eur_raw = _tgju_pick(current, "price_eur", "price_eur_ex")
        gbp_raw = _tgju_pick(current, "price_gbp")
        usdt_raw = _tgju_pick(current, "usdt-irr", "price_usdt")
        if not usd_raw:
            return None
        usd = _to_rial(usd_raw, prefer_toman_band=True)
        rates: dict[str, float] = {"USD": usd}
        if eur_raw:
            rates["EUR"] = _to_rial(eur_raw, prefer_toman_band=True)
        if gbp_raw:
            rates["GBP"] = _to_rial(gbp_raw, prefer_toman_band=True)
        if usdt_raw:
            usdt = _to_rial(usdt_raw, prefer_toman_band=True)
            # If USDT looks like toman while USD is already rial, scale up.
            if usd > 500_000 and usdt < usd * 0.4:
                usdt *= 10.0
            # Outlier guard: keep ≈ USD free market.
            if abs(usdt - usd) / usd > 0.35:
                usdt = usd
            rates["USDT"] = usdt
        else:
            rates["USDT"] = usd
        return RateBundle(
            rates=rates,
            source="TGJU",
            market="free_market",
            fetched_at=time.time(),
        )
    except Exception:
        return None


def _fetch_nobitex_usdt_rial() -> Optional[float]:
    try:
        r = requests.get(_NOBITEX_URL, timeout=12)
        r.raise_for_status()
        stats = (r.json() or {}).get("stats") or {}
        for key in ("USDTIRT", "USDT-rls", "USDTIRT".lower()):
            node = stats.get(key) or stats.get(key.upper())
            if not isinstance(node, dict):
                continue
            latest = _parse_price(node.get("latest") or node.get("bestSell"))
            if latest and latest > 0:
                # Nobitex IRT pairs are usually toman.
                return _to_rial(latest, prefer_toman_band=True)
        return None
    except Exception:
        return None


def _fetch_custom_bundle() -> Optional[RateBundle]:
    custom = (os.getenv("FX_IRR_PROVIDER_URL") or "").strip()
    if not custom:
        return None
    try:
        r = requests.get(custom, timeout=15)
        r.raise_for_status()
        data = r.json()
        rates_in = data.get("rates") if isinstance(data, dict) else None
        if not isinstance(rates_in, dict):
            return None
        irr = _parse_price(rates_in.get("IRR") or rates_in.get("IRT"))
        if not irr or irr <= 0:
            return None
        usd_irr = _to_rial(irr, prefer_toman_band=True)
        out = {"USD": usd_irr, "USDT": usd_irr}
        for code in ("EUR", "GBP"):
            v = _parse_price(rates_in.get(code))
            if v and v > 0:
                # If provider gives foreign→IRR already large, keep; else treat as FX vs USD.
                if v > 1000:
                    out[code] = _to_rial(v, prefer_toman_band=True)
        return RateBundle(
            rates=out,
            source="FX_IRR_PROVIDER_URL",
            market="custom",
            fetched_at=time.time(),
        )
    except Exception:
        return None


def _fetch_erapi_bundle() -> Optional[RateBundle]:
    try:
        r = requests.get(_ERAPI_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        rates_in = data.get("rates") or {}
        irr = _parse_price(rates_in.get("IRR") or rates_in.get("IRT"))
        if not irr or irr <= 0:
            return None
        usd_irr = _to_rial(float(irr), prefer_toman_band=True)
        out = {"USD": usd_irr, "USDT": usd_irr}
        return RateBundle(
            rates=out,
            source="open.er-api.com",
            market="official",
            fetched_at=time.time(),
        )
    except Exception:
        return None


def get_irr_rate_bundle(*, force_refresh: bool = False) -> tuple[bool, RateBundle | str]:
    """Cascade: TGJU free market → custom URL → official er-api."""
    now = time.time()
    cached = _cache.get("bundle")
    if (
        not force_refresh
        and isinstance(cached, RateBundle)
        and now - float(_cache.get("ts") or 0) < _CACHE_TTL_SEC
    ):
        return True, cached

    bundle = _fetch_tgju_bundle()
    if bundle:
        # Optional Nobitex refinement for USDT when reachable.
        nb = _fetch_nobitex_usdt_rial()
        if nb and nb > 0:
            rates = dict(bundle.rates)
            rates["USDT"] = nb
            bundle = RateBundle(
                rates=rates,
                source=f"{bundle.source}+Nobitex",
                market="free_market",
                fetched_at=bundle.fetched_at,
            )
    if not bundle:
        bundle = _fetch_custom_bundle()
    if not bundle:
        bundle = _fetch_erapi_bundle()
    if not bundle:
        return False, "irr_unavailable"

    _cache["ts"] = now
    _cache["bundle"] = bundle
    return True, bundle


def _irr_usd_rate() -> tuple[bool, float | str]:
    """Backward-compatible helper: IRR per 1 USD (rial)."""
    ok, bundle = get_irr_rate_bundle()
    if not ok or not isinstance(bundle, RateBundle):
        return False, str(bundle)
    usd = bundle.rates.get("USD")
    if not usd:
        return False, "usd_missing"
    return True, float(usd)


def clear_fx_cache() -> None:
    _cache["ts"] = 0.0
    _cache["bundle"] = None


def _fmt_ts(ts: float, lang: str) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts))
    except Exception:
        return "-"


def _display_code(code: str) -> str:
    c = code.upper()
    if c in ("IRT", "TMN"):
        return "IRT(toman)"
    return c


def _amount_to_rial(amount: float, code: str, bundle: RateBundle) -> tuple[bool, float | str]:
    c = code.upper()
    if c == "IRR":
        return True, amount
    if c in ("IRT", "TMN"):
        return True, amount * 10.0
    rate = bundle.rates.get(c)
    if rate:
        return True, amount * rate
    if c == "USD":
        return False, "usd_rate_missing"
    # Bridge via USD using Frankfurter then IRR.
    ok, usd_amt = _frankfurter(amount, c, "USD")
    if not ok:
        return False, usd_amt
    usd_rate = bundle.rates.get("USD")
    if not usd_rate:
        return False, "usd_rate_missing"
    return True, float(usd_amt) * usd_rate


def _rial_to_amount(rial: float, code: str, bundle: RateBundle) -> tuple[bool, float | str]:
    c = code.upper()
    if c == "IRR":
        return True, rial
    if c in ("IRT", "TMN"):
        return True, rial / 10.0
    rate = bundle.rates.get(c)
    if rate:
        return True, rial / rate
    usd_rate = bundle.rates.get("USD")
    if not usd_rate:
        return False, "usd_rate_missing"
    usd = rial / usd_rate
    if c == "USD":
        return True, usd
    ok, out = _frankfurter(usd, "USD", c)
    return ok, out


def currency_convert(
    amount: float,
    from_cur: str,
    to_cur: str,
    *,
    lang: str = "fa",
) -> tuple[bool, str]:
    fc = (from_cur or "USD").strip().upper()
    tc = (to_cur or "IRR").strip().upper()
    if fc == "TMN":
        fc = "IRT"
    if tc == "TMN":
        tc = "IRT"
    # Keep ISO-3 for Frankfurter; allow USDT.
    if fc not in _IRR_CODES and fc != "USDT":
        fc = fc[:3]
    if tc not in _IRR_CODES and tc != "USDT":
        tc = tc[:3]

    if fc == tc:
        return True, f"{amount:g} {_display_code(fc)} = {amount:g} {_display_code(tc)}"

    needs_irr = fc in _IRR_CODES or tc in _IRR_CODES or fc == "USDT" or tc == "USDT"
    if not needs_irr:
        ok, result = _frankfurter(amount, fc, tc)
        if not ok:
            return False, str(result)
        converted = float(result)
        unit = converted / amount if amount else converted
        if lang == "en":
            return True, (
                f"💱 Currency convert\n\n"
                f"{amount:g} {fc} = {converted:,.4f} {tc}\n"
                f"Rate: 1 {fc} = {unit:,.6f} {tc}\n\n"
                f"Source: Frankfurter"
            )
        return True, (
            f"💱 تبدیل ارز\n\n"
            f"{amount:g} {fc} = {converted:,.4f} {tc}\n"
            f"نرخ: 1 {fc} = {unit:,.6f} {tc}\n\n"
            f"منبع: Frankfurter"
        )

    ok_b, bundle_or_err = get_irr_rate_bundle()
    if not ok_b or not isinstance(bundle_or_err, RateBundle):
        detail = str(bundle_or_err)
        if lang == "en":
            return False, (
                f"IRR free-market rate unavailable ({detail}). "
                "Try USD/EUR without IRR or set FX_IRR_PROVIDER_URL."
            )
        return False, (
            f"نرخ بازار آزاد ریال در دسترس نیست ({detail}). "
            "جفت‌های بدون IRR را امتحان کن یا FX_IRR_PROVIDER_URL را تنظیم کن."
        )
    bundle = bundle_or_err

    ok1, rial_amt = _amount_to_rial(float(amount), fc, bundle)
    if not ok1:
        return False, str(rial_amt)
    ok2, converted = _rial_to_amount(float(rial_amt), tc, bundle)
    if not ok2:
        return False, str(converted)

    converted_f = float(converted)
    unit = converted_f / amount if amount else converted_f
    usd_irr = bundle.rates.get("USD") or 0.0
    toman_per_usd = usd_irr / 10.0 if usd_irr else 0.0
    src_line_fa = f"منبع: {bundle.source}"
    src_line_en = f"Source: {bundle.source}"
    if bundle.market == "official":
        src_line_fa += " (بین‌بانکی/رسمی — ممکن است با بازار آزاد فرق داشته باشد)"
        src_line_en += " (official/interbank — may differ from free market)"
    elif bundle.market == "free_market":
        src_line_fa += " (بازار آزاد ایران)"
        src_line_en += " (Iran free market)"
    ts = _fmt_ts(bundle.fetched_at, lang)

    if lang == "en":
        return True, (
            f"💱 Currency convert\n\n"
            f"{amount:g} {_display_code(fc)} = {converted_f:,.2f} {_display_code(tc)}\n"
            f"Rate: 1 {_display_code(fc)} ≈ {unit:,.4f} {_display_code(tc)}\n\n"
            f"USD free market ≈ {usd_irr:,.0f} IRR ({toman_per_usd:,.0f} toman)\n"
            f"{src_line_en}\n"
            f"Updated: {ts}"
        )
    return True, (
        f"💱 تبدیل ارز\n\n"
        f"{amount:g} {_display_code(fc)} = {converted_f:,.2f} {_display_code(tc)}\n"
        f"نرخ: 1 {_display_code(fc)} ≈ {unit:,.4f} {_display_code(tc)}\n\n"
        f"دلار آزاد ≈ {usd_irr:,.0f} ریال ({toman_per_usd:,.0f} تومان)\n"
        f"{src_line_fa}\n"
        f"به‌روزرسانی: {ts}"
    )
