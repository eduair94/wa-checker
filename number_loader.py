"""
Number loader — reads phone numbers from a local file or a remote URL.
Returns a deduplicated, cleaned list.
"""

from __future__ import annotations

import re
import sys

import requests

_DIGIT_RE = re.compile(r"[^\d+]")


def _clean_number(raw: str) -> str | None:
    """
    Strip whitespace, remove non-digit chars (except leading +), and
    return None for obviously invalid entries.
    """
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        return None

    # If a line has pipe-separated fields (like the export format), take only the first field
    if "|" in raw:
        raw = raw.split("|")[0].strip()

    # Preserve leading +, strip everything else that isn't a digit
    has_plus = raw.startswith("+")
    digits = _DIGIT_RE.sub("", raw)
    if not digits:
        return None

    # Minimum realistic phone number length
    if len(digits.lstrip("+")) < 7:
        return None

    return f"+{digits.lstrip('+')}" if has_plus else f"+{digits}"


def load_numbers(source: str) -> list[str]:
    """
    Load phone numbers from *source*.

    source can be:
    - A local file path (e.g. "numbers.txt")
    - An HTTP/HTTPS URL (e.g. "https://example.com/numbers.txt")

    Returns a list of unique, cleaned phone numbers in the order they appear.
    """
    raw_lines: list[str] = []

    if source.startswith("http://") or source.startswith("https://"):
        print(f"📥  Downloading number list from URL...")
        try:
            resp = requests.get(source, timeout=60)
            resp.raise_for_status()
            raw_lines = resp.text.splitlines()
            print(f"    ✅  Downloaded {len(raw_lines)} lines")
        except requests.RequestException as exc:
            print(f"\n❌  Failed to download {source}: {exc}")
            sys.exit(1)
    else:
        try:
            with open(source, "r", encoding="utf-8") as f:
                raw_lines = f.readlines()
            print(f"📂  Loaded {len(raw_lines)} lines from {source}")
        except FileNotFoundError:
            print(f"\n❌  Input file not found: {source}")
            print("    Make sure the file exists or use a URL in config.ini [files] input_file.\n")
            sys.exit(1)

    # Clean and deduplicate while preserving order
    seen: set[str] = set()
    numbers: list[str] = []
    for line in raw_lines:
        cleaned = _clean_number(line)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            numbers.append(cleaned)

    print(f"📋  {len(numbers)} unique phone numbers to check")
    return numbers
