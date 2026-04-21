# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── System deps for Playwright/Chromium ──────────────────────────────────────
# Install all Chromium system dependencies in one layer
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libx11-xcb1 libx11-6 \
    fonts-liberation fonts-noto-color-emoji \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# ── App setup ─────────────────────────────────────────────────────────────────
WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium — done after pip so browser cache survives code changes
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium

# Copy application code
COPY . .

# ── Health check — Coolify uses this to verify the container is up ────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8328}/health || exit 1

# ── Runtime ───────────────────────────────────────────────────────────────────
# PORT is injected by Coolify automatically
# GUNICORN_TIMEOUT can be overridden in Coolify env vars
CMD gunicorn main:app \
    --bind 0.0.0.0:${PORT:-8328} \
    --workers 1 \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --keep-alive 5 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
