"""Gregorian + Solar Hijri calendar helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def calendar_report() -> str:
    now = datetime.now(timezone.utc).astimezone()
    g = now.strftime("%Y-%m-%d %H:%M %Z (%A)")
    try:
        import jdatetime

        j = jdatetime.datetime.fromgregorian(datetime=now)
        sh = j.strftime("%Y/%m/%d %H:%M — %A")
        return f"📅 تقویم\n\nمیلادی: {g}\nشمسی: {sh}"
    except ImportError:
        return f"📅 تقویم\n\nمیلادی: {g}\nشمسی: (نصب jdatetime روی سرور برای نمایش شمسی)"
