"""
api.py — Flask API with async job queue.

POST /scrape       → starts a background job, returns job_id immediately
GET  /jobs/<id>    → poll for result (pending / done / failed)
GET  /health       → health check
GET  /config       → active config
GET  /             → API info
"""

import threading
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, jsonify, request

from app.config import API_KEY, DEBUG, HOST, PORT
from app.scraper import run_scraper

app = Flask(__name__)

# ── In-memory job store ───────────────────────────────────────────────────────
# Stores all job results for the lifetime of the process.
# Simple and sufficient for a low-volume daily scraper.
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _set_job(job_id: str, data: dict):
    with _jobs_lock:
        _jobs[job_id] = data


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


# ── Auth ──────────────────────────────────────────────────────────────────────

def require_api_key(f):
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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "OLX Real Estate Scraper API",
        "version": "2.0.0",
        "endpoints": {
            "GET  /health":         "Health check",
            "GET  /config":         "View active config (auth required)",
            "POST /scrape":         "Start a scrape job — returns job_id immediately (auth required)",
            "GET  /jobs/<job_id>":  "Poll job status and retrieve results (auth required)",
            "GET  /jobs":           "List all jobs (auth required)",
        }
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/config", methods=["GET"])
@require_api_key
def view_config():
    from app import config as c
    return jsonify({
        "headless":        c.HEADLESS,
        "page_timeout_ms": c.PAGE_TIMEOUT_MS,
        "delay_min":       c.DELAY_MIN,
        "delay_max":       c.DELAY_MAX,
        "scroll_steps":    c.SCROLL_STEPS,
        "max_pages":       c.MAX_PAGES,
        "locale":          c.LOCALE,
        "timezone":        c.TIMEZONE,
        "ref_prefix":      c.REF_PREFIX,
        "ref_padding":     c.REF_PADDING,
    })


@app.route("/scrape", methods=["POST"])
@require_api_key
def scrape():
    """
    Start a scrape job. Returns immediately with a job_id.
    Poll GET /jobs/<job_id> for the result.

    Request body:
    {
        "urls":      ["https://www.olx.pl/..."],  # required
        "only_new":  true,                         # optional, default true
        "ref_start": 0                             # optional, default 0
    }

    Response (202 Accepted):
    {
        "success":    true,
        "job_id":     "abc123",
        "status":     "pending",
        "poll_url":   "/jobs/abc123",
        "message":    "Job started. Poll /jobs/abc123 for results."
    }
    """
    body = request.get_json(silent=True) or {}

    # Validate
    urls = body.get("urls")
    if not urls or not isinstance(urls, list):
        return jsonify({"success": False, "error": "'urls' must be a non-empty list"}), 400
    for i, u in enumerate(urls):
        if not isinstance(u, str) or not u.startswith("http"):
            return jsonify({"success": False, "error": f"urls[{i}] is not a valid URL"}), 400

    only_new  = bool(body.get("only_new", True))
    ref_start = int(body.get("ref_start", 0))

    # Create job record
    job_id = str(uuid.uuid4())
    _set_job(job_id, {
        "job_id":    job_id,
        "status":    "pending",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "request":   {"urls": urls, "only_new": only_new, "ref_start": ref_start},
        "result":    None,
        "error":     None,
    })

    # Run scraper in background thread
    def _run():
        try:
            result = run_scraper(urls, only_new=only_new, ref_start=ref_start)
            _set_job(job_id, {
                **_get_job(job_id),
                "status":      "done",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "result":      result,
            })
        except Exception as e:
            _set_job(job_id, {
                **_get_job(job_id),
                "status":      "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error":       str(e),
            })

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify({
        "success":  True,
        "job_id":   job_id,
        "status":   "pending",
        "poll_url": f"/jobs/{job_id}",
        "message":  f"Job started. Poll /jobs/{job_id} for results.",
    }), 202


@app.route("/jobs/<job_id>", methods=["GET"])
@require_api_key
def get_job(job_id: str):
    """
    Poll for job result.

    Response while running:
    { "status": "pending", "job_id": "...", "started_at": "..." }

    Response when done:
    { "status": "done", "job_id": "...", "result": { ...scrape output... } }

    Response on failure:
    { "status": "failed", "job_id": "...", "error": "..." }
    """
    job = _get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": f"Job '{job_id}' not found"}), 404
    return jsonify({"success": True, **job})


@app.route("/jobs", methods=["GET"])
@require_api_key
def list_jobs():
    """List all jobs with their status. Useful for debugging."""
    with _jobs_lock:
        summary = [
            {
                "job_id":      j["job_id"],
                "status":      j["status"],
                "started_at":  j["started_at"],
                "finished_at": j["finished_at"],
                "urls":        j["request"]["urls"],
                "total":       j["result"]["total_new_listings"] if j["result"] else None,
            }
            for j in _jobs.values()
        ]
    return jsonify({"success": True, "jobs": summary})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)