"""
Scraper for yellowpages.com.eg (Egypt's official Yellow Pages).

Verified against the real, live site (Aug 2026):
  - General keyword search:  https://yellowpages.com.eg/en/search/{keyword}
  - Pagination:              https://yellowpages.com.eg/en/search/{keyword}/p2, /p3, ...
  - The site hides phone numbers behind a "Phone Number" placeholder (JS-only
    reveal), so we can't read them directly. BUT its WhatsApp button embeds
    the real phone number in the link itself (wa.me/whatsapp "send?phone=..."),
    so we pull the phone from there instead.
  - "Email Us" links go to an on-page contact form, not a real email address,
    so no email is available from this site directly — that's why the main
    pipeline still visits each company's own website afterward to look for one.

Parsing strategy: rather than depending on CSS class names (which any
directory redesign can change overnight), this groups everything by the
numeric company ID embedded in each profile URL
(/en/profile/{slug}/{ID}) and reads off the button TEXT ("Website",
"WhatsApp", "Map", "More info", etc.), which is far more stable than styling
classes. If the site changes its markup again, this is the file to revisit.
"""
import re
from collections import OrderedDict
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT

BASE = "https://yellowpages.com.eg"
PROFILE_ID_RE = re.compile(r"/en/profile/[^/\"'?]+/(\d+)")
WHATSAPP_PHONE_RE = re.compile(r"phone=(\+?\d+)")
SKIP_LINK_TEXT = {"more info", "email us", "map", "phone number", "see all branches"}


def _slug_to_name(href):
    """Fallback: turn /en/profile/some-company-name/123 into 'Some Company Name'."""
    m = re.search(r"/en/profile/([^/]+)/\d+", href)
    if not m:
        return None
    slug = m.group(1).replace("-_-", " & ").replace("-", " ")
    return slug.title()


def parse_results(html):
    soup = BeautifulSoup(html, "html.parser")
    groups = OrderedDict()  # profile_id -> {"name", "address", "website", "phone"}
    order = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        low = text.lower()

        m = PROFILE_ID_RE.search(href)
        if m:
            pid = m.group(1)
            if pid not in groups:
                groups[pid] = {"name": None, "address": None, "website": None, "phone": None, "href": href}
                order.append(pid)
            g = groups[pid]
            if low in SKIP_LINK_TEXT or not text:
                continue
            if g["name"] is None:
                # Guard against the occasional "sponsored" listing where the
                # first linked text is a long description, not the name.
                name = text if len(text) <= 80 else (_slug_to_name(href) or text[:80])
                g["name"] = name
            elif g["address"] is None and ("," in text or text.endswith(".")):
                g["address"] = text
            continue

        # Non-profile links (Website / WhatsApp) belong to whichever profile
        # group we most recently opened.
        if not order:
            continue
        current = groups[order[-1]]
        if low == "website" and href.startswith("http") and "yellowpages.com.eg" not in href:
            current["website"] = href
        elif low == "whatsapp":
            wm = WHATSAPP_PHONE_RE.search(href)
            if wm:
                current["phone"] = wm.group(1)

    results = []
    for pid in order:
        g = groups[pid]
        if not g["name"]:
            continue
        results.append({
            "name": g["name"],
            "address": g["address"] or "",
            "website": g["website"],
            "phone": g["phone"],
            "detail_url": BASE + g["href"] if g["href"].startswith("/") else g["href"],
            "source": "Yellow Pages Egypt",
        })
    return results


def search_yellowpages(field, location, num=10, max_pages=3, start_page=1):
    """
    Searches yellowpages.com.eg by keyword (field) and keeps only listings
    whose address text mentions the given location (e.g. "Alexandria").
    start_page lets a repeat search pick up where the last one left off,
    instead of re-fetching page 1 (and the same companies) every time.
    """
    keyword = quote(field.strip())
    location_key = location.split(",")[0].strip().lower()  # "Alexandria, Egypt" -> "alexandria"

    matches = []
    for page in range(start_page, start_page + max_pages):
        url = f"{BASE}/en/search/{keyword}" + (f"/p{page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                break
            page_results = parse_results(r.text)
        except requests.RequestException:
            break

        if not page_results:
            break

        for res in page_results:
            if location_key in res["address"].lower():
                matches.append(res)
                if len(matches) >= num:
                    return matches
    return matches
