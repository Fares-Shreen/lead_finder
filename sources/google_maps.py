import requests
from bs4 import BeautifulSoup

def search_google_maps(field, location, num_results, start=0, api_key=None):
    # Free general local search equivalent
    url = "https://html.duckduckgo.com/html/"
    search_query = f'"{field}" companies in "{location}"'
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    data = {'q': search_query, 's': start}
    
    try:
        res = requests.post(url, headers=headers, data=data, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        results = []
        seen = set()
        
        for item in soup.find_all("div", class_="result__body"):
            title_tag = item.find("h2", class_="result__title")
            a_tag = item.find("a", class_="result__url")
            
            if not title_tag or not a_tag: 
                continue
                
            title = title_tag.text.strip()
            link = a_tag.get("href", "")
            
            # Clean up SEO title tags to extract the core company name
            company = title.split("|")[0].split("-")[0].split(":")[0].strip()
            
            if company and len(company) < 50 and company not in seen:
                seen.add(company)
                results.append({
                    "name": company,
                    "website": link,
                    "linkedin": "",
                    "emails": [],
                    "phones": [],
                    "source": "Web Search (Free)",
                    "source_url": link
                })
                
                if len(results) >= num_results: 
                    break
                    
        return results
    except Exception as e:
        print(f"Web Free Scraper Error: {e}")
        return []