#!/usr/bin/env python3
"""
WhatsApp Number Checker  v3.0  — async I/O (aiohttp)
=====================================================

Reads a list of phone numbers (from a local file or a URL), checks each one
against the WhatsApp Proxy API using hundreds of concurrent async requests,
and writes the results into two files:

  results/valid.txt   — numbers that exist on WhatsApp (full details)
  results/invalid.txt — numbers that do NOT exist on WhatsApp

Supports resuming: if you stop the script (Ctrl+C) and run it again it will
skip numbers that were already checked.

Usage:
    python check.py                  # normal run
    python check.py --reset          # wipe progress and start fresh
    python check.py --config my.ini  # use a custom config file
    python check.py --workers 200    # override concurrency from CLI
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import signal
import subprocess
import sys
import time

# ── Auto-install missing dependencies ────────────────────────────────
def _ensure_dependencies() -> None:
    """Check that required packages are installed; install them if not."""
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        print("📦  Installing required packages (first time only)…")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "aiohttp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("    ✅  Done!\n")

_ensure_dependencies()

# Force UTF-8 output on Windows (prevents UnicodeEncodeError with cp1252)
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from api_client import ApiClient
from config_loader import AppConfig, load_config
from formatter import format_invalid_line, format_valid_line
from number_loader import load_numbers
from progress_tracker import ProgressTracker

# ── Graceful shutdown ────────────────────────────────────────────────
_shutdown_requested = False


def _request_shutdown() -> None:
    global _shutdown_requested
    if _shutdown_requested:
        print("\n\n⚡  Force quit.")
        os._exit(1)
    _shutdown_requested = True
    print("\n\n⏸  Stopping gracefully… finishing in-flight requests…")


def _handle_signal(signum: int, frame: object) -> None:
    _request_shutdown()


signal.signal(signal.SIGINT, _handle_signal)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _handle_signal)


# ── Pretty helpers ───────────────────────────────────────────────────

def _progress_bar(current: int, total: int, width: int = 30) -> str:
    if total == 0:
        return "[" + "=" * width + "] 100%"
    pct = current / total
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:.1%}"


def _eta(elapsed: float, done: int, remaining: int) -> str:
    if done == 0:
        return "calculating…"
    secs = (elapsed / done) * remaining
    if secs < 60:
        return f"{secs:.0f}s"
    if secs < 3600:
        return f"{secs / 60:.1f}m"
    hrs = secs / 3600
    if hrs < 48:
        return f"{hrs:.1f}h"
    return f"{hrs / 24:.1f}d"


# ── File writer (sync — fast enough for appending lines) ─────────────

def _append_line(filepath: str, line: str) -> None:
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ── Core async logic ─────────────────────────────────────────────────

async def _check_one(
    number: str,
    client: ApiClient,
    tracker: ProgressTracker,
    config: AppConfig,
    semaphore: asyncio.Semaphore,
    stats: dict,
) -> None:
    """Check a single number, respecting the concurrency semaphore."""
    if _shutdown_requested:
        return

    async with semaphore:
        if _shutdown_requested:
            return

        try:
            result = await client.check_number(number)
        except RuntimeError:
            stats["errors"] += 1
            return
        except Exception:
            stats["errors"] += 1
            return

        if result is not None:
            line = format_valid_line(result)
            _append_line(config.files.valid_output, line)
            tracker.mark_done(number, valid=True)
            stats["last_status"] = "✓"
        else:
            line = format_invalid_line(number)
            _append_line(config.files.invalid_output, line)
            tracker.mark_done(number, valid=False)
            stats["last_status"] = "✗"

        stats["checked"] += 1
        stats["last_number"] = number


async def _display_loop(stats: dict) -> None:
    """Dedicated coroutine that redraws the progress line ~4× per second."""
    while not stats["done"]:
        _draw_progress(stats)
        await asyncio.sleep(0.25)
    # Final redraw
    _draw_progress(stats)


def _draw_progress(stats: dict) -> None:
    checked = stats["checked"]
    if checked == 0:
        return
    total_done = stats["already"] + checked
    elapsed = time.monotonic() - stats["start"]
    rps = checked / elapsed if elapsed > 0 else 0
    remaining = stats["pending"] - checked - stats["errors"]
    eta = _eta(elapsed, checked, max(remaining, 0))
    bar = _progress_bar(total_done, stats["total"])
    status = stats.get("last_status", "·")
    number = stats.get("last_number", "")

    line = (
        f"\r  {bar}  {total_done}/{stats['total']}  "
        f"{status} {number}  "
        f"({rps:.1f} req/s · ETA {eta} · {stats['workers']}w)   "
    )
    sys.stdout.write(line)
    sys.stdout.flush()


async def run(config: AppConfig, workers_override: int | None = None) -> None:
    tracker = ProgressTracker(config.files.progress_file)
    numbers = load_numbers(config.files.input_file)

    # Filter out already-processed numbers
    pending = [n for n in numbers if not tracker.is_done(n)]
    already = len(numbers) - len(pending)

    if already > 0:
        print(f"⏩  Resuming — {already} numbers already processed, {len(pending)} remaining")
    if not pending:
        print("\n✅  All numbers have already been checked. Use --reset to start over.\n")
        _print_summary(tracker, numbers)
        return

    num_workers = workers_override or config.rate_limit.workers
    client = ApiClient(config.api, config.rate_limit)
    semaphore = asyncio.Semaphore(num_workers)

    print(f"\n🚀  Starting check of {len(pending)} numbers "
          f"(~{config.rate_limit.requests_per_second:.0f} req/s limit, "
          f"{num_workers} concurrent)\n")

    stats = {
        "checked": 0,
        "errors": 0,
        "already": already,
        "total": len(numbers),
        "pending": len(pending),
        "workers": num_workers,
        "start": time.monotonic(),
        "last_number": "",
        "last_status": "·",
        "done": False,
    }

    # Start the dedicated display-refresh coroutine
    display_task = asyncio.create_task(_display_loop(stats))

    # Launch all tasks — the semaphore caps concurrency
    tasks = []
    for number in pending:
        if _shutdown_requested:
            break
        task = asyncio.create_task(
            _check_one(number, client, tracker, config, semaphore, stats)
        )
        tasks.append(task)

    # Wait for completion (or shutdown)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    # Stop the display loop
    stats["done"] = True
    await display_task

    # Flush tracker to ensure all progress is saved
    tracker.flush()
    await client.close()

    # Final summary
    elapsed = time.monotonic() - stats["start"]
    print(f"\n\n{'=' * 60}")
    if _shutdown_requested:
        print(f"⏸  Paused after {stats['checked']} numbers ({elapsed:.1f}s)")
        print(f"   Run the script again to resume where you left off.")
    else:
        print(f"🏁  Finished in {elapsed:.1f}s ({stats['checked']} checked this run)")
    if stats["errors"]:
        print(f"⚠  {stats['errors']} numbers skipped due to errors")
    avg_rps = stats["checked"] / elapsed if elapsed > 0 else 0
    print(f"📈  Average throughput: {avg_rps:.1f} req/s ({num_workers} concurrent)")
    print(f"{'=' * 60}")
    _print_summary(tracker, numbers)


def _print_summary(tracker: ProgressTracker, numbers: list[str]) -> None:
    print(f"\n📊  Summary:")
    print(f"    Total numbers:  {len(numbers)}")
    print(f"    Processed:      {tracker.total_processed}")
    print(f"    ✅ Valid:        {tracker.valid_count}")
    print(f"    ❌ Invalid:      {tracker.invalid_count}")
    remaining = len(numbers) - tracker.total_processed
    if remaining > 0:
        print(f"    ⏳ Remaining:    {remaining}")
    print()


# ── Entry point ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check phone numbers against the WhatsApp Proxy API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", default="config.ini",
        help="Path to config file (default: config.ini)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe all progress and output files, then start fresh",
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Override the number of concurrent requests (default: from config.ini)",
    )
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════╗")
    print("║   WhatsApp Number Checker  v3.0  ⚡      ║")
    print("║   Async I/O — maximum throughput         ║")
    print("╚══════════════════════════════════════════╝")
    print()

    config = load_config(args.config)

    if args.reset:
        tracker = ProgressTracker(config.files.progress_file)
        tracker.reset()
        for fp in (config.files.valid_output, config.files.invalid_output):
            open(fp, "w", encoding="utf-8").close()
        print("🗑  Progress and output files cleared.\n")

    asyncio.run(run(config, workers_override=args.workers))


if __name__ == "__main__":
    main()
