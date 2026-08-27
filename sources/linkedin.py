import requests

def search_linkedin_companies(field, location, num_results, start=0, api_key=None):
    if not api_key: 
        return []
    
    # We use Google Search restricted to LinkedIn company pages to bypass LinkedIn's bot blockers
    query = f'site:linkedin.com/company/ "{field}" "{location}"'
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
        "start": start
    }
    
    try:
        res = requests.get("https://serpapi.com/search", params=params)
        data = res.json()
        results = []
        
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            link = item.get("link", "")
            
            # Clean up the title to extract just the company name
            # Google formats LinkedIn titles like: "Company Name - LinkedIn" or "Company Name | LinkedIn"
            company_name = title.split(" - ")[0].split(" | ")[0].replace("LinkedIn", "").strip()
            
            if company_name and "linkedin.com/company/" in link:
                results.append({
                    "name": company_name,
                    "website": "",
                    "linkedin": link,
                    "emails": [],
                    "phones": [],
                    "source": "LinkedIn",
                    "source_url": link
                })
                
        return results
    except Exception as e:
        print(f"LinkedIn Scraper Error: {e}")
        return []