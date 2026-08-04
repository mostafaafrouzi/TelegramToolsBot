"""Gregorian + Solar Hijri calendar helpers + age calculator."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone


def calendar_report(*, lang: str = "fa") -> str:
    now = datetime.now(timezone.utc).astimezone()
    g = now.strftime("%Y-%m-%d %H:%M %Z")
    g_day = now.strftime("%A")
    week = now.isocalendar()[1]
    try:
        import jdatetime

        j = jdatetime.datetime.fromgregorian(datetime=now)
        sh = j.strftime("%Y/%m/%d %H:%M")
        sh_day = j.strftime("%A")
        if lang == "en":
            return (
                f"📅 Calendar\n\n"
                f"Gregorian: {g} ({g_day})\n"
                f"Solar Hijri: {sh} ({sh_day})\n"
                f"ISO week: {week}"
            )
        return (
            f"📅 تقویم\n\n"
            f"میلادی: {g} ({g_day})\n"
            f"شمسی: {sh} ({sh_day})\n"
            f"هفته ISO: {week}"
        )
    except ImportError:
        if lang == "en":
            return f"📅 Calendar\n\nGregorian: {g} ({g_day})\nSolar: (install jdatetime)\nISO week: {week}"
        return (
            f"📅 تقویم\n\nمیلادی: {g} ({g_day})\n"
            f"شمسی: (نصب jdatetime روی سرور)\nهفته ISO: {week}"
        )


def _parse_birth_date(raw: str) -> tuple[bool, date | str]:
    s = (raw or "").strip().replace("-", "/").replace(".", "/")
    m = re.match(r"^(\d{3,4})/(\d{1,2})/(\d{1,2})$", s)
    if not m:
        return False, "bad_date_format"
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    # Solar Hijri years typically 1300–1500
    if 1200 <= y <= 1600:
        try:
            import jdatetime

            g = jdatetime.date(y, mo, d).togregorian()
            return True, g
        except Exception as e:
            return False, str(e)[:200]
    try:
        return True, date(y, mo, d)
    except ValueError as e:
        return False, str(e)


def convert_date(date_str: str, *, lang: str = "fa") -> tuple[bool, str]:
    """Convert Gregorian ↔ Solar Hijri for a single date."""
    ok, parsed = _parse_birth_date(date_str)
    if not ok:
        detail = str(parsed)
        if lang == "en":
            return False, f"Invalid date ({detail}). Use YYYY/MM/DD."
        return False, f"تاریخ نامعتبر ({detail}). فرمت: YYYY/MM/DD."
    g: date = parsed  # type: ignore[assignment]
    try:
        import jdatetime

        j = jdatetime.date.fromgregorian(date=g)
        if lang == "en":
            return True, f"Gregorian: {g.isoformat()}\nSolar Hijri: {j.strftime('%Y/%m/%d')}"
        return True, f"میلادی: {g.isoformat()}\nشمسی: {j.strftime('%Y/%m/%d')}"
    except ImportError:
        return False, "jdatetime_missing" if lang == "en" else "jdatetime نصب نیست."
    except Exception as e:
        return False, str(e)[:200]


def add_days(date_str: str, days: int, *, lang: str = "fa") -> tuple[bool, str]:
    """Add (or subtract) calendar days to a Gregorian/Solar date."""
    from datetime import timedelta

    ok, parsed = _parse_birth_date(date_str)
    if not ok:
        detail = str(parsed)
        if lang == "en":
            return False, f"Invalid date ({detail}). Use YYYY/MM/DD."
        return False, f"تاریخ نامعتبر ({detail}). فرمت: YYYY/MM/DD."
    base: date = parsed  # type: ignore[assignment]
    try:
        days_i = int(days)
    except (TypeError, ValueError):
        return False, "invalid_days" if lang == "en" else "تعداد روز نامعتبر است."
    if abs(days_i) > 36500:
        return False, "days_out_of_range" if lang == "en" else "بازه روزها خیلی بزرگ است."
    result = base + timedelta(days=days_i)
    try:
        import jdatetime

        j = jdatetime.date.fromgregorian(date=result)
        if lang == "en":
            return True, (
                f"📅 Add days\nStart: {base.isoformat()}\nDays: {days_i:+d}\n"
                f"Gregorian: {result.isoformat()}\nSolar: {j.strftime('%Y/%m/%d')}"
            )
        return True, (
            f"📅 افزودن روز\nشروع: {base.isoformat()}\nروز: {days_i:+d}\n"
            f"میلادی: {result.isoformat()}\nشمسی: {j.strftime('%Y/%m/%d')}"
        )
    except ImportError:
        if lang == "en":
            return True, f"📅 Add days\nStart: {base.isoformat()}\n→ {result.isoformat()}"
        return True, f"📅 افزودن روز\nشروع: {base.isoformat()}\n→ {result.isoformat()}"


def date_diff(a: str, b: str, *, lang: str = "fa") -> tuple[bool, str]:
    ok1, d1 = _parse_birth_date(a)
    ok2, d2 = _parse_birth_date(b)
    if not ok1:
        return False, str(d1)
    if not ok2:
        return False, str(d2)
    left: date = d1  # type: ignore[assignment]
    right: date = d2  # type: ignore[assignment]
    if left > right:
        left, right = right, left
    delta = right - left
    years = right.year - left.year
    months = right.month - left.month
    days = right.day - left.day
    if days < 0:
        months -= 1
        from calendar import monthrange

        prev_month = right.month - 1 or 12
        prev_year = right.year if right.month > 1 else right.year - 1
        days += monthrange(prev_year, prev_month)[1]
    if months < 0:
        years -= 1
        months += 12
    if lang == "en":
        return True, (
            f"Date diff\nFrom: {left.isoformat()}\nTo: {right.isoformat()}\n"
            f"{years}y {months}m {days}d · {delta.days} total days"
        )
    return True, (
        f"اختلاف تاریخ\nاز: {left.isoformat()}\nتا: {right.isoformat()}\n"
        f"{years} سال و {months} ماه و {days} روز · مجموع {delta.days} روز"
    )


def age_report(date_str: str, *, lang: str = "fa") -> tuple[bool, str]:
    ok, parsed = _parse_birth_date(date_str)
    if not ok:
        detail = str(parsed)
        if lang == "en":
            return False, f"Invalid date ({detail}). Use YYYY/MM/DD (Gregorian or Solar Hijri)."
        return False, f"تاریخ نامعتبر ({detail}). فرمت: YYYY/MM/DD (میلادی یا شمسی)."
    born: date = parsed  # type: ignore[assignment]
    today = datetime.now(timezone.utc).astimezone().date()
    if born > today:
        return False, "future_date" if lang == "en" else "تاریخ در آینده است."
    years = today.year - born.year
    months = today.month - born.month
    days = today.day - born.day
    if days < 0:
        months -= 1
        # days in previous month
        prev_month = today.month - 1 or 12
        prev_year = today.year if today.month > 1 else today.year - 1
        from calendar import monthrange

        days += monthrange(prev_year, prev_month)[1]
    if months < 0:
        years -= 1
        months += 12
    total_days = (today - born).days
    if lang == "en":
        return True, (
            f"🎂 Age\nBorn: {born.isoformat()}\n"
            f"{years} years, {months} months, {days} days\n"
            f"Total days: {total_days}"
        )
    return True, (
        f"🎂 سن\nتاریخ تولد (میلادی): {born.isoformat()}\n"
        f"{years} سال و {months} ماه و {days} روز\n"
        f"مجموع روزها: {total_days}"
    )
