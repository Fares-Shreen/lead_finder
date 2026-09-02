import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}

def search_google_maps(field, location, num_results, start=0, api_key=None):
    url = "https://html.duckduckgo.com/html/"
    query = f'"{field}" companies in "{location}" -site:linkedin.com -site:facebook.com'
    data = {"q": query, "s": start}
    
    try:
        res = requests.post(url, data=data, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        seen = set()
        
        for item in soup.find_all("div", class_="result__body"):
            title_tag = item.find("h2", class_="result__title")
            link_tag = item.find("a", class_="result__url")
            
            if not title_tag or not link_tag:
                continue
                
            raw_title = title_tag.get_text(strip=True)
            link = link_tag.get("href", "")
            
            # Clean directory titles to isolate business names
            name = raw_title.split("|")[0].split("-")[0].split(":")[0].strip()
            name_lower = name.lower()
            
            if name and len(name) < 45 and name_lower not in seen:
                seen.add(name_lower)
                results.append({
                    "name": name,
                    "website": link,
                    "linkedin": "",
                    "source": "Web Search (Free)",
                    "source_url": link
                })
                
                if len(results) >= num_results:
                    break
                    
        return results
    except Exception as e:
        print(f"Web Search Free Scraper Error: {e}")
        return []