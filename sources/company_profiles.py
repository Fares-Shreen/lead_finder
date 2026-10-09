"""Discover directory company profiles with a bounded query fallback."""
import re
from urllib.parse import urlparse, urlunparse

from lead_quality import is_valid_source_url, sanitize_lead, normalize_url
from sources.serpapi_search import _search
from company_location import TARGET_LOCATION

PROFILE_SITES = {
    "LinkedIn": "linkedin.com/company",
    "Wuzzuf": "wuzzuf.net/jobs/careers",
    "Indeed": "indeed.com/cmp",
    "Yellow Pages": "yellowpages.com.eg/en/profile",
    "Clutch": "clutch.co/profile",
}


def profile_url(source, value):
    url = normalize_url(value)
    if not url:
        return ""
    parsed = urlparse(url)
    # Convert known employer tabs to the main company profile.
    if source in {"LinkedIn", "Indeed"}:
        parts = parsed.path.strip("/").split("/")
        allowed_tabs = {"about", "jobs", "life", "people"} if source == "LinkedIn" else {"about", "reviews", "jobs", "salaries", "faq"}
        if len(parts) == 3 and parts[2].lower() in allowed_tabs:
            parsed = parsed._replace(path="/" + "/".join(parts[:2]))
    url = urlunparse(parsed._replace(query="", fragment=""))
    return url if is_valid_source_url(source, url) else ""


def company_name(source, title):
    name = str(title or "").strip()
    if source == "LinkedIn":
        name = re.sub(r"\s*[|–—-]\s*LinkedIn.*$", "", name, flags=re.I)
        name = re.sub(r"\s*:\s*(?:Overview|About|Jobs|Life|People)\s*$", "", name, flags=re.I)
    elif source == "Wuzzuf":
        match = re.search(r"(?:jobs? and )?careers at (.+?)(?: in Egypt|\s*\||$)", name, re.I)
        name = match.group(1) if match else re.split(r"\s+Careers\b|\s*\|", name, flags=re.I)[0]
    elif source == "Indeed":
        name = re.sub(r"^(?:Working at\s+|فرص العمل والتوظيف في\s+)", "", name, flags=re.I)
        name = re.split(r"\s+Careers and Employment|:\s*Reviews|\s*\|", name, flags=re.I)[0]
    elif source == "Clutch":
        name = re.sub(r"\s*\(\d+\),?\s*Pricing,.*$", "", name, flags=re.I)
        name = re.split(r"\s+Reviews\b|\s*\|", name, flags=re.I)[0]
    else:
        name = re.split(r"\s+\|\s+|\s+-\s+", name)[0]
    return name.strip(" -|:–—")


def search_company_profiles(source, field, location, num_results, start=0, api_key=None):
    location = TARGET_LOCATION
    city = location.split(",")[0].strip()
    site = PROFILE_SITES[source]
    # Avoid requiring an exact city/country punctuation format.
    queries = [
        f"site:{site} {field.strip()} {location.replace(',', ' ').strip()}",
        f'site:{site} {field.strip()} "{city}" "Egypt"',
    ]
    if source == "LinkedIn":
        queries.append(f"site:eg.linkedin.com/company {field.strip()} {city} Egypt")
    for query in dict.fromkeys(queries):
        items = _search(query, num=num_results, start=start, api_key=api_key)
        results, seen = [], set()
        for item in items:
            url = profile_url(source, item.get("link"))
            if not url or url.lower() in seen:
                continue
            candidate, _ = sanitize_lead({
                "name": company_name(source, item.get("title")),
                "source": source,
                "source_url": url,
                "linkedin": url if source == "LinkedIn" else "",
                "website": "",
                "snippet": item.get("snippet", ""),
            })
            if candidate:
                results.append(candidate)
                seen.add(url.lower())
            if len(results) >= num_results:
                break
        if results:
            return results
    return []
