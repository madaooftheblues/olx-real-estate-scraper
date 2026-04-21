"""
api.py — Flask API layer.
All routes, auth, and request/response handling live here.
"""

from flask import Flask, jsonify, request
from functools import wraps

from app.config import API_KEY, DEBUG, HOST, PORT
from app.scraper import run_scraper

app = Flask(__name__)


# ── Auth middleware ───────────────────────────────────────────────────────────

def require_api_key(f):
    """Decorator: rejects requests without a valid X-API-Key header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if key != API_KEY:
            return jsonify({"success": False, "error": "Unauthorized — invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(_):
    return jsonify({"success": False, "error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "error": str(e)}), 500


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def root():
    """API info — no auth needed."""
    return jsonify({
        "service":  "OLX Real Estate Scraper API",
        "version":  "1.0.0",
        "endpoints": {
            "GET  /health":  "Health check",
            "GET  /config":  "View active config (auth required)",
            "POST /scrape":  "Scrape OLX listings (auth required)",
        }
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check — used by Railway/Render to verify the service is up."""
    return jsonify({"status": "ok"})


@app.route("/config", methods=["GET"])
@require_api_key
def view_config():
    """
    Returns the active runtime config (minus the API key itself).
    Useful for verifying env vars are set correctly on the VPS.
    """
    from app import config as c
    return jsonify({
        "headless":       c.HEADLESS,
        "page_timeout_ms": c.PAGE_TIMEOUT_MS,
        "delay_min":      c.DELAY_MIN,
        "delay_max":      c.DELAY_MAX,
        "scroll_steps":   c.SCROLL_STEPS,
        "max_pages":      c.MAX_PAGES,
        "locale":         c.LOCALE,
        "timezone":       c.TIMEZONE,
        "ref_prefix":     c.REF_PREFIX,
        "ref_padding":    c.REF_PADDING,
        "viewport":       f"{c.VIEWPORT_WIDTH}x{c.VIEWPORT_HEIGHT}",
    })


@app.route("/scrape", methods=["POST"])
@require_api_key
def scrape():
    """
    Scrape OLX for new real estate listings.

    Request body (JSON):
    {
        "urls":      ["https://www.olx.pl/..."],   # required — list of OLX search URLs
        "only_new":  true,                          # optional — filter Nowość only (default: true)
        "ref_start": 0                              # optional — start ref ID counter from N (default: 0)
    }

    Response:
    {
        "success": true,
        "date": "2026-04-21",
        "total_new_listings": 5,
        "listings": [
            {
                "ref_id":  "OLX0001",
                "olx_id":  "1068099639",
                "title":   "Mieszkanie 3 pokoje...",
                "price":   "699 000 zł",
                "area":    "39.35 m²",
                "address": "Kraków, Krowodrza",
                "date":    "19 kwietnia 2026",
                "link":    "https://www.otodom.pl/..."
            }
        ]
    }
    """
    body = request.get_json(silent=True) or {}

    # ── Validate ──────────────────────────────────────────────────────────────
    urls = body.get("urls")
    if not urls or not isinstance(urls, list):
        return jsonify({"success": False, "error": "'urls' must be a non-empty list"}), 400

    for i, u in enumerate(urls):
        if not isinstance(u, str) or not u.startswith("http"):
            return jsonify({"success": False, "error": f"urls[{i}] is not a valid URL"}), 400

    only_new  = bool(body.get("only_new", True))
    ref_start = int(body.get("ref_start", 0))

    # ── Scrape ────────────────────────────────────────────────────────────────
    try:
        result = run_scraper(urls, only_new=only_new, ref_start=ref_start)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
