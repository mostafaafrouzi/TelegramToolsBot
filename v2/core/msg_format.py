"""Shared HTML message formatting for readable bot replies."""

from __future__ import annotations

import html
from typing import Any, Optional, Sequence


def escape(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=False)


def title(icon: str, text: str) -> str:
    icon_s = (icon or "").strip()
    body = escape(text)
    if icon_s:
        return f"<b>{escape(icon_s)} {body}</b>"
    return f"<b>{body}</b>"


def section(text: str) -> str:
    return f"\n<b>{escape(text)}</b>"


def kv(key: str, value: Any, *, bullet: str = "•") -> str:
    return f"{bullet} <b>{escape(key)}</b>: {escape(value)}"


def line(text: str, *, bullet: str = "•") -> str:
    return f"{bullet} {escape(text)}"


def code(s: Any) -> str:
    return f"<code>{escape(s)}</code>"


def italic(s: Any) -> str:
    return f"<i>{escape(s)}</i>"


def change_line(
    d: Optional[float],
    dp: Optional[float],
    dt: str = "",
    *,
    lang: str = "fa",
) -> str:
    if d is None and dp is None:
        return ""
    arrow = "─"
    dt_l = (dt or "").lower()
    if dt_l == "high" or (d is not None and d > 0) or (dp is not None and dp > 0):
        arrow = "▲"
    elif dt_l == "low" or (d is not None and d < 0) or (dp is not None and dp < 0):
        arrow = "▼"
    parts = [arrow]
    if d is not None:
        parts.append(f"{d:+,.4g}" if abs(d) < 1000 else f"{d:+,.0f}")
    if dp is not None:
        parts.append(f"({dp:+.2f}%)")
    label = "Day change" if lang == "en" else "تغییر روز"
    return kv(label, " ".join(parts))


def updated_line(ts: str, *, lang: str = "fa") -> str:
    label = "Updated" if lang == "en" else "به‌روزرسانی"
    return kv(label, ts or "—")


def pre_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    cols = [escape(h) for h in headers]
    widths = [len(c) for c in cols]
    esc_rows: list[list[str]] = []
    for row in rows:
        er = [escape(c) for c in row]
        esc_rows.append(er)
        for i, cell in enumerate(er):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))
            else:
                widths.append(len(cell))

    def fmt(cells: Sequence[str]) -> str:
        parts = []
        for i, w in enumerate(widths):
            cell = cells[i] if i < len(cells) else ""
            parts.append(cell.ljust(w))
        return "  ".join(parts)

    lines = [fmt(cols), fmt(["─" * w for w in widths])]
    for er in esc_rows:
        lines.append(fmt(er))
    return "<pre>" + "\n".join(lines) + "</pre>"


def join(*blocks: str) -> str:
    return "\n".join(b for b in blocks if b)


async def reply_html(message: Any, body: str, *, reply_markup: Any = None) -> Any:
    """Send HTML body; fall back to plain if Telegram rejects entities."""
    try:
        return await message.reply_text(body, parse_mode="html", reply_markup=reply_markup)
    except Exception:
        plain = (
            body.replace("<b>", "")
            .replace("</b>", "")
            .replace("<i>", "")
            .replace("</i>", "")
            .replace("<code>", "")
            .replace("</code>", "")
            .replace("<pre>", "")
            .replace("</pre>", "")
        )
        plain = html.unescape(plain)
        return await message.reply_text(plain, parse_mode=None, reply_markup=reply_markup)
