import requests

def search_indeed(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    query = f'site:eg.indeed.com/viewjob "{field}" "{location}"'
    params = {"engine": "google", "q": query, "api_key": api_key, "num": num_results, "start": start}
    
    try:
        res = requests.get("https://serpapi.com/search", params=params)
        data = res.json()
        results = []
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            company = ""
            if "-" in title:
                parts = title.split("-")
                if len(parts) >= 2:
                    company = parts[1].replace("Indeed.com", "").strip()
            
            if company and len(company) < 40:
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": "",
                    "source": "Indeed",
                    "source_url": item.get("link", "")
                })
        return results
    except Exception:
        return []