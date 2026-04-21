"""
scraper.py — Core OLX scraping logic.
Called by the API layer. No Flask/HTTP concerns here.
"""

import random
import re
import time
from datetime import date

from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import Stealth
    STEALTH_V2 = True
except ImportError:
    from playwright_stealth import stealth_sync
    STEALTH_V2 = False

from app.config import (
    BROWSER_ARGS_EXTRA, DELAY_MIN, DELAY_MAX, HEADLESS,
    LOCALE, MAX_PAGES, PAGE_TIMEOUT_MS, REF_PADDING, REF_PREFIX,
    SCROLL_STEPS, TIMEZONE, USER_AGENT, VIEWPORT_HEIGHT, VIEWPORT_WIDTH,
)

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--single-process",            # Required on Render/Railway free tier
] + BROWSER_ARGS_EXTRA


# ── Helpers ──────────────────────────────────────────────────────────────────

def human_delay(min_s=None, max_s=None):
    time.sleep(random.uniform(
        min_s if min_s is not None else DELAY_MIN,
        max_s if max_s is not None else DELAY_MAX,
    ))


def slow_scroll(page):
    for i in range(1, SCROLL_STEPS + 1):
        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i / SCROLL_STEPS})")
        time.sleep(random.uniform(0.3, 0.8))


def generate_ref_id(existing_ids, start_from=0):
    if not existing_ids and start_from == 0:
        return f"{REF_PREFIX}{'1'.zfill(REF_PADDING)}"
    if existing_ids:
        numbers = [int(re.sub(r"[^0-9]", "", r)) for r in existing_ids if re.search(r"\d+", r)]
        next_num = max(numbers) + 1 if numbers else 1
    else:
        next_num = start_from + 1
    return f"{REF_PREFIX}{str(next_num).zfill(REF_PADDING)}"


# ── Card extraction ───────────────────────────────────────────────────────────

def extract_card(card) -> dict | None:
    """Extract all fields from a single listing card. Returns None if not new."""

    # OLX listing ID
    olx_id = card.get_attribute("id") or "N/A"

    # Nowość badge check
    try:
        badge = card.locator("p:has-text('Nowość')").first
        is_new = badge.is_visible(timeout=500)
    except Exception:
        is_new = False

    if not is_new:
        return None

    # Title
    try:
        title = card.locator("[data-cy='ad-card-title'] h4, [data-cy='ad-card-title'] h6").first.inner_text().strip()
    except Exception:
        title = "N/A"

    # Price
    try:
        price = card.locator("[data-testid='ad-price']").first.inner_text().strip().split("\n")[0].strip()
    except Exception:
        price = "N/A"

    # Address & date
    try:
        location_date = card.locator("[data-testid='location-date']").first.inner_text().strip()
        parts = location_date.split(" - ")
        address      = parts[0].strip() if parts else "N/A"
        listing_date = parts[1].strip() if len(parts) > 1 else str(date.today())
    except Exception:
        address      = "N/A"
        listing_date = str(date.today())

    # Area
    area = "N/A"
    try:
        param_text  = card.locator("[data-testid='blueprint-card-param-icon']").locator("..").inner_text().strip()
        area_match  = re.search(r"([\d\s]+[,.]?\d*)\s*m²", param_text)
        if area_match:
            area = area_match.group(1).strip().replace(",", ".") + " m²"
    except Exception:
        full_text  = card.inner_text()
        area_match = re.search(r"([\d]+[,.]?\d*)\s*m²", full_text)
        if area_match:
            area = area_match.group(1).replace(",", ".") + " m²"

    # Link
    try:
        href = card.locator("[data-cy='ad-card-title'] a").first.get_attribute("href") or ""
        if href.startswith("/"):
            href = "https://www.olx.pl" + href
    except Exception:
        href = "N/A"

    return {
        "olx_id":  olx_id,
        "title":   title,
        "price":   price,
        "area":    area,
        "address": address,
        "date":    listing_date,
        "link":    href,
    }


# ── Page scraper ──────────────────────────────────────────────────────────────

def scrape_url(page, url: str, only_new: bool = True) -> list:
    listings  = []
    current   = url
    page_num  = 1

    while current:
        # Safety cap
        if MAX_PAGES and page_num > MAX_PAGES:
            print(f"  [cap] Reached MAX_PAGES={MAX_PAGES}, stopping.")
            break

        print(f"  -> page {page_num}: {current[:90]}...")
        page.goto(current, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        human_delay(2, 4)
        slow_scroll(page)
        human_delay(1, 2)

        # Cookie banner
        try:
            btn = page.locator("[id*='onetrust-accept'], button:has-text('Akceptuję')").first
            if btn.is_visible(timeout=3000):
                btn.click()
                human_delay(1, 2)
        except Exception:
            pass

        cards     = page.locator("div[data-cy='l-card']").all()
        new_count = 0
        print(f"     {len(cards)} cards found")

        for card in cards:
            try:
                result = extract_card(card) if only_new else extract_card_all(card)
                if result:
                    listings.append(result)
                    new_count += 1
            except Exception as e:
                print(f"     ! parse error: {e}")

        print(f"     {new_count} new listings extracted")

        if only_new and new_count == 0:
            print("     No new listings — stopping pagination.")
            break

        # Next page
        try:
            nxt = page.locator("a[data-cy='pagination-forward']").first
            if nxt.is_visible(timeout=2000):
                href = nxt.get_attribute("href") or ""
                current = ("https://www.olx.pl" + href) if href.startswith("/") else href
                page_num += 1
                human_delay(2, 4)
            else:
                current = None
        except Exception:
            current = None

    return listings


def extract_card_all(card) -> dict | None:
    """Same as extract_card but skips the Nowość filter — returns all listings."""
    olx_id = card.get_attribute("id") or "N/A"
    try:
        title = card.locator("[data-cy='ad-card-title'] h4, [data-cy='ad-card-title'] h6").first.inner_text().strip()
    except Exception:
        title = "N/A"
    try:
        price = card.locator("[data-testid='ad-price']").first.inner_text().strip().split("\n")[0].strip()
    except Exception:
        price = "N/A"
    try:
        location_date = card.locator("[data-testid='location-date']").first.inner_text().strip()
        parts = location_date.split(" - ")
        address      = parts[0].strip() if parts else "N/A"
        listing_date = parts[1].strip() if len(parts) > 1 else str(date.today())
    except Exception:
        address      = "N/A"
        listing_date = str(date.today())
    area = "N/A"
    try:
        param_text = card.locator("[data-testid='blueprint-card-param-icon']").locator("..").inner_text().strip()
        m = re.search(r"([\d\s]+[,.]?\d*)\s*m²", param_text)
        if m:
            area = m.group(1).strip().replace(",", ".") + " m²"
    except Exception:
        m = re.search(r"([\d]+[,.]?\d*)\s*m²", card.inner_text())
        if m:
            area = m.group(1).replace(",", ".") + " m²"
    try:
        href = card.locator("[data-cy='ad-card-title'] a").first.get_attribute("href") or ""
        if href.startswith("/"):
            href = "https://www.olx.pl" + href
    except Exception:
        href = "N/A"
    if title == "N/A" and href == "N/A":
        return None
    return {"olx_id": olx_id, "title": title, "price": price,
            "area": area, "address": address, "date": listing_date, "link": href}


# ── Main runner ───────────────────────────────────────────────────────────────

def run_scraper(urls: list, only_new: bool = True, ref_start: int = 0) -> dict:
    """
    Launch browser, scrape all URLs, assign ref IDs.
    Returns structured dict ready for JSON response.
    """
    all_listings = []
    ref_counter  = []

    def _run(p):
        browser = p.chromium.launch(headless=HEADLESS, args=BROWSER_ARGS)
        context = browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            user_agent=USER_AGENT,
            locale=LOCALE,
            timezone_id=TIMEZONE,
        )
        page = context.new_page()
        if not STEALTH_V2:
            stealth_sync(page)
        for url in urls:
            print(f"\n[URL] {url[:90]}...")
            try:
                results = scrape_url(page, url, only_new=only_new)
                all_listings.extend(results)
            except Exception as e:
                print(f"  FAILED: {e}")
        browser.close()

    if STEALTH_V2:
        with Stealth().use_sync(sync_playwright()) as p:
            _run(p)
    else:
        with sync_playwright() as p:
            _run(p)

    # Assign ref IDs
    for listing in all_listings:
        ref_id = generate_ref_id(ref_counter, start_from=ref_start)
        ref_counter.append(ref_id)
        listing["ref_id"] = ref_id

    return {
        "success":            True,
        "date":               str(date.today()),
        "total_new_listings": len(all_listings),
        "listings":           all_listings,
    }
