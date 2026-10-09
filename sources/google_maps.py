import requests
from urllib.parse import quote_plus

def search_google_maps(field, location, num_results, start=0, api_key=None):
    if not api_key: raise Exception("No SerpApi key provided.")
    
    query = f"{field} in {location}"
    params = {
        "engine": "google_maps",
        "q": query,
        "api_key": api_key,
        "type": "search",  # CRITICAL: SerpApi now requires this for maps
        "start": start
    }
    
    res = requests.get("https://serpapi.com/search", params=params, timeout=10)
    data = res.json()
    
    if "error" in data:
        raise Exception(f"SerpApi Error: {data['error']}")
        
    results = []
    for item in data.get("local_results", []):
        company = item.get("title", "")
        if company:
            phone = item.get("phone", "")
            links = item.get("links", {}) or {}
            website = item.get("website", "") or links.get("website", "")
            source_url = item.get("link", "") or links.get("directions", "")
            if not source_url:
                # A raw place_id is not clickable. A Maps search URL remains useful
                # across both the CID and ChIJ variants returned by SerpApi.
                source_url = (
                    "https://www.google.com/maps/search/?api=1&query="
                    + quote_plus(f"{company}, {location}")
                )
            results.append({
                "name": company,
                "website": website,
                "linkedin": "",
                "emails": [],
                "phones": [phone] if phone else [],
                "source": "Google Maps",
                "source_url": source_url,
                "snippet": item.get("description", "")
            })
            if len(results) >= num_results:
                break
                
    return results
