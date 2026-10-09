import requests
import re

def search_linkedin_companies(field, location, num_results, start=0, api_key=None):
    if not api_key: raise Exception("No SerpApi key provided.")
    
    # Forces exact match on "Alexandria, Egypt"
    query = f'site:linkedin.com/company/ "{field}" "{location}"'
    
    params = {
        "engine": "google", 
        "q": query, 
        "api_key": api_key, 
        "num": min(num_results, 20), 
        "start": start 
    }
    
    res = requests.get("https://serpapi.com/search", params=params, timeout=15)
    data = res.json()
    if "error" in data: raise Exception(f"SerpApi Error: {data['error']}")
        
    results = []
    for item in data.get("organic_results", []):
        title = item.get("title", "Unknown")
        link = item.get("link", "")
        if "/company/" not in link.lower():
            continue
        company = re.sub(r"\s*(?:\||-)\s*LinkedIn.*$", "", title, flags=re.I).strip()
        
        results.append({
            "name": company if company else title,
            "website": "",
            "linkedin": link,
            "source": "LinkedIn",
            "source_url": link,
            "snippet": item.get("snippet", "")
        })
    return results
