import requests

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    # site:wuzzuf.net/jobs/p targets specific job posting pages
    query = f'site:wuzzuf.net/jobs/p "{field}" "{location}"'
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
        "start": start,
        "tbs": "qdr:m24" # Within last 24 months to ensure they are active
    }
    
    try:
        res = requests.get("https://serpapi.com/search", params=params)
        data = res.json()
        results = []
        
        loc_lower = location.split(",")[0].lower().strip() # "alexandria"
        
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            title_clean = title.replace(" - Wuzzuf", "").replace(" | WUZZUF", "")
            
            # Enforce strict location check on the title itself (drops Dubai/Cairo results)
            if loc_lower not in title_clean.lower():
                continue
            
            # Wuzzuf pattern is usually: Job Title - Company Name - Location
            parts = title_clean.split(" - ")
            
            company = ""
            if len(parts) >= 3:
                # The company is usually the second-to-last item before the location
                company = parts[-2].strip()
            elif len(parts) == 2:
                company = parts[-1].strip()
                
            # Filter out messy extractions and long job descriptions
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