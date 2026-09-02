import requests

def search_indeed(field, location, num_results, start=0, api_key=None):
    if not api_key: raise Exception("No SerpApi key provided.")
    
    city = location.split(",")[0].strip()
    query = f'{field} "{city}" (site:eg.indeed.com OR site:indeed.com/cmp)'
    
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
        
        # Skip aggregate search pages
        if "/q-" in link or "/jobs" in link:
            continue
            
        company = title
        
        # Extract name if it says "Working at TechCorp" or "TechCorp Careers"
        if "Working at " in title:
            company = title.replace("Working at ", "").split(":")[0].strip()
        elif " Careers and Employment" in title:
            company = title.split(" Careers and Employment")[0].strip()
        else:
            company = title.split(" - ")[0].split(" | ")[0].strip()

        if company and len(company) < 55 and company.lower() not in seen and "Indeed" not in company:
            seen.add(company.lower())
            results.append({
                "name": company,
                "website": "",
                "linkedin": "",
                "source": "Indeed",
                "source_url": link
            })
            
    return results