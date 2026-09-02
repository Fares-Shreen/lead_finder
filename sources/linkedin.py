import requests

def search_linkedin_companies(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    # Removed exact-match quotes so Google doesn't drop close matches
    query = f'site:eg.linkedin.com/company {field} {location}'
    
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
            
            if not ("eg.linkedin.com" in link or "www.linkedin.com" in link):
                continue
                
            company = title.split(" | ")[0].split(" - ")[0].strip()
            
            if company and "LinkedIn" not in company:
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": link,
                    "source": "LinkedIn",
                    "source_url": link
                })
                
        return results
    except Exception as e:
        print(f"LinkedIn Scraper Error: {e}")
        return []