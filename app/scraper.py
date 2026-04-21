"""
scraper.py — Core OLX scraping logic.

Stealth improvements:
  1. Cookie persistence  — saved/loaded between runs so OLX sees a returning user
  2. Warm-up visit       — visits OLX homepage before search URLs (natural entry)
  3. Randomised run time — jitter added to delays so timing is never mechanical
  4. Reduced scroll      — 3-4 steps instead of 6 (less detectable, still loads lazy content)
"""

import json
import os
import random
import re
import time
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import Stealth
    STEALTH_V2 = True
except ImportError:
    from playwright_stealth import stealth_sync
    STEALTH_V2 = False

from app.config import (
    BROWSER_ARGS_EXTRA, COOKIE_FILE, DELAY_MIN, DELAY_MAX, HEADLESS,
    LOCALE, MAX_PAGES, PAGE_TIMEOUT_MS, REF_PADDING, REF_PREFIX,
    SCROLL_STEPS, TIMEZONE, USER_AGENT, VIEWPORT_HEIGHT, VIEWPORT_WIDTH,
    WARMUP_URL,
)

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-shared-memory-files",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-audio-output",
    "--disable-dbus",
    "--no-zygote",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--metrics-recording-only",
    "--mute-audio",
] + BROWSER_ARGS_EXTRA


# ── Cookie persistence ────────────────────────────────────────────────────────

def load_cookies(context) -> bool:
    """Load saved cookies into the browser context. Returns True if loaded."""
    cookie_path = Path(COOKIE_FILE)
    if not cookie_path.exists():
        print("[Cookies] No saved cookies found — fresh session")
        return False
    try:
        cookies = json.loads(cookie_path.read_text(encoding="utf-8"))
        context.add_cookies(cookies)
        print(f"[Cookies] Loaded {len(cookies)} cookies from {COOKIE_FILE}")
        return True
    except Exception as e:
        print(f"[Cookies] Failed to load cookies: {e}")
        return False


def save_cookies(context):
    """Save current browser cookies to disk for next run."""
    try:
        cookies = context.cookies()
        Path(COOKIE_FILE).parent.mkdir(parents=True, exist_ok=True)
        Path(COOKIE_FILE).write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[Cookies] Saved {len(cookies)} cookies to {COOKIE_FILE}")
    except Exception as e:
        print(f"[Cookies] Failed to save cookies: {e}")


# ── Warm-up visit ─────────────────────────────────────────────────────────────

def warmup(page):
    """
    Visit OLX homepage before hitting search URLs.
    Humans don't deep-link directly into paginated search results.
    """
    print(f"[Warmup] Visiting {WARMUP_URL}...")
    try:
        page.goto(WARMUP_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        human_delay(2, 5)

        # Accept cookie banner on homepage if present
        try:
            btn = page.locator("[id*='onetrust-accept'], button:has-text('Akceptuję')").first
            if btn.is_visible(timeout=4000):
                btn.click()
                print("[Warmup] Cookie banner accepted")
                human_delay(1, 2)
        except Exception:
            pass

        # Gentle scroll — simulate a glance at the homepage
        for i in range(1, 3):
            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i / 3})")
            time.sleep(random.uniform(0.5, 1.2))

        human_delay(1, 3)
        print("[Warmup] Done")
    except Exception as e:
        print(f"[Warmup] Failed (non-fatal): {e}")


# ── Human-like helpers ────────────────────────────────────────────────────────

def human_delay(min_s=None, max_s=None):
    """
    Sleep for a random duration. Uses config defaults if no args given.
    Adds a small extra jitter so timing is never perfectly uniform.
    """
    base = random.uniform(
        min_s if min_s is not None else DELAY_MIN,
        max_s if max_s is not None else DELAY_MAX,
    )
    jitter = random.uniform(0, 0.4)   # up to 400ms extra randomness
    time.sleep(base + jitter)


def slow_scroll(page):
    """
    Scroll down gradually. Uses fewer steps than before (3-4 vs 6)
    — enough to trigger lazy-loaded content, less detectable as automation.
    """
    steps = random.randint(max(2, SCROLL_STEPS - 1), SCROLL_STEPS + 1)
    for i in range(1, steps + 1):
        # Scroll to a slightly randomised position, not perfectly even fractions
        fraction = (i / steps) + random.uniform(-0.03, 0.03)
        fraction = max(0.0, min(1.0, fraction))
        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {fraction})")
        time.sleep(random.uniform(0.4, 1.0))
    # Scroll back up slightly — humans often do this
    page.evaluate("window.scrollTo(0, window.scrollY * 0.85)")
    time.sleep(random.uniform(0.2, 0.5))


# ── Reference ID ──────────────────────────────────────────────────────────────

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

def _extract_fields(card) -> dict:
    """Extract all fields from a card — shared by both extract functions."""
    olx_id = card.get_attribute("id") or "N/A"

    try:
        title = card.locator(
            "[data-cy='ad-card-title'] h4, [data-cy='ad-card-title'] h6"
        ).first.inner_text().strip()
    except Exception:
        title = "N/A"

    try:
        price = card.locator("[data-testid='ad-price']").first.inner_text().strip().split("\n")[0].strip()
    except Exception:
        price = "N/A"

    try:
        location_date = card.locator("[data-testid='location-date']").first.inner_text().strip()
        parts        = location_date.split(" - ")
        address      = parts[0].strip() if parts else "N/A"
        listing_date = parts[1].strip() if len(parts) > 1 else str(date.today())
    except Exception:
        address      = "N/A"
        listing_date = str(date.today())

    area = "N/A"
    try:
        param_text = card.locator(
            "[data-testid='blueprint-card-param-icon']"
        ).locator("..").inner_text().strip()
        m = re.search(r"([\d\s]+[,.]?\d*)\s*m\u00b2", param_text)
        if m:
            area = m.group(1).strip().replace(",", ".") + " m\u00b2"
    except Exception:
        m = re.search(r"([\d]+[,.]?\d*)\s*m\u00b2", card.inner_text())
        if m:
            area = m.group(1).replace(",", ".") + " m\u00b2"

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


def extract_card(card) -> dict | None:
    """Extract a card only if it has the Nowość badge."""
    try:
        badge  = card.locator("p:has-text('Nowo\u015b\u0107')").first
        is_new = badge.is_visible(timeout=500)
    except Exception:
        is_new = False

    if not is_new:
        return None

    return _extract_fields(card)


def extract_card_all(card) -> dict | None:
    """Extract any card regardless of badge."""
    data = _extract_fields(card)
    if data["title"] == "N/A" and data["link"] == "N/A":
        return None
    return data


# ── Page scraper ──────────────────────────────────────────────────────────────

def scrape_url(page, url: str, only_new: bool = True) -> list:
    listings = []
    current  = url
    page_num = 1

    while current:
        if MAX_PAGES and page_num > MAX_PAGES:
            print(f"  [cap] MAX_PAGES={MAX_PAGES} reached, stopping.")
            break

        print(f"  -> page {page_num}: {current[:90]}...")
        page.goto(current, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        human_delay(2, 4)
        slow_scroll(page)
        human_delay(1, 2)

        # Cookie banner on search pages (may appear again after warmup)
        try:
            btn = page.locator("[id*='onetrust-accept'], button:has-text('Akceptuj\u0119')").first
            if btn.is_visible(timeout=2000):
                btn.click()
                human_delay(0.8, 1.5)
        except Exception:
            pass

        # Read the active category from the filter dropdown — once per page
        try:
            category = page.locator(
                "[data-testid='category-dropdown'] .css-ydag0f"
            ).first.inner_text().strip()
        except Exception:
            category = "N/A"
        print(f"     Category: {category}")

        cards     = page.locator("div[data-cy='l-card']").all()
        new_count = 0
        print(f"     {len(cards)} cards found")

        for card in cards:
            try:
                result = extract_card(card) if only_new else extract_card_all(card)
                if result:
                    result["category"] = category
                    listings.append(result)
                    new_count += 1
            except Exception as e:
                print(f"     ! parse error: {e}")

        print(f"     {new_count} new listings extracted")

        if only_new and new_count == 0:
            print("     No new listings on this page — stopping.")
            break

        # Pagination
        try:
            nxt = page.locator("a[data-cy='pagination-forward']").first
            if nxt.is_visible(timeout=2000):
                href    = nxt.get_attribute("href") or ""
                current = ("https://www.olx.pl" + href) if href.startswith("/") else href
                page_num += 1
                human_delay(2, 4)
            else:
                current = None
        except Exception:
            current = None

    return listings


# ── Main runner ───────────────────────────────────────────────────────────────

def run_scraper(urls: list, only_new: bool = True, ref_start: int = 0) -> dict:
    """
    Launch stealth browser, run warm-up, load cookies, scrape all URLs,
    save cookies, assign ref IDs. Returns structured result dict.
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

        # Apply stealth v1 patch if needed (v2 is applied at the playwright level)
        page = context.new_page()
        if not STEALTH_V2:
            stealth_sync(page)

        # 1. Load persisted cookies from previous run
        load_cookies(context)

        # 2. Warm-up visit — browse homepage naturally before hitting search
        warmup(page)

        # 3. Scrape each URL
        for url in urls:
            print(f"\n[URL] {url[:90]}...")
            try:
                results = scrape_url(page, url, only_new=only_new)
                all_listings.extend(results)
            except Exception as e:
                print(f"  FAILED: {e}")

            # Brief pause between URLs — humans don't instantly jump between pages
            if len(urls) > 1:
                human_delay(3, 7)

        # 4. Save cookies for next run before closing
        save_cookies(context)
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