"""
Progress tracker — persists which numbers have already been processed
so the checker can resume after being stopped.

Thread-safe: all public methods are protected with a lock.
"""

import json
import os
import threading
from typing import Any


class ProgressTracker:
    """
    Keeps a set of already-processed numbers in a JSON file.
    All mutations are serialised with a threading.Lock, and the file
    is saved periodically (every *save_interval* marks) plus on demand
    via ``flush()``.

    Structure of the JSON file:
    {
        "processed": ["968123456", "968789012", ...],
        "valid_count": 42,
        "invalid_count": 18,
        "last_updated": "2026-04-08T12:00:00"
    }
    """

    def __init__(self, progress_file: str, *, save_interval: int = 50) -> None:
        self._path = progress_file
        self._lock = threading.Lock()
        self._processed: set[str] = set()
        self._valid_count = 0
        self._invalid_count = 0
        self._dirty = 0          # how many marks since last save
        self._save_interval = save_interval
        self._load()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_done(self, number: str) -> bool:
        """Return True if this number has already been checked."""
        key = self._normalize(number)
        with self._lock:
            return key in self._processed

    def mark_done(self, number: str, *, valid: bool) -> None:
        """Mark a number as processed. Saves to disk every *save_interval* marks."""
        key = self._normalize(number)
        with self._lock:
            self._processed.add(key)
            if valid:
                self._valid_count += 1
            else:
                self._invalid_count += 1
            self._dirty += 1
            if self._dirty >= self._save_interval:
                self._save_unlocked()
                self._dirty = 0

    def flush(self) -> None:
        """Force an immediate save (call on shutdown)."""
        with self._lock:
            self._save_unlocked()
            self._dirty = 0

    @property
    def total_processed(self) -> int:
        with self._lock:
            return len(self._processed)

    @property
    def valid_count(self) -> int:
        with self._lock:
            return self._valid_count

    @property
    def invalid_count(self) -> int:
        with self._lock:
            return self._invalid_count

    def reset(self) -> None:
        """Wipe all progress (useful for a fresh run)."""
        with self._lock:
            self._processed.clear()
            self._valid_count = 0
            self._invalid_count = 0
            self._dirty = 0
            if os.path.isfile(self._path):
                os.remove(self._path)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(number: str) -> str:
        return number.lstrip("+").strip()

    def _load(self) -> None:
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            self._processed = set(data.get("processed", []))
            self._valid_count = data.get("valid_count", 0)
            self._invalid_count = data.get("invalid_count", 0)
        except (json.JSONDecodeError, OSError):
            # Corrupted file — start fresh
            self._processed = set()

    def _save_unlocked(self) -> None:
        """Write progress to disk.  Caller MUST hold self._lock."""
        from datetime import datetime, timezone

        data = {
            "processed": sorted(self._processed),
            "valid_count": self._valid_count,
            "invalid_count": self._invalid_count,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        # Atomic rename (as atomic as the OS allows)
        os.replace(tmp, self._path)
