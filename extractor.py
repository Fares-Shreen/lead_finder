"""
Given raw HTML (from a company's own website), pull out the useful bits:
emails, phone numbers, and a LinkedIn profile link if one is present.
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Egyptian-friendly phone matcher: local numbers, +20 country code, spaced/dashed formats
PHONE_RE = re.compile(
    r"(?:\+?20[\s\-]?1[0125][\s\-]?\d{3}[\s\-]?\d{4}"   # +20 1x xxx xxxx (mobile)
    r"|\+?\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4})"
)
LINKEDIN_RE = re.compile(r"https?://[\w.]*linkedin\.com/[^\s\"'<>]+", re.I)

CONTACT_PATH_HINTS = ["contact", "contact-us", "contactus", "about", "about-us", "get-in-touch"]

SKIP_EMAIL_DOMAINS = {"example.com", "sentry.io", "wixpress.com", "godaddy.com"}


def _clean_emails(raw_emails):
    seen, out = set(), []
    for e in raw_emails:
        e = e.strip().strip(".,;:")
        domain = e.split("@")[-1].lower()
        if domain in SKIP_EMAIL_DOMAINS:
            continue
        if e.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
            continue
        if e.lower() not in seen:
            seen.add(e.lower())
            out.append(e)
    return out


def _clean_phones(raw_phones):
    seen, out = set(), []
    for p in raw_phones:
        digits = re.sub(r"\D", "", p)
        if len(digits) < 8:
            continue
        if digits not in seen:
            seen.add(digits)
            out.append(p.strip())
    return out


def _fetch(url):
    try:
        r = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return r.text
    except requests.RequestException:
        pass
    return None


def _find_contact_page(base_url, soup):
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(hint in href for hint in CONTACT_PATH_HINTS):
            return urljoin(base_url, a["href"])
    return None


def enrich_from_website(website_url):
    """
    Visit a company's homepage (and its contact page, if findable) and
    return {"emails": [...], "phones": [...], "linkedin": "..." or None}.
    Best-effort: sites with heavy JS rendering or bot protection may return
    little or nothing, in which case the fields come back empty.
    """
    result = {"emails": [], "phones": [], "linkedin": None}
    if not website_url:
        return result

    html = _fetch(website_url)
    pages_html = [html] if html else []

    if html:
        soup = BeautifulSoup(html, "html.parser")
        contact_url = _find_contact_page(website_url, soup)
        if contact_url and contact_url != website_url:
            contact_html = _fetch(contact_url)
            if contact_html:
                pages_html.append(contact_html)

    all_emails, all_phones, linkedin = [], [], None
    for page in pages_html:
        if not page:
            continue
        all_emails += EMAIL_RE.findall(page)
        all_phones += PHONE_RE.findall(page)
        if not linkedin:
            m = LINKEDIN_RE.search(page)
            if m:
                linkedin = m.group(0)

    result["emails"] = _clean_emails(all_emails)
    result["phones"] = _clean_phones(all_phones)
    result["linkedin"] = linkedin
    return result
