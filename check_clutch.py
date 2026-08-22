"""
Run this to find out exactly why Clutch is returning 0 results:

    python check_clutch.py

It checks the two most likely causes:
  1. Cloudflare is blocking the request outright (shows a "challenge"
     page instead of real content) — common for commercial B2B sites.
  2. The request succeeds, but the real page structure doesn't match
     what the parser expects (site changed / my assumption was wrong).

It also saves the raw HTML to clutch_debug.html so you can send it back
if the diagnosis isn't obvious from the printed summary.
"""
import requests
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT

URL = "https://clutch.co/eg/developers"

print(f"Fetching {URL} ...")
try:
    r = requests.get(URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
except requests.RequestException as e:
    print(f"\nRequest FAILED to even connect: {e}")
    print("This usually means a network/firewall/antivirus issue on this PC, not Clutch itself.")
    raise SystemExit

print(f"Status code: {r.status_code}")
print(f"Response length: {len(r.text)} characters")

with open("clutch_debug.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("Saved full response to clutch_debug.html\n")

lower = r.text.lower()
challenge_signs = ["just a moment", "cf-browser-verification", "attention required",
                    "checking your browser", "cloudflare", "captcha"]
found_signs = [s for s in challenge_signs if s in lower]

if r.status_code in (403, 429, 503) or found_signs:
    print("DIAGNOSIS: Looks like Cloudflare (or similar) is blocking this request.")
    print(f"  Status: {r.status_code}, matched signs: {found_signs or 'none, but status code suggests a block'}")
    print("  This means Clutch needs a JS-capable fetch (e.g. Playwright) instead of")
    print("  a plain request — a different kind of fix than a parser tweak.")
else:
    soup = BeautifulSoup(r.text, "html.parser")
    headings = soup.find_all(["h2", "h3"])
    print(f"DIAGNOSIS: Page loaded normally (no block detected).")
    print(f"  Found {len(headings)} <h2>/<h3> tags on the page.")
    if headings:
        print("  First few:")
        for h in headings[:8]:
            print(f"    - <{h.name}> {h.get_text(strip=True)[:60]!r}")
        print("\n  If these look like company names -> parser logic needs a small fix.")
        print("  If these look like page titles/section headers, not company names")
        print("  -> company names live in a different tag, need to adjust selector.")
    else:
        print("  No h2/h3 tags found at all — company names must be in a different")
        print("  tag (div/span/p). Open clutch_debug.html and search for a company")
        print("  name you can see on the live site (e.g. 'TrianglZ') to find the real tag.")
