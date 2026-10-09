import requests
from urllib.parse import quote_plus
from config import SERPAPI_KEY
from lead_quality import is_valid_source_url, sanitize_lead
from company_location import TARGET_LOCATION

def search_google_maps(field, location, num_results, start=0, api_key=None):
    location = TARGET_LOCATION
    api_key = api_key or SERPAPI_KEY
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

    if (res.status_code == 200
            and data.get("error") == "Google hasn't returned any results for this query."
            and (data.get("search_metadata") or {}).get("status", "Success") == "Success"):
        return []
    
    if "error" in data:
        raise Exception(f"SerpApi Error: {str(data['error']).replace(api_key, '[redacted]')}")
    res.raise_for_status()
        
    results = []
    for item in data.get("local_results", []):
        company = item.get("title", "")
        if company:
            phone = item.get("phone", "")
            links = item.get("links", {}) or {}
            website = item.get("website", "") or links.get("website", "")
            source_url = item.get("link", "") or links.get("directions", "")
            if not is_valid_source_url("Google Maps", source_url):
                # A raw place_id is not clickable. A Maps search URL remains useful
                # across both the CID and ChIJ variants returned by SerpApi.
                source_url = (
                    "https://www.google.com/maps/search/?api=1&query="
                    + quote_plus(f"{company}, {location}")
                )
            candidate, _ = sanitize_lead({
                "name": company,
                "website": website,
                "linkedin": "",
                "emails": [],
                "phones": [phone] if phone else [],
                "source": "Google Maps",
                "source_url": source_url,
                "snippet": item.get("description", ""),
                "address": item.get("address", ""),
            })
            if candidate:
                results.append(candidate)
            if len(results) >= num_results:
                break
                
    return results
