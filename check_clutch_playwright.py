"""
Run this AFTER `playwright install chromium` to check whether the
browser-based fallback actually gets past Clutch's Cloudflare block:

    python check_clutch_playwright.py

This is slower than check_clutch.py (a real browser has to launch and
render the page — expect 10-20 seconds), but tells you definitively
whether the Playwright approach works before you rely on it in a real
search.
"""
from bs4 import BeautifulSoup

from sources.clutch import fetch_with_browser, _looks_blocked, parse_results

URL = "https://clutch.co/eg/developers"

print(f"Launching a real Chromium browser and loading {URL} ...")
print("(this can take 10-20 seconds)\n")

html = fetch_with_browser(URL)

if html is None:
    print("FAILED: Playwright itself didn't return any HTML.")
    print("Most likely cause: Playwright/Chromium isn't installed yet. Run:")
    print("  pip install playwright")
    print("  playwright install chromium")
    raise SystemExit

print(f"Got {len(html)} characters of HTML back.")

if _looks_blocked(200, html):
    print("\nSTILL BLOCKED: even the real browser hit a Cloudflare challenge.")
    print("This means Clutch's bot detection is fingerprinting the automated")
    print("browser itself, not just the plain HTTP request. At that point the")
    print("realistic options are: a paid scraping-API service (e.g. ScraperAPI,")
    print("Bright Data) that specializes in evading this, or dropping Clutch and")
    print("relying on Yellow Pages (unlimited, free) + Google/LinkedIn via SerpApi.")
else:
    results = parse_results(html)
    print(f"\nSUCCESS: page rendered normally. Parser found {len(results)} companies.")
    for r in results[:5]:
        print(f"  - {r['name']} | {r['website']} | {r['location_text']}")
    if not results:
        print("\n(0 companies parsed even though the page loaded — the parser's")
        print(" heading-tag guess may not match Clutch's real markup. Open the")
        print(" saved HTML and check what tag company names are actually in.)")
        with open("clutch_playwright_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(" Saved to clutch_playwright_debug.html for inspection.")
