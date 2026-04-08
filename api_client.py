"""
WhatsApp Proxy API client — fully asynchronous with aiohttp.

Uses a non-blocking async rate limiter and connection pooling for
maximum throughput.  Designed to be shared across hundreds of
concurrent coroutines.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp

from config_loader import ApiConfig, RateLimitConfig


class AsyncRateLimiter:
    """
    Non-blocking token-dispatch rate limiter for asyncio.

    Uses an ``asyncio.Lock`` so that ``await asyncio.sleep()`` yields
    control to the event loop instead of blocking a thread.  Adapts
    dynamically when 429s are received.
    """

    def __init__(self, requests_per_second: float) -> None:
        self._lock = asyncio.Lock()
        self._base_rps = requests_per_second
        self._current_rps = requests_per_second
        self._min_interval = 1.0 / requests_per_second
        self._last_request_time = 0.0

    async def acquire(self) -> None:
        """Wait until the next request slot is available (non-blocking)."""
        async with self._lock:
            now = time.monotonic()
            delta = self._min_interval - (now - self._last_request_time)
            if delta > 0:
                await asyncio.sleep(delta)
            self._last_request_time = time.monotonic()

    def slow_down(self) -> None:
        """Halve throughput after a 429."""
        self._current_rps = max(0.5, self._current_rps / 2)
        self._min_interval = 1.0 / self._current_rps

    def speed_up(self) -> None:
        """Gradually recover towards the configured RPS."""
        if self._current_rps < self._base_rps:
            self._current_rps = min(self._base_rps, self._current_rps * 1.1)
            self._min_interval = 1.0 / self._current_rps

    @property
    def current_rps(self) -> float:
        return self._current_rps


class ApiClient:
    """
    Async wrapper around the WhatsApp Proxy API.

    Responsibilities:
    - Enforce rate-limits locally before each request.
    - Retry with exponential back-off on 429 / transient errors.
    - Return a clean dict or None (for invalid numbers).
    """

    _RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, api_cfg: ApiConfig, rl_cfg: RateLimitConfig) -> None:
        self._base_url = api_cfg.base_url
        self._api_key = api_cfg.api_key
        self._rate_limiter = AsyncRateLimiter(rl_cfg.requests_per_second)
        self._max_retries = rl_cfg.max_retries
        self._backoff_start = rl_cfg.backoff_start
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=0,            # no per-host connection cap
                ttl_dns_cache=300,  # cache DNS for 5 min
                keepalive_timeout=30,
            )
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "x-rapidapi-key": self._api_key,
                    "Accept": "application/json",
                },
            )
        return self._session

    async def check_number(self, number: str) -> dict[str, Any] | None:
        """
        Query /number/{number}.

        Returns:
            dict  – full API payload when the number exists on WhatsApp.
            None  – when the number does NOT exist.

        Raises:
            RuntimeError – after exhausting all retries.
        """
        clean = number.lstrip("+").strip()
        url = f"{self._base_url}/number/{clean}"

        session = await self._get_session()
        backoff = self._backoff_start
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            await self._rate_limiter.acquire()

            try:
                async with session.get(url) as resp:
                    status = resp.status

                    if status == 429:
                        retry_after = float(
                            resp.headers.get("Retry-After", backoff)
                        )
                        self._rate_limiter.slow_down()
                        await asyncio.sleep(retry_after)
                        backoff = min(backoff * 2, 60)
                        continue

                    if status in self._RETRYABLE_STATUSES:
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 60)
                        continue

                    # Successful slot — speed limiter back up
                    self._rate_limiter.speed_up()

                    # 4xx = invalid / not found
                    if 400 <= status < 500:
                        return None

                    try:
                        data: dict[str, Any] = await resp.json(
                            content_type=None
                        )
                    except (ValueError, aiohttp.ContentTypeError):
                        return None

                    if data.get("error") or data.get("exists") is False:
                        return None

                    return data

            except asyncio.TimeoutError:
                last_error = TimeoutError(f"Timeout on attempt {attempt}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            except aiohttp.ClientError as exc:
                last_error = exc
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue

        raise RuntimeError(
            f"Failed after {self._max_retries} retries for {number}: {last_error}"
        )

    @property
    def current_rps(self) -> float:
        return self._rate_limiter.current_rps

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
