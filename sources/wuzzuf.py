import requests

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    query = f'site:wuzzuf.net/jobs/p "{field}" "{location}"'
    params = {"engine": "google", "q": query, "api_key": api_key, "num": num_results, "start": start}
    
    try:
        res = requests.get("https://serpapi.com/search", params=params)
        data = res.json()
        results = []
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            company = ""
            if " at " in title and " - " in title:
                company = title.split(" at ")[1].split(" - ")[0].strip()
            elif "-" in title:
                company = title.split("-")[1].replace("WUZZUF", "").replace("|", "").strip()
            
            if company and len(company) < 40:
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": "",
                    "source": "Wuzzuf",
                    "source_url": item.get("link", "")
                })
        return results
    except Exception:
        return []