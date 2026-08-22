"""
Scrapes Clutch data via SerpApi (Google site: search).
Bypasses Cloudflare bot detection entirely by leveraging Google search indexing.
"""
from sources.serpapi_search import _search

def search_clutch(field, location, num=10, start=0, api_key=None):
    """Find Clutch company profiles for field+location via site: search."""
    loc = location.split(",")[0].strip()
    query = f'site:clutch.co/profile "{field}" "{loc}"'
    items = _search(query, num=num, start=start, api_key=api_key)
    
    # Fallback if strict quoted query returns few results
    if not items and start == 0:
        query_broad = f'site:clutch.co/profile {field} {location}'
        items = _search(query_broad, num=num, start=start, api_key=api_key)

    results = []
    for it in items:
        title = it.get("title", "")
        # Clean title: e.g. "TrianglZ Reviews | Clutch.co" -> "TrianglZ"
        name = title.split(" - ")[0].split(" | ")[0].replace(" Reviews", "").strip()
        if not name or "clutch" in name.lower():
            continue
        
        clutch_url = it.get("link")
        results.append({
            "name": name,
            "website": None,
            "detail_url": clutch_url,
            "snippet": it.get("snippet", ""),
            "source": "Clutch",
        })
    return results