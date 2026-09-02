import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    # Wuzzuf pagination is 0-indexed (start // 10 roughly maps to pages)
    page = start // 10 
    query = quote(f"{field} {location}")
    url = f"https://wuzzuf.net/search/jobs/?q={query}&start={page}"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        results = []
        seen = set()
        
        # Wuzzuf companies are linked to /jobs/careers/
        for a in soup.find_all("a", href=True):
            if "/jobs/careers/" in a["href"]:
                # Clean up the name
                comp_name = a.text.replace(" -", "").strip()
                
                if comp_name and comp_name not in seen and len(comp_name) < 40 and "job at" not in comp_name.lower():
                    seen.add(comp_name)
                    results.append({
                        "name": comp_name,
                        "website": "",
                        "linkedin": "",
                        "source": "Wuzzuf",
                        "source_url": "https://wuzzuf.net" + a["href"]
                    })
                    
                    if len(results) >= num_results:
                        break
                        
        return results
    except Exception as e:
        print(f"Wuzzuf Free Scraper Error: {e}")
        return []