import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

def search_yellowpages(field, location, num_results, start=0, api_key=None):
    city = location.split(",")[0].strip().replace(" ", "-")
    page = (start // 15) + 1  # YP pages are 1-indexed
    query = quote(field.replace(" ", "-"))
    
    url = f"https://yellowpages.com.eg/en/search/{query}/{city}/p{page}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        results = []
        seen = set()
        
        # Look for standard YP profile links
        for a in soup.find_all("a", href=True):
            if "/en/profile/" in a["href"] or "/en/short-profile/" in a["href"]:
                comp_name = a.text.strip()
                
                if comp_name and len(comp_name) > 2 and comp_name not in seen:
                    link = a["href"]
                    if not link.startswith("http"):
                        link = "https://yellowpages.com.eg" + link
                        
                    seen.add(comp_name)
                    results.append({
                        "name": comp_name,
                        "website": "",
                        "linkedin": "",
                        "source": "Yellow Pages",
                        "source_url": link
                    })
                    
                    if len(results) >= num_results:
                        break
                        
        return results
    except Exception as e:
        print(f"Yellow Pages Free Scraper Error: {e}")
        return []