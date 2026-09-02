import requests

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    if not api_key: raise Exception("No SerpApi key provided.")
    
    # Forces exact match on "Alexandria, Egypt"
    query = f'{field} "{location}" site:wuzzuf.net'
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": min(num_results, 20),
        "start": start
    }
    
    res = requests.get("https://serpapi.com/search", params=params, timeout=15)
    data = res.json()
    if "error" in data: raise Exception(f"SerpApi Error: {data['error']}")
        
    results = []
    for item in data.get("organic_results", []):
        results.append({
            "name": item.get("title", "Unknown"),
            "website": "",
            "linkedin": "",
            "source": "Wuzzuf",
            "source_url": item.get("link", "")
        })
    return results