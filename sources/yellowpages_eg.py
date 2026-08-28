import requests

def search_yellowpages(field, location, num_results, start=0, api_key=None):
    if not api_key: return []
    
    # Use an f-string to safely inject variables (prevents the string/int concatenation error)
    query = f'site:yellowpages.com.eg "{field}" "{location}"'
    
    params = {
        "engine": "google", 
        "q": query, 
        "api_key": api_key, 
        "num": num_results, 
        "start": start  # Requests library automatically handles integer conversion here
    }
    
    try:
        res = requests.get("https://serpapi.com/search", params=params, timeout=10)
        data = res.json()
        results = []
        
        for item in data.get("organic_results", []):
            title = item.get("title", "")
            
            # Yellow Pages Google titles usually look like: "Company Name - Category - Location"
            company = title.split(" - ")[0].strip()
            
            # Filter out generic directory pages (e.g., "Top 10 Software Companies")
            if company and len(company) < 50 and "Yellowpages" not in company and "Top" not in company:
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