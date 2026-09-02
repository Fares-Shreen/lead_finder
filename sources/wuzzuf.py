import requests

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    query = f'site:wuzzuf.net/jobs/p {field} {location}'
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
        "start": start,
        "tbs": "qdr:m24"
    }
    
    try:
        res = requests.get("https://serpapi.com/search", params=params, timeout=10)
        data = res.json()
        results = []
        
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            title_clean = title.replace(" - Wuzzuf", "").replace(" | WUZZUF", "")
            parts = title_clean.split(" - ")
            
            company = ""
            if len(parts) >= 3:
                company = parts[-2].strip()
            elif len(parts) == 2:
                company = parts[-1].strip()
                
            if company and len(company) < 40 and "job at" not in company.lower():
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": "",
                    "source": "Wuzzuf",
                    "source_url": item.get("link", "")
                })
                
        return results
    except Exception as e:
        print(f"Wuzzuf Scraper Error: {e}")
        return []