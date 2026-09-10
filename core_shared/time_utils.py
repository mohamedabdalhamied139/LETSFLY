"""Shared authoritative table/round duration helpers."""
from __future__ import annotations
from datetime import datetime, timezone

def parse_timestamp(value):
    if not value:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None

def format_duration(seconds: float, lang: str = "ar") -> str:
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    if lang == "en":
        parts = []
        if days:
            parts.append(f"{days} day" if days == 1 else f"{days} days")
        if hours:
            parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
        if minutes:
            parts.append(f"{minutes} minute" if minutes == 1 else f"{minutes} minutes")
        if not parts and secs:
            parts.append(f"{secs} second" if secs == 1 else f"{secs} seconds")
        return ", ".join(parts) if parts else "0 seconds"

    parts = []
    def arabic_count(n, one, two, plural, singular_after_ten=None):
        if n == 1:
            return one
        if n == 2:
            return two
        if 3 <= n <= 10:
            return f"{n} {plural}"
        return f"{n} {singular_after_ten or plural}"
    if days:
        parts.append(arabic_count(days, "يوم", "يومان", "أيام", "يوم"))
    if hours:
        parts.append(arabic_count(hours, "ساعة", "ساعتان", "ساعات", "ساعة"))
    if minutes:
        parts.append(arabic_count(minutes, "دقيقة", "دقيقتان", "دقائق", "دقيقة"))
    if not parts and secs:
        parts.append(arabic_count(secs, "ثانية", "ثانيتان", "ثواني", "ثانية"))
    return " و".join(parts) if parts else "0 ثانية"
