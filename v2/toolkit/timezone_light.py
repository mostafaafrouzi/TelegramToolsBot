"""Local time / timezone lookup via Open-Meteo geocoding + zoneinfo."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


def _geocode(place: str, *, lang: str = "fa") -> tuple[bool, float, float, str, str]:
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": place, "count": 1, "language": "fa" if lang != "en" else "en"},
            timeout=12,
        )
        r.raise_for_status()
        results = (r.json().get("results") or [])
        if not results:
            return False, 0.0, 0.0, "", "place_not_found"
        row = results[0]
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        label = row.get("name") or place
        country = row.get("country") or ""
        if country:
            label = f"{label}, {country}"
        tz = str(row.get("timezone") or "")
        return True, lat, lon, label, tz
    except Exception as e:
        return False, 0.0, 0.0, "", str(e)[:300]


def timezone_report(place_or_tz: str, *, lang: str = "fa") -> tuple[bool, str]:
    raw = (place_or_tz or "").strip()
    if not raw:
        return False, "empty_place"

    tz_name = ""
    label = raw

    # Direct IANA zone
    if "/" in raw and " " not in raw.strip():
        try:
            ZoneInfo(raw)
            tz_name = raw
            label = raw
        except ZoneInfoNotFoundError:
            tz_name = ""

    if not tz_name:
        ok, _lat, _lon, label, tz_name = _geocode(raw, lang=lang)
        if not ok:
            return False, label if label else tz_name

    if not tz_name:
        return False, "timezone_unknown"

    try:
        zi = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return False, f"unknown_tz:{tz_name}"

    now = datetime.now(zi)
    utc_now = datetime.now(timezone.utc)
    offset = now.utcoffset()
    offset_h = int(offset.total_seconds() // 3600) if offset else 0
    offset_m = int(abs(offset.total_seconds()) % 3600 // 60) if offset else 0
    sign = "+" if offset and offset.total_seconds() >= 0 else "-"
    off_s = f"UTC{sign}{abs(offset_h):02d}:{offset_m:02d}"
    if lang == "en":
        return True, (
            f"🕒 {label}\n"
            f"Zone: {tz_name}\n"
            f"Local: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"Offset: {off_s}\n"
            f"UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    return True, (
        f"🕒 {label}\n"
        f"منطقه: {tz_name}\n"
        f"محلی: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"اختلاف: {off_s}\n"
        f"UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}"
    )
