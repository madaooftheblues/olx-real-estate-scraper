"""
config.py — Central configuration for the OLX Scraper API.
All tuneable settings live here. Change values here, nowhere else.
"""

import os

# ── Security ────────────────────────────────────────────────────────────────
# Set this as an environment variable on your VPS. Never hardcode it.
# Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
API_KEY = os.environ.get("OLX_API_KEY", "dev-insecure-key-change-me")

# ── Server ───────────────────────────────────────────────────────────────────
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8000))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# ── Scraper behaviour ────────────────────────────────────────────────────────
# How long to wait for a page to load (milliseconds)
PAGE_TIMEOUT_MS = int(os.environ.get("PAGE_TIMEOUT_MS", 30000))

# Human-like delay range between actions (seconds)
DELAY_MIN = float(os.environ.get("DELAY_MIN", 1.2))
DELAY_MAX = float(os.environ.get("DELAY_MAX", 3.5))

# Scroll steps per page (more = slower, more human-like)
SCROLL_STEPS = int(os.environ.get("SCROLL_STEPS", 6))

# Whether to run browser in headless mode (always True in production)
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"

# Max pages to scrape per URL (safety cap — 0 = unlimited)
MAX_PAGES = int(os.environ.get("MAX_PAGES", 0))

# ── Browser fingerprint ───────────────────────────────────────────────────────
VIEWPORT_WIDTH  = int(os.environ.get("VIEWPORT_WIDTH", 1366))
VIEWPORT_HEIGHT = int(os.environ.get("VIEWPORT_HEIGHT", 768))
USER_AGENT = os.environ.get(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
LOCALE      = os.environ.get("LOCALE", "pl-PL")
TIMEZONE    = os.environ.get("TIMEZONE", "Europe/Warsaw")

# ── Reference ID ─────────────────────────────────────────────────────────────
# Prefix for generated reference IDs e.g. OLX0001
REF_PREFIX = os.environ.get("REF_PREFIX", "OLX")
REF_PADDING = int(os.environ.get("REF_PADDING", 4))  # zero-pad width

# ── Gunicorn ──────────────────────────────────────────────────────────────────
# Timeout in seconds — must be longer than your slowest expected scrape run
# Scraping 2 URLs across 2 pages each typically takes 60-90s
GUNICORN_TIMEOUT = int(os.environ.get("GUNICORN_TIMEOUT", 120))

# ── Extra browser args (add custom flags as needed) ───────────────────────────
BROWSER_ARGS_EXTRA = []
