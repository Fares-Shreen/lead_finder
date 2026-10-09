"""Shared validation for leads returned by every search source.

Search engines rank pages, not companies.  This module is the boundary that
keeps videos, articles, job listings, search pages, and malformed URLs out of
the company database even when an upstream query returns them.
"""

import re
from urllib.parse import parse_qs, unquote, urlparse, urlunparse


BLOCKED_WEBSITE_DOMAINS = {
    "youtube.com", "youtu.be", "vimeo.com", "tiktok.com",
    "facebook.com", "instagram.com", "x.com", "twitter.com",
    "pinterest.com", "reddit.com", "medium.com", "wikipedia.org",
    "linkedin.com", "indeed.com", "wuzzuf.net", "yellowpages.com.eg",
    "clutch.co", "google.com", "googleusercontent.com", "linktr.ee",
}

GENERIC_NAMES = {
    "youtube", "linkedin", "facebook", "instagram", "wuzzuf", "indeed",
    "yellow pages", "google maps", "home", "search results", "jobs",
}

NOISY_NAME_PATTERNS = (
    re.compile(r"\b(?:top|best)\s+\d+\b", re.I),
    re.compile(r"\b\d+\s+(?:top|best)\b", re.I),
    re.compile(r"\b(?:list of|companies in|jobs? in|job vacancies|search results)\b", re.I),
    re.compile(r"\b(?:watch|video|playlist)\b", re.I),
)


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _domain_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def normalize_url(value) -> str:
    """Return a clean HTTP(S) URL, or an empty string for non-URLs."""
    if not value:
        return ""
    value = str(value).strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    try:
        parsed = urlparse(value)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return ""

    # Google occasionally wraps an organic result in /url?q=<real URL>.
    if _domain_matches((parsed.hostname or "").lower(), "google.com") and parsed.path == "/url":
        target = parse_qs(parsed.query).get("q", [""])[0]
        return normalize_url(unquote(target))

    return urlunparse((parsed.scheme.lower(), parsed.netloc, parsed.path or "", "", parsed.query, ""))


def is_useful_company_website(url: str) -> bool:
    """True only for a plausible company-owned website."""
    clean = normalize_url(url)
    if not clean:
        return False
    host = _host(clean)
    return not any(_domain_matches(host, domain) for domain in BLOCKED_WEBSITE_DOMAINS)


def is_useful_company_name(name: str) -> bool:
    name = re.sub(r"\s+", " ", str(name or "")).strip(" -|:–—")
    if len(name) < 2 or len(name) > 100 or name.casefold() in GENERIC_NAMES:
        return False
    if name.startswith(("http://", "https://", "www.")):
        return False
    return not any(pattern.search(name) for pattern in NOISY_NAME_PATTERNS)


def is_valid_source_url(source: str, url: str) -> bool:
    """Require each source to return its own useful company/place page."""
    clean = normalize_url(url)
    if not clean:
        return False
    host, path = _host(clean), urlparse(clean).path.lower()
    source = (source or "").casefold()

    if source == "google maps":
        return _domain_matches(host, "google.com") and path.startswith("/maps")
    if source == "linkedin":
        return _domain_matches(host, "linkedin.com") and path.startswith("/company/")
    if source == "yellow pages":
        return _domain_matches(host, "yellowpages.com.eg") and "/profile" in path
    if source == "wuzzuf":
        return _domain_matches(host, "wuzzuf.net") and path.startswith("/jobs/careers/")
    if source == "indeed":
        return _domain_matches(host, "indeed.com") and path.startswith("/cmp/") and len(path) > 5
    if source == "clutch":
        return _domain_matches(host, "clutch.co") and path.startswith("/profile/")
    if source == "google":
        return is_useful_company_website(clean)
    return False


def sanitize_lead(lead: dict):
    """Return ``(clean_lead, reason)``; ``clean_lead`` is None when rejected."""
    cleaned = dict(lead)
    cleaned["name"] = re.sub(r"\s+", " ", str(cleaned.get("name") or "")).strip(" -|:–—")
    if not is_useful_company_name(cleaned["name"]):
        return None, "invalid company name"

    source_url = normalize_url(
        cleaned.get("source_url") or cleaned.get("detail_url") or
        (cleaned.get("linkedin") if cleaned.get("source") == "LinkedIn" else "")
    )
    if not is_valid_source_url(cleaned.get("source", ""), source_url):
        return None, "irrelevant source URL"
    cleaned["source_url"] = source_url
    cleaned.pop("detail_url", None)

    website = normalize_url(cleaned.get("website"))
    cleaned["website"] = website if is_useful_company_website(website) else ""

    linkedin = normalize_url(cleaned.get("linkedin"))
    cleaned["linkedin"] = (
        linkedin
        if is_valid_source_url("LinkedIn", linkedin)
        else ""
    )
    return cleaned, ""
