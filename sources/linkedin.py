import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}

def search_linkedin_companies(field, location, num_results, start=0, api_key=None):
    url = "https://html.duckduckgo.com/html/"
    query = f'site:eg.linkedin.com/company "{field}" "{location}"'
    data = {"q": query, "s": start}
    
    try:
        res = requests.post(url, data=data, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        seen = set()
        
        for link_tag in soup.find_all("a", class_="result__url"):
            link = link_tag.get("href", "")
            if "linkedin.com/company" in link:
                container = link_tag.find_parent("div", class_="result__body")
                title_tag = container.find("h2", class_="result__title") if container else None
                
                if title_tag:
                    raw_title = title_tag.get_text(strip=True)
                    # Extract pure company name from format "Company Name | LinkedIn"
                    name = raw_title.split("|")[0].split("-")[0].replace("LinkedIn", "").strip()
                    name_lower = name.lower()
                    
                    if name and len(name) < 50 and name_lower not in seen:
                        seen.add(name_lower)
                        results.append({
                            "name": name,
                            "website": "",
                            "linkedin": link,
                            "source": "LinkedIn",
                            "source_url": link
                        })
                        
                        if len(results) >= num_results:
                            break
                            
        return results
    except Exception as e:
        print(f"LinkedIn Free Scraper Error: {e}")
        return []