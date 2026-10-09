import requests
import re

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    if not api_key: raise Exception("No SerpApi key provided.")
    
    city = location.split(",")[0].strip()
    query = f'site:wuzzuf.net/jobs/careers/ "{field}" "{city}"'
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": 20,
        "start": start
    }
    
    res = requests.get("https://serpapi.com/search", params=params, timeout=25)
    data = res.json()
    if "error" in data: raise Exception(f"SerpApi Error: {data['error']}")
        
    results = []
    seen = set()
    
    for item in data.get("organic_results", []):
        title = item.get("title", "")
        link = item.get("link", "")
        
        # Keep only actual company profiles, never job or aggregate pages.
        if "/jobs/careers/" not in link.lower():
            continue
            
        match = re.search(r"(?:jobs? and )?careers at (.+?)(?: in | \||$)", title, re.I)
        company = match.group(1).strip() if match else title
        company = company.split(" Careers")[0].split(" careers")[0]
        company = company.split(" | ")[0].split(" - ")[0].strip()
                
        if company and len(company) < 55 and company.lower() not in seen:
            seen.add(company.lower())
            results.append({
                "name": company,
                "website": "",
                "linkedin": "",
                "source": "Wuzzuf",
                "source_url": link,
                "snippet": item.get("snippet", "")
            })
            
    return results
