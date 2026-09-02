import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    page = start // 15
    query = quote(f"{field} {location}")
    url = f"https://wuzzuf.net/search/jobs/?q={query}&start={page}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        seen = set()
        
        # Matches Wuzzuf's company profile links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/jobs/careers/" in href:
                name = a.get_text(strip=True).replace(" -", "")
                name_lower = name.lower()
                
                if name and len(name) < 45 and name_lower not in seen and "job" not in name_lower:
                    seen.add(name_lower)
                    full_link = href if href.startswith("http") else f"https://wuzzuf.net{href}"
                    
                    results.append({
                        "name": name,
                        "website": "",
                        "linkedin": "",
                        "source": "Wuzzuf",
                        "source_url": full_link
                    })
                    
                    if len(results) >= num_results:
                        break
                        
        return results
    except Exception as e:
        print(f"Wuzzuf Free Scraper Error: {e}")
        return []