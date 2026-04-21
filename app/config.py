"""
config.py — Central configuration for the OLX Scraper API.
All tuneable settings live here. Change values in environment variables,
not in this file.
"""

import os

# ── Security ──────────────────────────────────────────────────────────────────
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
API_KEY = os.environ.get("OLX_API_KEY", "dev-insecure-key-change-me")

# ── Server ────────────────────────────────────────────────────────────────────
HOST  = os.environ.get("HOST", "0.0.0.0")
PORT  = int(os.environ.get("PORT", 8328))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# ── Gunicorn ──────────────────────────────────────────────────────────────────
GUNICORN_TIMEOUT = int(os.environ.get("GUNICORN_TIMEOUT", 120))

# ── Scraper behaviour ─────────────────────────────────────────────────────────
PAGE_TIMEOUT_MS = int(os.environ.get("PAGE_TIMEOUT_MS", 30000))
DELAY_MIN       = float(os.environ.get("DELAY_MIN", 1.5))
DELAY_MAX       = float(os.environ.get("DELAY_MAX", 4.0))
SCROLL_STEPS    = int(os.environ.get("SCROLL_STEPS", 3))   # reduced from 6
HEADLESS        = os.environ.get("HEADLESS", "true").lower() == "true"
MAX_PAGES       = int(os.environ.get("MAX_PAGES", 0))

# ── Stealth / anti-detection ──────────────────────────────────────────────────
# Path where browser cookies are persisted between scrape runs.
# In Docker/Coolify this must be a mounted volume path to survive restarts.
# If left as default (/data/cookies.json) Coolify will need a volume mounted at /data.
COOKIE_FILE = os.environ.get("COOKIE_FILE", "/data/cookies.json")

# OLX homepage — visited before search URLs to simulate natural browsing
WARMUP_URL = os.environ.get("WARMUP_URL", "https://www.olx.pl")

# ── Browser fingerprint ───────────────────────────────────────────────────────
VIEWPORT_WIDTH  = int(os.environ.get("VIEWPORT_WIDTH", 1366))
VIEWPORT_HEIGHT = int(os.environ.get("VIEWPORT_HEIGHT", 768))
USER_AGENT = os.environ.get(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
LOCALE   = os.environ.get("LOCALE", "pl-PL")
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Warsaw")

# ── Reference ID ──────────────────────────────────────────────────────────────
REF_PREFIX  = os.environ.get("REF_PREFIX", "OLX")
REF_PADDING = int(os.environ.get("REF_PADDING", 4))

# ── Extra browser args ────────────────────────────────────────────────────────
BROWSER_ARGS_EXTRA = []