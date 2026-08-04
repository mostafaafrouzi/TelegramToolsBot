"""Free-form live FX / gold calculator: '100000 تومان', '1 سکه امامی', '50 USD'."""

from __future__ import annotations

import re
from typing import Optional

from v2.core import msg_format as mf
from v2.toolkit import fx_light
from v2.toolkit.market_board import PROVIDER_LABEL_EN, PROVIDER_LABEL_FA, _LABELS_FA

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# Alias → canonical code used by fx_light / quote cache
_ALIASES: dict[str, str] = {
    "ریال": "IRR",
    "rial": "IRR",
    "irr": "IRR",
    "تومان": "IRT",
    "تومن": "IRT",
    "toman": "IRT",
    "tmn": "IRT",
    "irt": "IRT",
    "دلار": "USD",
    "dollar": "USD",
    "usd": "USD",
    "یورو": "EUR",
    "euro": "EUR",
    "eur": "EUR",
    "پوند": "GBP",
    "gbp": "GBP",
    "ین": "JPY",
    "yen": "JPY",
    "jpy": "JPY",
    "یوان": "CNY",
    "یوآن": "CNY",
    "cny": "CNY",
    "تتر": "USDT",
    "usdt": "USDT",
    "درهم": "AED",
    "aed": "AED",
    "لیر": "TRY",
    "try": "TRY",
    "انس": "XAU_OZ",
    "انس طلا": "XAU_OZ",
    "طلا": "GOLD18",
    "طلای18": "GOLD18",
    "طلای ۱۸": "GOLD18",
    "گرم طلا": "GOLD18",
    "سکه": "SEKEE",
    "سکه امامی": "SEKEE",
    "امامی": "SEKEE",
    "بهار": "SEKEB",
    "سکه بهار": "SEKEB",
    "نیم سکه": "NIM",
    "نیم": "NIM",
    "ربع سکه": "ROB",
    "ربع": "ROB",
    "گرمی": "GERAMI",
    "مثقال": "MESGHAL",
    "نقره": "XAG_OZ",
}

_DEFAULT_TARGETS = ("IRT", "IRR", "USD", "EUR", "GBP", "CNY", "USDT", "GOLD18", "SEKEE")


def _norm_digits(s: str) -> str:
    return (s or "").translate(_FA_DIGITS)


def resolve_unit(token: str) -> Optional[str]:
    t = (token or "").strip().lower()
    if not t:
        return None
    if t in _ALIASES:
        return _ALIASES[t]
    # multi-word keys
    for k, v in _ALIASES.items():
        if " " in k and k in t:
            return v
    u = t.upper()
    if len(u) in (3, 4) and u.isalpha():
        return u
    return None


def parse_amount_unit(raw: str) -> tuple[bool, float | str, str]:
    """Parse '100000 تومان' or '50 USD' → (ok, amount, code)."""
    s = _norm_digits(raw).strip().replace(",", "").replace("٬", "").replace("،", "")
    if not s:
        return False, "empty", ""
    # Prefer longest unit match at end
    lower = s.lower()
    best_key = ""
    best_code = ""
    for k, code in sorted(_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if lower.endswith(k) or lower.endswith(" " + k):
            if len(k) > len(best_key):
                best_key = k
                best_code = code
    if best_key:
        num_s = s[: -len(best_key)].strip()
        try:
            amount = float(num_s.replace(" ", ""))
        except ValueError:
            return False, "bad_amount", ""
        return True, amount, best_code
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*([A-Za-z\u0600-\u06FF]+)?$", s)
    if not m:
        return False, "bad_format", ""
    amount = float(m.group(1))
    unit_tok = (m.group(2) or "IRT").strip()
    code = resolve_unit(unit_tok) or unit_tok.upper()
    return True, amount, code


def _rial_of(amount: float, code: str) -> tuple[bool, float | str]:
    ok, bundle = fx_light.get_irr_rate_bundle()
    if not ok or not isinstance(bundle, fx_light.RateBundle):
        return False, str(bundle)
    c = code.upper()
    # Gold / metal from quote cache (price in IRR unless USD unit)
    q = fx_light._quote_cache.get(c)
    if q is not None:
        if getattr(q, "unit", "IRR") == "USD":
            usd_rate = bundle.rates.get("USD")
            if not usd_rate:
                return False, "usd_rate_missing"
            return True, amount * float(q.price) * float(usd_rate)
        return True, amount * float(q.price)
    if c in fx_light._gold_cache:
        return True, amount * float(fx_light._gold_cache[c])
    return fx_light._amount_to_rial(amount, c, bundle)


def _from_rial(rial: float, code: str) -> tuple[bool, float | str]:
    ok, bundle = fx_light.get_irr_rate_bundle()
    if not ok or not isinstance(bundle, fx_light.RateBundle):
        return False, str(bundle)
    c = code.upper()
    q = fx_light._quote_cache.get(c)
    if q is not None:
        price = float(q.price)
        if price <= 0:
            return False, "bad_price"
        if getattr(q, "unit", "IRR") == "USD":
            usd_rate = bundle.rates.get("USD")
            if not usd_rate:
                return False, "usd_rate_missing"
            return True, rial / (price * float(usd_rate))
        return True, rial / price
    if c in fx_light._gold_cache:
        p = float(fx_light._gold_cache[c])
        if p <= 0:
            return False, "bad_price"
        return True, rial / p
    return fx_light._rial_to_amount(rial, c, bundle)


def _label(code: str, lang: str) -> str:
    if lang == "en":
        return code
    if code == "IRR":
        return "ریال"
    if code in ("IRT", "TMN"):
        return "تومان"
    return _LABELS_FA.get(code, code)


def calculate_report(raw: str, *, lang: str = "fa", targets: tuple[str, ...] | None = None) -> tuple[bool, str]:
    ok, amount_or_err, code = parse_amount_unit(raw)
    if not ok:
        if lang == "en":
            return False, "Send like: 100000 toman · 50 USD · 1 sekkee"
        return False, "مثال: ۱۰۰۰۰۰ تومان · ۵۰ دلار · ۱ سکه امامی · ۱۰ گرم طلا"
    amount = float(amount_or_err)
    ok_r, rial_or_err = _rial_of(amount, code)
    if not ok_r:
        return False, str(rial_or_err)
    rial = float(rial_or_err)
    dests = list(targets or _DEFAULT_TARGETS)
    if code.upper() in dests:
        dests = [d for d in dests if d != code.upper()]
    # Always show both IRR and IRT when source is one of them
    lines = []
    for dest in dests:
        ok_d, val = _from_rial(rial, dest)
        if not ok_d:
            continue
        v = float(val)
        if dest in ("IRR",):
            txt = f"{v:,.0f} {_label(dest, lang)}"
        elif dest in ("IRT", "TMN"):
            txt = f"{v:,.0f} {_label(dest, lang)}"
        elif dest in ("XAU_OZ", "XAG_OZ", "GOLD18", "SEKEE", "SEKEB", "NIM", "ROB", "GERAMI", "MESGHAL"):
            txt = f"{v:,.4g} {_label(dest, lang)}"
        else:
            txt = f"{v:,.4f} {_label(dest, lang)}"
        lines.append(mf.kv(_label(dest, lang), txt, icon="→"))

    ok_b, bundle = fx_light.get_irr_rate_bundle()
    src = PROVIDER_LABEL_FA if lang != "en" else PROVIDER_LABEL_EN
    ts = ""
    if ok_b and isinstance(bundle, fx_light.RateBundle):
        if bundle.market == "free_market":
            src = PROVIDER_LABEL_FA if lang != "en" else PROVIDER_LABEL_EN
        ts = fx_light._fmt_ts(bundle.fetched_at, lang)

    head = (
        mf.title("🧮", "FX calculator")
        if lang == "en"
        else mf.title("🧮", "ماشین‌حساب ارز و طلا")
    )
    src_line = mf.kv(
        "Amount" if lang == "en" else "مبلغ",
        f"{amount:g} {_label(code, lang)}",
        icon="💰",
    )
    blocks = [head, src_line, mf.section("Equals" if lang == "en" else "معادل")]
    blocks.extend(lines or [mf.line("no rates" if lang == "en" else "نرخی در دسترس نیست")])
    blocks.append(mf.kv("Market" if lang == "en" else "بازار", src, icon="🏛"))
    if ts:
        blocks.append(mf.updated_line(ts, lang=lang))
    return True, mf.join(*blocks)
