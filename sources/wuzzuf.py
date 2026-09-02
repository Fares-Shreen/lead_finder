import requests

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    if not api_key: raise Exception("No SerpApi key provided.")
    
    city = location.split(",")[0].strip()
    query = f'{field} "{city}" site:wuzzuf.net'
    
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
        
        # Skip aggregate search pages (like "370 alexandria Jobs in Egypt")
        if "/a/" in link or " Jobs in " in title:
            continue
            
        company = title
        
        # Extract name if it says "job at TechCorp" or "Careers at TechCorp"
        if " at " in title:
            try:
                company = title.split(" at ")[1].split(" in ")[0].strip()
            except:
                pass
                
        if company and len(company) < 55 and company.lower() not in seen:
            seen.add(company.lower())
            results.append({
                "name": company,
                "website": "",
                "linkedin": "",
                "source": "Wuzzuf",
                "source_url": link
            })
            
    return results