import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def search_yellowpages(field, location, num_results, start=0, api_key=None):
    city = location.split(",")[0].strip().replace(" ", "-")
    clean_field = quote(field.replace(" ", "-"))
    page = (start // 15) + 1
    
    url = f"https://yellowpages.com.eg/en/search/{clean_field}/{city}/p{page}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        seen = set()
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/en/profile/" in href or "/en/short-profile/" in href:
                name = a.get_text(strip=True)
                name_lower = name.lower()
                
                invalid_terms = ["yellowpages", "profile", "category", "more info", "call now"]
                if name and len(name) < 55 and name_lower not in seen and not any(term in name_lower for term in invalid_terms):
                    seen.add(name_lower)
                    full_link = href if href.startswith("http") else f"https://yellowpages.com.eg{href}"
                    
                    results.append({
                        "name": name,
                        "website": "",
                        "linkedin": "",
                        "source": "Yellow Pages",
                        "source_url": full_link
                    })
                    
                    if len(results) >= num_results:
                        break
                        
        return results
    except Exception as e:
        print(f"Yellow Pages Free Scraper Error: {e}")
        return []