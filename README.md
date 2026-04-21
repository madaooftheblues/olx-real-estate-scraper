# OLX Real Estate Scraper API

Scrapes new OLX Poland real estate listings (marked Nowość) and returns
structured JSON. Designed to be called by Make.com as part of an automated
email → scrape → Google Sheets pipeline.

Built with Flask + Playwright + playwright-stealth. Deployed via Docker.

---

## Project structure

```
olx_api/
├── app/
│   ├── __init__.py
│   ├── api.py          # Flask routes, auth, validation
│   ├── config.py       # All settings — driven by environment variables
│   └── scraper.py      # Playwright scraping logic
├── tests/
│   └── test_api.py     # API layer tests (no browser needed)
├── main.py             # Gunicorn entry point
├── Dockerfile          # Container definition
├── coolify.json        # Coolify port + healthcheck config
├── .env.example        # All supported environment variables
├── .dockerignore       # Keeps Docker builds lean
└── requirements.txt
```

---

## Local development

### 1. Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
# Open .env and set OLX_API_KEY to any string for local testing
```

### 3. Run

```bash
python main.py
# API available at http://localhost:8328
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8328/health

# Scrape
curl -X POST http://localhost:8328/scrape \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/krakow/"],
    "only_new": true
  }'
```

### 5. Run tests (no browser needed)

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Deploying to Hetzner + Coolify

### Prerequisites
- Hetzner server running with Coolify installed
- Your code pushed to a GitHub repository

### Step 1 — Create a new resource in Coolify

In your Coolify dashboard:
1. **New Resource → Application**
2. Select **GitHub** and connect your repo
3. Select the branch (e.g. `main`)
4. Build pack: **Dockerfile** (auto-detected)

### Step 2 — Configure the port

In the application settings:
- **Port:** `8328`

Coolify reads `coolify.json` for this, but confirm it's set in the UI.

### Step 3 — Set environment variables

In Coolify → your app → **Environment Variables**, add:

| Key | Value |
|---|---|
| `OLX_API_KEY` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `HEADLESS` | `true` |
| `GUNICORN_TIMEOUT` | `120` |
| `MAX_PAGES` | `0` |

PORT is injected by Coolify automatically — do not set it manually.

### Step 4 — Deploy

Click **Deploy**. Coolify will:
1. Pull your repo
2. Build the Docker image (installs Chromium — takes ~3 minutes first time)
3. Start the container
4. Monitor `/health` every 30 seconds

### Step 5 — Verify

Once deployed, Coolify gives you a public URL like `https://olx-api.yourdomain.com`.

```bash
curl https://olx-api.yourdomain.com/health
# {"status": "ok"}

curl https://olx-api.yourdomain.com/config \
  -H "X-API-Key: your-key"
# Returns active configuration
```

---

## API Reference

### Authentication

All protected endpoints require:
```
X-API-Key: your-secret-key
```

---

### GET /
API info. No auth required.

---

### GET /health
Health check. Used by Coolify to monitor uptime. No auth required.
```json
{"status": "ok"}
```

---

### GET /config
Returns active runtime configuration. Useful for verifying env vars are
set correctly after deployment.
```
X-API-Key: required
```

---

### POST /scrape
Scrape OLX for new listings.

```
X-API-Key: required
Content-Type: application/json
```

**Request:**
```json
{
    "urls": [
        "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/krakow/?min_id=...",
        "https://www.olx.pl/nieruchomosci/domy/sprzedaz/krakow/?min_id=..."
    ],
    "only_new": true,
    "ref_start": 0
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `urls` | list | Yes | — | OLX search URLs to scrape |
| `only_new` | bool | No | `true` | `true` = Nowość only, `false` = all listings |
| `ref_start` | int | No | `0` | Start reference ID numbering from N |

**Response:**
```json
{
    "success": true,
    "date": "2026-04-21",
    "total_new_listings": 3,
    "listings": [
        {
            "ref_id":  "OLX0001",
            "olx_id":  "1068099639",
            "title":   "ul. Cieszyńska, mieszkanie jednopokojowe, 39 m2",
            "price":   "699 000 zł",
            "area":    "39.35 m²",
            "address": "Kraków, Krowodrza",
            "date":    "19 kwietnia 2026",
            "link":    "https://www.otodom.pl/pl/oferta/..."
        }
    ]
}
```

---

## Make.com integration

Add an **HTTP → Make a request** module:

| Setting | Value |
|---|---|
| URL | `https://your-coolify-domain.com/scrape` |
| Method | `POST` |
| Headers | `X-API-Key: your-key` |
| Body type | `Raw (application/json)` |
| Body | `{"urls": ["{{url1}}", "{{url2}}"], "only_new": true}` |

The `listings` array in the response maps directly to Google Sheets rows.

---

## Environment variable reference

All variables can be updated in Coolify's dashboard without touching code.
Changes take effect after redeployment.

| Variable | Default | Description |
|---|---|---|
| `OLX_API_KEY` | — | **Required.** Auth key for all API requests |
| `PORT` | `8328` | Injected by Coolify automatically |
| `DEBUG` | `false` | Enable Flask debug mode (never use in production) |
| `GUNICORN_TIMEOUT` | `120` | Request timeout in seconds — increase if scrapes time out |
| `PAGE_TIMEOUT_MS` | `30000` | Browser page load timeout (milliseconds) |
| `DELAY_MIN` | `1.2` | Minimum delay between actions (seconds) |
| `DELAY_MAX` | `3.5` | Maximum delay between actions (seconds) |
| `SCROLL_STEPS` | `6` | Scroll steps per page |
| `HEADLESS` | `true` | Run browser headless (always true in production) |
| `MAX_PAGES` | `0` | Max pages per URL — 0 = unlimited |
| `REF_PREFIX` | `OLX` | Prefix for reference IDs |
| `REF_PADDING` | `4` | Zero-pad width for reference IDs |
