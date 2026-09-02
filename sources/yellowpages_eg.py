import requests

def search_yellowpages(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    # Extract just the city name (e.g., "Alexandria" from "Alexandria, Egypt")
    city = location.split(",")[0].strip()
    
    # Restricting to '/en/profile' forces Google to ONLY return individual company pages!
    query = f'site:yellowpages.com.eg/en/profile "{field}" "{city}"'
    
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
            
            # Profile page titles format: "Company Name - Category - Location | Yellowpages..."
            company = title.split(" - ")[0].split(" | ")[0].strip()
            
            invalid_keywords = ["yellowpages", "profile", "category"]
            comp_lower = company.lower()
            
            if company and len(company) < 60 and not any(k in comp_lower for k in invalid_keywords):
                results.append({
                    "name": company,
                    "website": "",
                    "linkedin": "",
                    "source": "Yellow Pages",
                    "source_url": link
                })
                
        return results
    except Exception as e:
        print(f"Yellow Pages Error: {e}")
        return []