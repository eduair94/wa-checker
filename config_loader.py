"""
Configuration loader — reads config.ini and exposes typed settings.
"""

import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE = "config.ini"


@dataclass(frozen=True)
class ApiConfig:
    api_key: str
    base_url: str


@dataclass(frozen=True)
class RateLimitConfig:
    requests_per_second: float
    max_retries: int
    backoff_start: float
    workers: int


@dataclass(frozen=True)
class FilesConfig:
    input_file: str
    valid_output: str
    invalid_output: str
    progress_file: str


@dataclass(frozen=True)
class AppConfig:
    api: ApiConfig
    rate_limit: RateLimitConfig
    files: FilesConfig


def load_config(config_path: str | None = None) -> AppConfig:
    """Load and validate config.ini, returning a typed AppConfig."""
    path = config_path or CONFIG_FILE

    if not os.path.isfile(path):
        print(f"\n❌  Config file not found: {path}")
        print("    Please copy config.ini.example to config.ini and fill in your API key.\n")
        sys.exit(1)

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    # --- API section ---
    api_key = parser.get("api", "api_key", fallback="").strip()
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("\n❌  API key is missing or still set to the placeholder.")
        print("    Open config.ini and set your real API key in the [api] section.\n")
        sys.exit(1)

    base_url = parser.get("api", "base_url", fallback="https://whatsapp-proxy.checkleaked.cc").strip().rstrip("/")

    # --- Rate-limit section ---
    requests_per_second = parser.getfloat("rate_limit", "requests_per_second", fallback=3.0)
    max_retries = parser.getint("rate_limit", "max_retries", fallback=5)
    backoff_start = parser.getfloat("rate_limit", "backoff_start", fallback=2.0)
    workers = parser.getint("rate_limit", "workers", fallback=10)

    # --- Files section ---
    input_file = parser.get("files", "input_file", fallback="numbers.txt").strip()
    valid_output = parser.get("files", "valid_output", fallback="results/valid.txt").strip()
    invalid_output = parser.get("files", "invalid_output", fallback="results/invalid.txt").strip()
    progress_file = parser.get("files", "progress_file", fallback="results/.progress.json").strip()

    # Ensure output directories exist
    for file_path in (valid_output, invalid_output, progress_file):
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        api=ApiConfig(api_key=api_key, base_url=base_url),
        rate_limit=RateLimitConfig(
            requests_per_second=requests_per_second,
            max_retries=max_retries,
            backoff_start=backoff_start,
            workers=workers,
        ),
        files=FilesConfig(
            input_file=input_file,
            valid_output=valid_output,
            invalid_output=invalid_output,
            progress_file=progress_file,
        ),
    )
