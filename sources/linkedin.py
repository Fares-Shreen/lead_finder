import requests
from bs4 import BeautifulSoup

def search_linkedin_companies(field, location, num_results, start=0, api_key=None):
    # Use DuckDuckGo HTML for a CAPTCHA-free web search
    url = "https://html.duckduckgo.com/html/"
    search_query = f'site:eg.linkedin.com/company "{field}" "{location}"'
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    data = {'q': search_query, 's': start} # 's' handles DDG pagination
    
    try:
        res = requests.post(url, headers=headers, data=data, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        results = []
        
        for a in soup.find_all("a", class_="result__url"):
            link = a.get("href", "")
            if "linkedin.com/company" in link:
                # Extract title from the parent body
                body = a.find_parent("div", class_="result__body")
                title_tag = body.find("h2", class_="result__title") if body else None
                
                if title_tag:
                    title = title_tag.text.strip()
                    company = title.split("|")[0].split("-")[0].strip()
                    
                    if company and "LinkedIn" not in company:
                        results.append({
                            "name": company,
                            "website": "",
                            "linkedin": link,
                            "source": "LinkedIn",
                            "source_url": link
                        })
                        
                        if len(results) >= num_results:
                            break
                            
        return results
    except Exception as e:
        print(f"LinkedIn Free DDG Error: {e}")
        return []