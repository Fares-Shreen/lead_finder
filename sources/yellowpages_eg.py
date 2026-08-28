import requests

def search_yellowpages(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    query = f'site:yellowpages.com.eg "{field}" "{location}"'
    
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
            link = item.get("link", "").lower()
            
            # 1. Skip directory and category pages immediately
            if "/category/" in link or "/map-category/" in link:
                continue
                
            # Yellow Pages Google titles usually look like: "Company Name - Category - Location"
            company = title.split(" - ")[0].strip()
            comp_lower = company.lower()
            
            # 2. Block aggregate titles like "Best 50 Companies..."
            invalid_keywords = ["yellowpages", "top", "best", "companies", "ministries", "organizations"]
            if company and len(company) < 50 and not any(k in comp_lower for k in invalid_keywords):
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": "",
                    "source": "Yellow Pages",
                    "source_url": item.get("link", "")
                })
                
        return results
    except Exception as e:
        print(f"Yellow Pages Error: {e}")
        return []