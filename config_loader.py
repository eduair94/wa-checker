"""
Configuration loader — reads config.ini and exposes typed settings.
If the config file is missing or incomplete, launches an interactive
setup wizard so non-technical users can get going without editing files.
"""

import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE = "config.ini"

# ── Default template ─────────────────────────────────────────────────

_DEFAULT_CONFIG = """\
[api]
api_key = {api_key}
base_url = {base_url}

[rate_limit]
requests_per_second = {rps}
workers = {workers}
max_retries = 3
backoff_start = 1.0

[files]
input_file = {input_file}
valid_output = results/valid.txt
invalid_output = results/invalid.txt
progress_file = results/.progress.json
"""

# ── Dataclasses ──────────────────────────────────────────────────────

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


# ── Interactive setup wizard ─────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    """Prompt user with an optional default value."""
    if default:
        text = input(f"  {prompt} [{default}]: ").strip()
        return text if text else default
    while True:
        text = input(f"  {prompt}: ").strip()
        if text:
            return text
        print("    ⚠  This field is required. Please enter a value.")


def _run_interactive_setup(config_path: str) -> None:
    """Walk the user through creating a config.ini interactively."""
    print("┌──────────────────────────────────────────────┐")
    print("│       ⚙️   First-time Setup Wizard   ⚙️       │")
    print("└──────────────────────────────────────────────┘")
    print()
    print("  Let's get you set up! I'll ask a few questions and")
    print("  create your config file automatically.\n")

    # 1. API key
    print("  ─── Step 1 of 3: API Key ───")
    print("  You need an API key from the WhatsApp Proxy service.")
    print("  (It looks like: ab12cd34-ef56-7890-abcd-1234567890ab)\n")
    api_key = _ask("Paste your API key here")
    print()

    # 2. Input file
    print("  ─── Step 2 of 3: Phone Numbers ───")
    print("  Where are your phone numbers?")
    print("    • Type a filename  (e.g. numbers.txt)")
    print("    • Or paste a URL   (e.g. https://example.com/numbers.txt)\n")
    input_file = _ask("File path or URL", "numbers.txt")
    print()

    # 3. Speed
    print("  ─── Step 3 of 3: Speed ───")
    print("  How fast should it check? (requests per second)")
    print("    • 50  = normal (recommended to start)")
    print("    • 100 = fast   (if you have a good API plan)")
    print("    • 200 = turbo  (may get rate-limited)\n")
    rps_str = _ask("Requests per second", "50")
    try:
        rps = float(rps_str)
    except ValueError:
        rps = 50.0

    # Auto-calculate workers
    workers = max(50, int(rps * 4))

    base_url = "https://whatsapp-proxy.checkleaked.cc"

    # Write the config
    config_text = _DEFAULT_CONFIG.format(
        api_key=api_key,
        base_url=base_url,
        rps=int(rps),
        workers=workers,
        input_file=input_file,
    )
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config_text)

    print("  ─────────────────────────────────────────────")
    print(f"  ✅  Config saved to {config_path}")
    print("  You can edit this file later to change settings.")
    print("  ─────────────────────────────────────────────\n")


def _needs_setup(config_path: str) -> bool:
    """Return True if the config file is missing or has a placeholder key."""
    if not os.path.isfile(config_path):
        return True
    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")
    api_key = parser.get("api", "api_key", fallback="").strip()
    return not api_key or api_key == "YOUR_API_KEY_HERE"


# ── Main loader ──────────────────────────────────────────────────────

def load_config(config_path: str | None = None) -> AppConfig:
    """
    Load and validate config.ini, returning a typed AppConfig.
    If the file is missing or has a placeholder API key, run the
    interactive setup wizard first.
    """
    path = config_path or CONFIG_FILE

    # ── Interactive setup if needed ──
    if _needs_setup(path):
        _run_interactive_setup(path)

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    # --- API section ---
    api_key = parser.get("api", "api_key", fallback="").strip()
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("\n❌  API key is still missing after setup.")
        print("    Open config.ini and set your real API key in the [api] section.\n")
        sys.exit(1)

    base_url = parser.get("api", "base_url", fallback="https://whatsapp-proxy.checkleaked.cc").strip().rstrip("/")

    # --- Rate-limit section ---
    requests_per_second = parser.getfloat("rate_limit", "requests_per_second", fallback=50.0)
    max_retries = parser.getint("rate_limit", "max_retries", fallback=3)
    backoff_start = parser.getfloat("rate_limit", "backoff_start", fallback=1.0)
    workers = parser.getint("rate_limit", "workers", fallback=200)

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
