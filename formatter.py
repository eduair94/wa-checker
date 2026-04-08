"""
Formatter — converts an API response dict into the same one-line
pipe-delimited format used by the TypeScript export_country.ts script.

Example output:
+96891234567 | name: Ahmed | about: Hello | pic: yes | img: https://whatsapp-db.checkleaked.com/96891234567.jpg | added: 2026-03-15 10:22:00 | face: Young man | tags: person, smile | people: [male/age 20-25] | quality: high
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_NEWLINE_RE = re.compile(r"[\r\n]+")


def _clean(text: str) -> str:
    """Collapse newlines/CRs into spaces and strip pipe chars to keep one-line format."""
    return _NEWLINE_RE.sub(" ", text).replace("|", "/").strip()


def _fmt_date(value: Any) -> str:
    """Format a date value (ISO string or dict with $date) into a compact string."""
    if not value:
        return ""
    # The API may return {"$date": "..."} or a plain ISO string
    if isinstance(value, dict) and "$date" in value:
        value = value["$date"]
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value
    return str(value)


def _fmt_people(people: list[dict[str, Any]] | None) -> str:
    """Summarise faceAnalysis.people into a compact semicolon-separated string."""
    if not people:
        return ""
    summaries: list[str] = []
    for p in people:
        parts: list[str] = []
        if p.get("gender"):
            parts.append(p["gender"])
        age_min = p.get("ageMin")
        age_max = p.get("ageMax")
        age = p.get("age")
        if age_min is not None and age_max is not None:
            parts.append(f"age {age_min}-{age_max}")
        elif age is not None:
            parts.append(f"age {age}")
        if p.get("ethnicity"):
            parts.append(p["ethnicity"])
        if p.get("emotion"):
            parts.append(p["emotion"])
        if p.get("hasGlasses"):
            parts.append("glasses")
        if p.get("hasBeard"):
            parts.append("beard")
        if parts:
            summaries.append("/".join(parts))
    return "; ".join(summaries)


def format_valid_line(data: dict[str, Any]) -> str:
    """
    Turn a full API response dict into a single pipe-delimited line.
    Always starts with the phone number prefixed with '+'.
    """
    number = str(data.get("number", data.get("phone", ""))).lstrip("+")
    parts: list[str] = [f"+{number}"]

    # Core fields
    pushname = data.get("pushname") or data.get("notifyName")
    if pushname:
        parts.append(f"name: {_clean(pushname)}")
    about = data.get("about")
    if about:
        parts.append(f"about: {_clean(about)}")
    device_count = data.get("deviceCount")
    if device_count is not None:
        parts.append(f"devices: {device_count}")
    has_img = data.get("hasUrlImage")
    if has_img is not None:
        parts.append(f"pic: {'yes' if has_img else 'no'}")
    if number:
        parts.append(f"img: https://whatsapp-db.checkleaked.com/{number}.jpg")
    date_val = data.get("date")
    if date_val:
        parts.append(f"added: {_fmt_date(date_val)}")

    # Face analysis
    fa = data.get("faceAnalysis")
    if fa and isinstance(fa, dict):
        desc = fa.get("description")
        if desc:
            parts.append(f"face: {_clean(desc)}")
        tags = fa.get("tags")
        if tags and isinstance(tags, list) and len(tags) > 0:
            parts.append(f"tags: {', '.join(str(t) for t in tags)}")
        people_summary = _fmt_people(fa.get("people"))
        if people_summary:
            parts.append(f"people: [{people_summary}]")
        quality = fa.get("imageQuality")
        if quality:
            parts.append(f"quality: {quality}")

    # Business profile
    bp = data.get("businessProfile")
    if bp and isinstance(bp, dict):
        bp_desc = bp.get("description")
        if bp_desc:
            parts.append(f"biz: {_clean(bp_desc)}")
        cat = bp.get("category")
        if cat:
            parts.append(f"category: {cat}")
        addr = bp.get("address")
        if addr:
            parts.append(f"address: {_clean(addr)}")
        email = bp.get("email")
        if email:
            parts.append(f"email: {email}")
        web = bp.get("website")
        if web:
            if isinstance(web, list):
                parts.append(f"web: {', '.join(web)}")
            else:
                parts.append(f"web: {web}")

    return " | ".join(parts)


def format_invalid_line(number: str, reason: str = "") -> str:
    """One-line entry for the invalid-numbers file."""
    clean = number.lstrip("+").strip()
    line = f"+{clean}"
    if reason:
        line += f" | reason: {_clean(reason)}"
    return line
