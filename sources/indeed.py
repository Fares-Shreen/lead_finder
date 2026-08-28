import requests

def search_indeed(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    # Switch to the native Indeed engine
    params = {
        "engine": "indeed", 
        "q": field,           # e.g., "software"
        "l": location,        # e.g., "Alexandria, Egypt"
        "api_key": api_key, 
        "start": start        # Pagination jumps by 10 (0, 10, 20)
    }
    
    try:
        res = requests.get("https://serpapi.com/search", params=params, timeout=10)
        data = res.json()
        results = []
        
        # Native Indeed API returns a clean "jobs_results" array instead of Google organic results
        for item in data.get("jobs_results", []):
            company = item.get("company_name", "").strip()
            
            invalid_keywords = ["indeed", "وظائف", "confidential"]
            comp_lower = company.lower()
            
            # Ensure we have a valid company name (not a confidential listing)
            if company and len(company) < 50 and not any(k in comp_lower for k in invalid_keywords):
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": "",
                    "source": "Indeed",
                    # Prefer share_link if available, otherwise fallback to standard link
                    "source_url": item.get("share_link", item.get("link", "")) 
                })
                
        return results
    except Exception as e:
        print(f"Indeed Native Scraper Error: {e}")
        return []