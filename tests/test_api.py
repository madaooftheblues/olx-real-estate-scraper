"""
test_api.py — API layer tests. No browser launched.
Run: python -m pytest tests/ -v
"""

import os
import pytest

os.environ["OLX_API_KEY"] = "test-key"

from app.api import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

AUTH    = {"X-API-Key": "test-key", "Content-Type": "application/json"}
NO_AUTH = {"Content-Type": "application/json"}


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "endpoints" in r.get_json()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_config(client):
    r = client.get("/config", headers=AUTH)
    assert r.status_code == 200
    data = r.get_json()
    assert "headless" in data and "max_pages" in data


def test_auth_required_scrape(client):
    r = client.post("/scrape", headers=NO_AUTH, json={"urls": ["https://olx.pl"]})
    assert r.status_code == 401

def test_auth_required_jobs(client):
    r = client.get("/jobs", headers=NO_AUTH)
    assert r.status_code == 401

def test_wrong_key(client):
    r = client.post("/scrape",
                    headers={"X-API-Key": "wrong", "Content-Type": "application/json"},
                    json={"urls": ["https://olx.pl"]})
    assert r.status_code == 401


def test_missing_urls(client):
    r = client.post("/scrape", headers=AUTH, json={})
    assert r.status_code == 400
    assert "urls" in r.get_json()["error"]


def test_invalid_url(client):
    r = client.post("/scrape", headers=AUTH, json={"urls": ["not-a-url"]})
    assert r.status_code == 400


def test_scrape_returns_job_id(client):
    """POST /scrape should return 202 with a job_id immediately."""
    r = client.post("/scrape", headers=AUTH,
                    json={"urls": ["https://www.olx.pl/nieruchomosci/"]})
    assert r.status_code == 202
    data = r.get_json()
    assert data["status"] == "pending"
    assert "job_id" in data
    assert "poll_url" in data


def test_poll_job(client):
    """After starting a job, GET /jobs/<id> should return its record."""
    r = client.post("/scrape", headers=AUTH,
                    json={"urls": ["https://www.olx.pl/nieruchomosci/"]})
    job_id = r.get_json()["job_id"]

    r2 = client.get(f"/jobs/{job_id}", headers=AUTH)
    assert r2.status_code == 200
    data = r2.get_json()
    assert data["job_id"] == job_id
    assert data["status"] in ("pending", "done", "failed")


def test_job_not_found(client):
    r = client.get("/jobs/nonexistent-id", headers=AUTH)
    assert r.status_code == 404


def test_list_jobs(client):
    r = client.get("/jobs", headers=AUTH)
    assert r.status_code == 200
    assert "jobs" in r.get_json()


def test_404(client):
    r = client.get("/nonexistent")
    assert r.status_code == 404