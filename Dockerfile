# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── System deps for Playwright/Chromium ──────────────────────────────────────
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    # Core Chromium libs
    libnss3 libnspr4 \
    libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libx11-6 libx11-xcb1 libxcb1 \
    libxext6 libxrender1 \
    # Font support
    fonts-liberation fonts-noto-color-emoji \
    # Audio stub — prevents ALSA warnings crashing the process
    libasound2 \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# ── App setup ─────────────────────────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pin Chromium to a known path for container stability
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium

COPY . .

# ── Health check ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8328}/health || exit 1

# ── Runtime ───────────────────────────────────────────────────────────────────
CMD gunicorn main:app \
    --bind 0.0.0.0:${PORT:-8328} \
    --workers 1 \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --keep-alive 5 \
    --log-level info \
    --access-logfile - \
    --error-logfile -