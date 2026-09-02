import requests

def search_indeed(field, location, num_results, start=0, api_key=None):
    if not api_key: raise Exception("No SerpApi key provided.")
    
    # Searches both the global and Egyptian Indeed domains, and removes the strict /cmp filter
    query = f'{field} "{location}" (site:eg.indeed.com OR site:indeed.com)'
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": min(num_results, 20),
        "start": start
    }
    
    res = requests.get("https://serpapi.com/search", params=params, timeout=15)
    data = res.json()
    
    if "error" in data: 
        raise Exception(f"SerpApi Error: {data['error']}")
        
    results = []
    # Grab EVERYTHING Google returns to see what data is actually there
    for item in data.get("organic_results", []):
        title = item.get("title", "Unknown")
        link = item.get("link", "")
        
        results.append({
            "name": title,  # Passing raw title so we can see what it looks like in the DB
            "website": "",
            "linkedin": "",
            "source": "Indeed",
            "source_url": link
        })
            
    return results