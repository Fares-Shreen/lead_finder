import requests

def search_indeed(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    query = f'site:indeed.com/cmp {field} {location}'
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
        "start": start
    }
    
    try:
        res = requests.get("https://serpapi.com/search", params=params, timeout=10)
        data = res.json()
        results = []
        
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            link = item.get("link", "")
            
            # Clean up titles like "Working at Company | Indeed.com"
            company = title.split(" - ")[0].split(" | ")[0].replace("Working at", "").replace("Careers and Employment", "").strip()
            
            if company and len(company) < 40 and "Indeed" not in company:
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": "",
                    "source": "Indeed",
                    "source_url": link
                })
                
        return results
    except Exception as e:
        print(f"Indeed Scraper Error: {e}")
        return []