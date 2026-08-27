import requests

def search_indeed(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    # Remove /viewjob constraint since Indeed uses 'noindex' tags on direct job URLs
    # A broad site search catches their indexed category and career pages reliably
    query = f'site:eg.indeed.com "{field}" "{location}"'
    
    params = {
        "engine": "google", 
        "q": query, 
        "api_key": api_key, 
        "num": num_results, 
        "start": start,
        "tbs": "qdr:m24" # Limits to active/recent listings in the last 2 years
    }
    
    try:
        res = requests.get("https://serpapi.com/search", params=params)
        data = res.json()
        results = []
        
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            
            # Indeed titles on Google typically follow this structure:
            # "Job Title - Location - Company Name - Indeed.com"
            title_clean = title.replace(" - Indeed.com", "").replace(" | Indeed.com", "")
            
            parts = title_clean.split(" - ")
            company = ""
            
            if len(parts) > 1:
                # The company name is almost always the very last chunk after removing 'Indeed.com'
                company = parts[-1].strip()
            
            # Skip generic directory pages (e.g., "Browse all Software Jobs in Egypt")
            if company and len(company) < 40 and "jobs" not in company.lower() and "indeed" not in company.lower():
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": "",
                    "source": "Indeed",
                    "source_url": item.get("link", "")
                })
                
        return results
    except Exception as e:
        print(f"Indeed Scraper Error: {e}")
        return []