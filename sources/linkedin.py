from playwright.sync_api import sync_playwright
from urllib.parse import quote
import time

def search_linkedin_companies(field, location, num_results, start=0, api_key=None):
    # Using DuckDuckGo native search via browser to find LinkedIn pages
    query = quote(f'site:eg.linkedin.com/company "{field}" "{location}"')
    url = f"https://duckduckgo.com/?q={query}&t=h_&ia=web"
    
    results = []
    seen = set()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = context.new_page()
            
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)  # Give DuckDuckGo a second to load results
            
            # Extract links directly from DuckDuckGo search results
            search_results = page.locator("a[data-testid='result-title-a']").all()
            for a_tag in search_results:
                title = a_tag.inner_text().strip()
                href = a_tag.get_attribute("href")
                
                if "linkedin.com/company" in href:
                    # Clean up "Company Name | LinkedIn"
                    name = title.split("|")[0].split("-")[0].replace("LinkedIn", "").strip()
                    
                    if name and name.lower() not in seen:
                        seen.add(name.lower())
                        results.append({
                            "name": name,
                            "website": "",
                            "linkedin": href,
                            "source": "LinkedIn",
                            "source_url": href
                        })
                        
                        if len(results) >= num_results: 
                            break
            browser.close()
    except Exception as e:
        print(f"LinkedIn Playwright Error: {e}")
        
    return results