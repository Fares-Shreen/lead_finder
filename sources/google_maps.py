import requests

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
            results.append({
                "name": company,
                "website": item.get("website", ""),
                "linkedin": "",
                "emails": [],
                "phones": [phone] if phone else [],
                "source": "Google Maps",
                "source_url": item.get("gps_coordinates", {}).get("google_maps_url", "") or item.get("place_id", "")
            })
            if len(results) >= num_results:
                break
                
    return results