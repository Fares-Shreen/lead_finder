import requests

def search_indeed(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    # 1. Force Google to only look at actual job posting pages (bypasses directory pages)
    query = f'site:eg.indeed.com/viewjob "{field}" "{location}"'
    
    params = {
        "engine": "google", 
        "q": query, 
        "api_key": api_key, 
        "num": num_results, 
        "start": start,
        "tbs": "qdr:m24" # Limits to active listings in the last 24 months
    }
    
    try:
        res = requests.get("https://serpapi.com/search", params=params, timeout=10)
        data = res.json()
        results = []
        
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            
            # Ensure it is an actual job posting, not a category page
            if "/viewjob" not in link:
                continue
            
            company = ""
            
            # 2. Indeed's Google snippets for /viewjob almost always follow this format:
            # "Job Title - Location. Company Name. Location. Job Description..."
            # By splitting by period, the company name is almost always the second item.
            snippet_parts = snippet.split(".")
            if len(snippet_parts) >= 2:
                company = snippet_parts[1].strip()
                
            # Fallback: If snippet parsing fails, try extracting from the title (Older format)
            if not company or len(company) > 40:
                title_clean = title.replace(" - Indeed.com", "").replace(" - Indeed", "").replace(" | Indeed", "")
                parts = title_clean.split(" - ")
                if len(parts) >= 3:
                    company = parts[-2].strip()
                    
            # 3. Final validation to block garbage data
            invalid_keywords = ["indeed", "وظائف", "job", "salary", "full time", "part time"]
            comp_lower = company.lower()
            
            if company and len(company) < 45 and not any(k in comp_lower for k in invalid_keywords):
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