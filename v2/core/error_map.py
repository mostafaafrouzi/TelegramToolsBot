"""Map raw worker/provider errors to short user-facing codes + hints."""

from __future__ import annotations

import re
from typing import Optional


# code -> (fa, en, next_action_fa, next_action_en)
_MAP: dict[str, tuple[str, str, str, str]] = {
    "net_down": (
        "اینترنت بین‌الملل در دسترس نیست.",
        "International network is unavailable.",
        "بعداً دوباره تلاش کن یا /netstatus را بزن.",
        "Retry later or check /netstatus.",
    ),
    "rubika_502": (
        "سرور روبیکا موقتاً پاسخ نداد (۵۰۲).",
        "Rubika edge returned a temporary 502.",
        "یک‌بار دیگر بفرست؛ اگر تکرار شد /rubika_connect.",
        "Retry once; if it persists run /rubika_connect.",
    ),
    "rubika_session": (
        "نشست روبیکا منقضی یا نامعتبر است.",
        "Rubika session expired or invalid.",
        "دوباره /rubika_connect بزن.",
        "Run /rubika_connect again.",
    ),
    "bale_size": (
        "حجم فایل برای بله زیاد است.",
        "File is too large for Bale.",
        "فایل کوچک‌تر بفرست یا مقصد دیگری انتخاب کن.",
        "Send a smaller file or pick another destination.",
    ),
    "drive_auth": (
        "دسترسی گوگل درایو معتبر نیست.",
        "Google Drive auth is invalid.",
        "دوباره /drive_connect را انجام بده.",
        "Run /drive_connect again.",
    ),
    "ssh_auth": (
        "ورود SSH رد شد (رمز یا کلید).",
        "SSH authentication failed.",
        "سرور را در منوی SSH بررسی یا دوباره اضافه کن.",
        "Check the SSH server entry or re-add it.",
    ),
    "timeout": (
        "عملیات به‌خاطر اتمام زمان قطع شد.",
        "The operation timed out.",
        "دوباره تلاش کن؛ اگر فایل بزرگ است صبر بیشتری بده.",
        "Retry; large files may need more time.",
    ),
    "generic": (
        "ارسال ناموفق بود.",
        "Transfer failed.",
        "job_id را برای پشتیبانی بفرست یا دوباره تلاش کن.",
        "Send the job_id to support or retry.",
    ),
}


def classify_error(raw: str) -> str:
    s = (raw or "").lower()
    if "502" in s or "bad gateway" in s:
        return "rubika_502"
    if "session" in s and ("invalid" in s or "expire" in s or "auth" in s):
        return "rubika_session"
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "bale" in s and ("size" in s or "too large" in s or "20" in s):
        return "bale_size"
    if "drive" in s and ("auth" in s or "credential" in s or "token" in s or "401" in s or "403" in s):
        return "drive_auth"
    if "ssh" in s or "paramiko" in s or "authentication failed" in s:
        return "ssh_auth"
    if "network" in s or "internet" in s or "connection" in s and "refused" not in s:
        if "بین‌الملل" in (raw or "") or "github.com" in s:
            return "net_down"
    if "بین‌الملل" in (raw or ""):
        return "net_down"
    return "generic"


def format_user_error(raw: str, *, lang: str = "fa") -> str:
    code = classify_error(raw)
    fa, en, na_fa, na_en = _MAP.get(code, _MAP["generic"])
    title = en if lang == "en" else fa
    nxt = na_en if lang == "en" else na_fa
    detail = (raw or "").strip()
    if detail and len(detail) < 180 and detail not in title:
        # Keep a short technical crumb without dumping stack traces.
        detail = re.sub(r"\s+", " ", detail)[:160]
        return f"❌ {title}\n{nxt}\n\n({detail})"
    return f"❌ {title}\n{nxt}"


def worker_status_text(code: str, *, lang: str = "fa", detail: str = "") -> str:
    """Status text for rub worker push_status when using known codes."""
    if code in _MAP:
        fa, en, na_fa, na_en = _MAP[code]
        title = en if lang == "en" else fa
        nxt = na_en if lang == "en" else na_fa
        if detail:
            return f"{title}\n{nxt}\n({detail[:120]})"
        return f"{title}\n{nxt}"
    # Progress / success codes not in error map
    progress = {
        "downloading": ("در حال دانلود…", "Downloading…"),
        "uploading": ("در حال آپلود…", "Uploading…"),
        "done": ("با موفقیت ارسال شد ✅", "Sent successfully ✅"),
        "queued": ("در صف پردازش…", "Queued for processing…"),
    }
    if code in progress:
        fa, en = progress[code]
        return en if lang == "en" else fa
    return detail or code
