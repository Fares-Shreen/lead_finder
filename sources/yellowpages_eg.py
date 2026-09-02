import requests

def search_yellowpages(field, location, num_results, start=0, api_key=None):
    if not api_key: raise Exception("No SerpApi key provided.")
    
    city = location.split(",")[0].strip()
    query = f'site:yellowpages.com.eg/en/profile {field} {city}'
    params = {
        "engine": "google", 
        "q": query, 
        "api_key": api_key, 
        "num": num_results, 
        "start": start 
    }
    
    res = requests.get("https://serpapi.com/search", params=params, timeout=10)
    data = res.json()
    
    if "error" in data:
        raise Exception(f"SerpApi Error: {data['error']}")
        
    results = []
    for item in data.get("organic_results", []):
        title = item.get("title", "")
        link = item.get("link", "")
        company = title.split(" - ")[0].split(" | ")[0].strip()
        
        invalid_keywords = ["yellowpages", "profile", "category"]
        comp_lower = company.lower()
        
        if company and len(company) < 60 and not any(k in comp_lower for k in invalid_keywords):
            results.append({
                "name": company,
                "website": "",
                "linkedin": "",
                "source": "Yellow Pages",
                "source_url": link
            })
            
    return results