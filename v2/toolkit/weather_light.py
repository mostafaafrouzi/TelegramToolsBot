"""Weather, air quality, sun times via Open-Meteo (no API key)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import requests

# Re-export for older imports
from v2.toolkit.fx_light import currency_convert  # noqa: F401

_WMO_FA = {
    0: "آسمان صاف",
    1: "عمدتاً صاف",
    2: "نیمه‌ابری",
    3: "ابری",
    45: "مه",
    48: "مه یخ‌زده",
    51: "باران‌ریزه سبک",
    53: "باران‌ریزه",
    55: "باران‌ریزه شدید",
    61: "باران سبک",
    63: "باران",
    65: "باران شدید",
    71: "برف سبک",
    73: "برف",
    75: "برف شدید",
    80: "رگبار سبک",
    81: "رگبار",
    82: "رگبار شدید",
    95: "رعدوبرق",
    96: "رعدوبرق با تگرگ",
    99: "رعدوبرق شدید با تگرگ",
}

_WMO_EN = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Slight showers",
    81: "Showers",
    82: "Violent showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm with hail",
}


def wmo_label(code: Optional[int], *, lang: str = "fa") -> str:
    if code is None:
        return "?"
    table = _WMO_EN if lang == "en" else _WMO_FA
    return table.get(int(code), f"code {code}")


def _geocode(city: str, *, lang: str = "fa") -> tuple[bool, float, float, str]:
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "fa" if lang != "en" else "en"},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            return False, 0.0, 0.0, "city_not_found"
        row = results[0]
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        label = row.get("name") or city
        country = row.get("country") or ""
        if country:
            label = f"{label}, {country}"
        return True, lat, lon, label
    except Exception as e:
        return False, 0.0, 0.0, str(e)[:300]


def _fmt_sun(iso_s: str) -> str:
    if not iso_s:
        return "—"
    try:
        # Open-Meteo: 2024-01-01T06:30
        if "T" in iso_s:
            return iso_s.split("T", 1)[1][:5]
        return iso_s[:16]
    except Exception:
        return iso_s


def weather_report(city: str, *, lang: str = "fa", forecast_days: int = 3) -> tuple[bool, str]:
    ok, lat, lon, label = _geocode(city, lang=lang)
    if not ok:
        return False, label
    days = max(1, min(int(forecast_days), 5))
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,weather_code",
                "timezone": "auto",
                "forecast_days": days,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        cur = data.get("current") or {}
        daily = data.get("daily") or {}
        temp = cur.get("temperature_2m")
        hum = cur.get("relative_humidity_2m")
        wind = cur.get("wind_speed_10m")
        code = cur.get("weather_code")
        cond = wmo_label(code, lang=lang)
        tmax = (daily.get("temperature_2m_max") or [None])[0]
        tmin = (daily.get("temperature_2m_min") or [None])[0]
        sunrise = _fmt_sun((daily.get("sunrise") or [""])[0])
        sunset = _fmt_sun((daily.get("sunset") or [""])[0])
        uv = (daily.get("uv_index_max") or [None])[0]
        if lang == "en":
            lines = [
                f"🌤 {label}",
                f"Now: {temp}°C · {cond} · humidity {hum}% · wind {wind} km/h",
                f"Today: min {tmin}°C · max {tmax}°C · UV {uv}",
                f"🌅 Sunrise: {sunrise} · 🌇 Sunset: {sunset}",
            ]
        else:
            lines = [
                f"🌤 {label}",
                f"الان: {temp}°C · {cond} · رطوبت {hum}% · باد {wind} km/h",
                f"امروز: min {tmin}°C · max {tmax}°C · UV {uv}",
                f"🌅 طلوع: {sunrise} · 🌇 غروب: {sunset}",
            ]
        dates = daily.get("time") or []
        dmax = daily.get("temperature_2m_max") or []
        dmin = daily.get("temperature_2m_min") or []
        dcodes = daily.get("weather_code") or []
        if len(dates) > 1:
            lines.append("")
            lines.append("پیش‌بینی:" if lang != "en" else "Forecast:")
            for i in range(1, min(len(dates), days)):
                d = dates[i]
                try:
                    d_short = datetime.fromisoformat(d).strftime("%m-%d")
                except Exception:
                    d_short = d
                lines.append(
                    f"  {d_short}: {dmin[i] if i < len(dmin) else '?'}–"
                    f"{dmax[i] if i < len(dmax) else '?'}°C · "
                    f"{wmo_label(dcodes[i] if i < len(dcodes) else None, lang=lang)}"
                )
        return True, "\n".join(lines)
    except Exception as e:
        return False, str(e)[:400]


def air_quality_report(city: str, *, lang: str = "fa") -> tuple[bool, str]:
    ok, lat, lon, label = _geocode(city, lang=lang)
    if not ok:
        return False, label
    try:
        r = requests.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "pm10,pm2_5,us_aqi",
                "timezone": "auto",
            },
            timeout=15,
        )
        r.raise_for_status()
        cur = r.json().get("current") or {}
        if lang == "en":
            return True, (
                f"🫁 Air quality — {label}\n"
                f"PM2.5: {cur.get('pm2_5')} · PM10: {cur.get('pm10')} · US AQI: {cur.get('us_aqi')}"
            )
        return True, (
            f"🫁 کیفیت هوا — {label}\n"
            f"PM2.5: {cur.get('pm2_5')} · PM10: {cur.get('pm10')} · US AQI: {cur.get('us_aqi')}"
        )
    except Exception as e:
        return False, str(e)[:400]


def recent_earthquakes(limit: int = 8, *, min_mag: float = 4.5, lang: str = "fa") -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
            timeout=15,
        )
        r.raise_for_status()
        feats = r.json().get("features") or []
        rows = []
        for f in feats:
            p = f.get("properties") or {}
            g = (f.get("geometry") or {}).get("coordinates") or []
            try:
                mag = float(p.get("mag") or 0)
            except (TypeError, ValueError):
                continue
            if mag < float(min_mag):
                continue
            ts = p.get("time")
            when = "—"
            if ts:
                try:
                    when = datetime.utcfromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M UTC")
                except Exception:
                    when = str(ts)
            depth = g[2] if len(g) >= 3 else None
            depth_s = f"{depth:.0f} km" if isinstance(depth, (int, float)) else "—"
            rows.append((mag, p.get("place") or "?", when, depth_s))
            if len(rows) >= limit:
                break
        if not rows:
            # fallback significant
            r2 = requests.get(
                "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson",
                timeout=12,
            )
            r2.raise_for_status()
            for f in (r2.json().get("features") or [])[:limit]:
                p = f.get("properties") or {}
                ts = p.get("time")
                when = "—"
                if ts:
                    try:
                        when = datetime.utcfromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M UTC")
                    except Exception:
                        pass
                rows.append((p.get("mag"), p.get("place") or "?", when, "—"))
        if not rows:
            return True, ("No M≥{m} quakes in the last day.".format(m=min_mag) if lang == "en" else f"زلزلهٔ M≥{min_mag} در ۲۴ ساعت اخیر ثبت نشد.")
        header = (
            f"🌍 Earthquakes (24h, M≥{min_mag}):"
            if lang == "en"
            else f"🌍 زلزله‌ها (۲۴h، M≥{min_mag}):"
        )
        lines = [header]
        for mag, place, when, depth in rows:
            lines.append(f"• M{mag} — {place}\n  {when} · depth {depth}")
        return True, "\n".join(lines)
    except Exception as e:
        return False, str(e)[:400]
