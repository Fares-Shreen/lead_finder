"""Discover directory company profiles with a bounded query fallback."""
import re
from collections import Counter
from urllib.parse import urlparse, urlunparse

from lead_quality import is_valid_source_url, sanitize_lead, normalize_url
from sources.serpapi_search import _search
from company_location import TARGET_LOCATION
from sources.location_verifier import verify_on_maps


class CompanyProfiles(list):
    def __init__(self):
        super().__init__()
        self.diagnostics = Counter()


def industry_terms(field):
    return {
        "it": '("information technology" OR "IT services" OR software)',
        "video editing": '("video production" OR "post production" OR "media production")',
    }.get(field.strip().casefold(), field.strip())

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
        f'site:{site} {industry_terms(field)} "{city}" "Egypt"',
    ]
    if source == "LinkedIn":
        queries.append(f"site:eg.linkedin.com/company {industry_terms(field)} {city} Egypt")
    results = CompanyProfiles()
    seen = set()
    checked_on_maps = {}
    maps_checks_remaining = 2
    for query in dict.fromkeys(queries):
        items = _search(query, num=num_results, start=start, api_key=api_key)
        results.diagnostics["search results examined"] += len(items)
        for item in items:
            url = profile_url(source, item.get("link"))
            if not url or url.lower() in seen:
                results.diagnostics["non-company/duplicate URLs"] += 1
                continue
            raw = {
                "name": company_name(source, item.get("title")),
                "source": source,
                "source_url": url,
                "linkedin": url if source == "LinkedIn" else "",
                "website": "",
                "snippet": item.get("snippet", ""),
            }
            candidate, reason = sanitize_lead(raw)
            if not candidate and reason == "Alexandria, Egypt location not established":
                name_key = raw["name"].casefold()
                if name_key not in checked_on_maps and maps_checks_remaining:
                    maps_checks_remaining -= 1
                    results.diagnostics["Maps address checks"] += 1
                    try:
                        checked_on_maps[name_key] = verify_on_maps(raw["name"], api_key)
                    except Exception:
                        checked_on_maps[name_key] = None
                        results.diagnostics["Maps checks unavailable"] += 1
                place = checked_on_maps.get(name_key)
                if place:
                    raw["address"] = place["address"]
                    raw["location_evidence_url"] = place["source_url"]
                    raw["website"] = place.get("website", "")
                    raw["phones"] = place.get("phones", [])
                    candidate, reason = sanitize_lead(raw)
            if candidate:
                results.append(candidate)
                seen.add(url.lower())
            else:
                results.diagnostics[reason] += 1
            if len(results) >= num_results:
                break
        if results:
            return results
    return results
