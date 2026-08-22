"""
Uses SerpApi (serpapi.com) to get real Google search results — and,
via a `site:linkedin.com/company` query, real LinkedIn company pages —
without scraping Google or LinkedIn directly (both block that outright).

WHY SERPAPI INSTEAD OF GOOGLE'S OWN CUSTOM SEARCH API:
Google's Custom Search JSON API is closed to new sign-ups as of 2025 and
is being shut down entirely on January 1, 2027 (confirmed via Google's
own developer docs, Aug 2026), so it's not viable to build on going
forward. SerpApi's free plan gives 250 real Google searches every month,
on a recurring basis, with no credit card required to sign up — the most
durable free option currently available. Get a key at:
  https://serpapi.com/users/sign_up
(after signing up, your key is on your SerpApi dashboard)

250/month is enough for roughly 100+ full app searches (each search uses
~2 calls: one for general Google results, one for LinkedIn company pages).
If you outgrow it, SerpApi's paid tiers start at $25/month for 1,000
searches — or just lean on Yellow Pages + Clutch, which need no API key
and have no cap at all.
"""
import requests

from config import SERPAPI_KEY, REQUEST_TIMEOUT

ENDPOINT = "https://serpapi.com/search"


def _search(query, num=10, start=0, api_key=None):
    key = api_key or SERPAPI_KEY
    if not key:
        return []
    params = {
        "engine": "google",
        "q": query,
        "api_key": key,
        "num": min(num, 50),  # SerpApi/Google results reliably thin out past ~50-100
        "start": start,  # pagination offset, in units of 10 (Google convention)
    }
    try:
        r = requests.get(ENDPOINT, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return []
    if "error" in data:
        return []
    return data.get("organic_results", [])[:num]


def search_google_companies(field, location, num=10, start=0, api_key=None):
    """General web search for companies matching field+location."""
    query = f'{field} companies in {location} -site:linkedin.com'
    items = _search(query, num=num, start=start, api_key=api_key)
    results = []
    for it in items:
        title = it.get("title", "")
        results.append({
            "name": title.split(" - ")[0].split(" | ")[0].strip(),
            "website": it.get("link"),
            "snippet": it.get("snippet", ""),
            "source": "Google",
        })
    return results


def search_linkedin_companies(field, location, num=10, start=0, api_key=None):
    """Find LinkedIn company pages for field+location via site: search."""
    query = f'site:linkedin.com/company {field} {location}'
    items = _search(query, num=num, start=start, api_key=api_key)
    results = []
    for it in items:
        title = it.get("title", "")
        name = title.split(" | ")[0].split(" - LinkedIn")[0].strip()
        results.append({
            "name": name,
            "website": None,
            "linkedin": it.get("link"),
            "snippet": it.get("snippet", ""),
            "source": "LinkedIn",
        })
    return results
