"""
test_api.py — Local tests you can run before deploying.
Tests the API layer without launching a real browser.

Run with:  python -m pytest tests/ -v
"""

import json
import os
import pytest

os.environ["OLX_API_KEY"] = "test-key"

from app.api import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

HEADERS = {"X-API-Key": "test-key", "Content-Type": "application/json"}


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.get_json()
    assert "endpoints" in data


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_auth_required(client):
    r = client.post("/scrape", json={"urls": ["https://olx.pl"]})
    assert r.status_code == 401


def test_wrong_api_key(client):
    r = client.post("/scrape",
                    headers={"X-API-Key": "wrong", "Content-Type": "application/json"},
                    json={"urls": ["https://olx.pl"]})
    assert r.status_code == 401


def test_missing_urls(client):
    r = client.post("/scrape", headers=HEADERS, json={})
    assert r.status_code == 400
    assert "urls" in r.get_json()["error"]


def test_invalid_url(client):
    r = client.post("/scrape", headers=HEADERS, json={"urls": ["not-a-url"]})
    assert r.status_code == 400


def test_config_endpoint(client):
    r = client.get("/config", headers=HEADERS)
    assert r.status_code == 200
    data = r.get_json()
    assert "headless" in data
    assert "max_pages" in data


def test_404(client):
    r = client.get("/nonexistent")
    assert r.status_code == 404
