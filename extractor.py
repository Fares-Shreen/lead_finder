"""
Given raw HTML (from a company's own website), pull out the useful bits:
emails, Egyptian phone numbers, and a LinkedIn profile link if one is present.
"""
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import dns.resolver
from config import REQUEST_HEADERS, REQUEST_TIMEOUT

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# STRICT EGYPTIAN PHONE MATCHER
# Matches: 
# - Mobiles: +20 10/11/12/15, 0020 1x, or 01x
# - Landlines (Cairo/Alex/etc): +20 2/3, 02/03, 04x-09x
PHONE_RE = re.compile(
    r"(?<!\d)(?:(?:\+20|0020)|0)[\s\-()]*(?:\d[\s\-()]*){8,10}(?!\d)"
)

LINKEDIN_RE = re.compile(r"https?://[\w.]*linkedin\.com/company/[^\s\"'<>/?#]+", re.I)

CONTACT_PATH_HINTS = ["contact", "contact-us", "contactus", "about", "about-us", "get-in-touch"]

SKIP_EMAIL_DOMAINS = {"example.com", "sentry.io", "wixpress.com", "godaddy.com"}


def _is_valid_email_domain(email):
    domain = email.split("@")[-1]
    try:
        # Check if the domain has a mail server configured
        dns.resolver.resolve(domain, 'MX')
        return True
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        return False

def _clean_emails(raw_emails):
    seen, out = set(), []
    for e in raw_emails:
        e = e.strip().strip(".,;:")
        domain = e.split("@")[-1].lower()
        if any(domain == blocked or domain.endswith("." + blocked) for blocked in SKIP_EMAIL_DOMAINS) or e.lower().endswith((".png", ".jpg", ".gif")):
            continue
        if e.lower() not in seen:
            seen.add(e.lower())
            # ONLY add the email if the domain can actually receive mail!
            if _is_valid_email_domain(e):
                out.append(e)
    return out


def _clean_phones(raw_phones):
    seen, out = set(), []
    for p in raw_phones:
        digits = re.sub(r"\D", "", p)
        if digits.startswith("0020"):
            digits = digits[2:]
        national = "0" + digits[2:] if digits.startswith("20") else digits
        is_mobile = bool(re.fullmatch(r"01[0125]\d{8}", national))
        is_cairo = bool(re.fullmatch(r"02\d{8}", national))
        is_alex = bool(re.fullmatch(r"03\d{7}", national))
        is_other_landline = bool(re.fullmatch(r"0[4-9]\d{8}", national))
        if not any((is_mobile, is_cairo, is_alex, is_other_landline)):
            continue
        if national not in seen:
            seen.add(national)
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
    """
    result = {"emails": [], "phones": [], "linkedin": None}
    if not website_url:
        return result

    # Fix missing http/https
    if not website_url.startswith("http"):
        website_url = "http://" + website_url

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
