from playwright.sync_api import sync_playwright
from urllib.parse import quote
import time

def search_google_maps(field, location, num_results, start=0, api_key=None):
    # Using DuckDuckGo native search for local business discovery
    query = quote(f'"{field}" companies in "{location}" -site:linkedin.com -site:facebook.com')
    url = f"https://duckduckgo.com/?q={query}&t=h_&ia=web"
    
    results = []
    seen = set()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = context.new_page()
            
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2) 
            
            search_results = page.locator("a[data-testid='result-title-a']").all()
            for a_tag in search_results:
                title = a_tag.inner_text().strip()
                href = a_tag.get_attribute("href")
                
                # Clean SEO descriptions to grab company name
                name = title.split("|")[0].split("-")[0].split(":")[0].strip()
                
                if name and len(name) < 45 and name.lower() not in seen:
                    seen.add(name.lower())
                    results.append({
                        "name": name,
                        "website": href,
                        "linkedin": "",
                        "emails": [],
                        "phones": [],
                        "source": "Web Search (Free)",
                        "source_url": href
                    })
                    
                    if len(results) >= num_results: 
                        break
            browser.close()
    except Exception as e:
        print(f"Web Search Playwright Error: {e}")
        
    return results