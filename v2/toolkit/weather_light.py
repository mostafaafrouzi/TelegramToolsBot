"""Weather, air quality, sun times via Open-Meteo (no API key)."""

from __future__ import annotations

import requests
from typing import Optional, Tuple


def _geocode(city: str) -> tuple[bool, float, float, str]:
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "fa"},
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


def weather_report(city: str) -> tuple[bool, str]:
    ok, lat, lon, label = _geocode(city)
    if not ok:
        return False, label
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max",
                "timezone": "auto",
                "forecast_days": 1,
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
        tmax = (daily.get("temperature_2m_max") or [None])[0]
        tmin = (daily.get("temperature_2m_min") or [None])[0]
        sunrise = (daily.get("sunrise") or [""])[0]
        sunset = (daily.get("sunset") or [""])[0]
        lines = [
            f"🌤 {label}",
            f"الان: {temp}°C · رطوبت {hum}% · باد {wind} km/h · کد {code}",
            f"امروز: min {tmin}°C · max {tmax}°C",
            f"🌅 طلوع: {sunrise}",
            f"🌇 غروب: {sunset}",
        ]
        return True, "\n".join(lines)
    except Exception as e:
        return False, str(e)[:400]


def air_quality_report(city: str) -> tuple[bool, str]:
    ok, lat, lon, label = _geocode(city)
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
        return True, (
            f"🫁 کیفیت هوا — {label}\n"
            f"PM2.5: {cur.get('pm2_5')} · PM10: {cur.get('pm10')} · US AQI: {cur.get('us_aqi')}"
        )
    except Exception as e:
        return False, str(e)[:400]


def currency_convert(amount: float, from_cur: str, to_cur: str) -> tuple[bool, str]:
    fc = (from_cur or "USD").strip().upper()[:3]
    tc = (to_cur or "IRR").strip().upper()[:3]
    try:
        r = requests.get(
            f"https://api.frankfurter.app/latest",
            params={"from": fc, "to": tc, "amount": amount},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        rate = data.get("rates", {}).get(tc)
        if rate is None:
            return False, "rate_unavailable"
        return True, f"{amount} {fc} = {rate} {tc}\nنرخ: 1 {fc} = {float(rate)/amount:.6f} {tc}"
    except Exception as e:
        return False, str(e)[:300]


def recent_earthquakes(limit: int = 5) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson",
            timeout=12,
        )
        r.raise_for_status()
        feats = (r.json().get("features") or [])[:limit]
        if not feats:
            return True, "هیچ زلزلهٔ مهم امروز ثبت نشده."
        lines = []
        for f in feats:
            p = f.get("properties") or {}
            lines.append(f"• M{p.get('mag')} — {p.get('place')} ({p.get('time')})")
        return True, "🌍 زلزله‌های مهم (۲۴h):\n" + "\n".join(lines)
    except Exception as e:
        return False, str(e)[:400]
