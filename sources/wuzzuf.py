from playwright.sync_api import sync_playwright
from urllib.parse import quote

def search_wuzzuf(field, location, num_results, start=0, api_key=None):
    page_num = start // 15
    query = quote(f"{field} {location}")
    url = f"https://wuzzuf.net/search/jobs/?q={query}&start={page_num}"
    
    results = []
    seen = set()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Simulating a real user to bypass blocks
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = context.new_page()
            
            # Go to Wuzzuf
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # Find all links to company pages
            links = page.locator("a[href*='/jobs/careers/']").all()
            for a in links:
                name = a.inner_text().replace("-", "").strip()
                name_lower = name.lower()
                href = a.get_attribute("href")
                
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
            browser.close()
    except Exception as e:
        print(f"Wuzzuf Playwright Error: {e}")
        
    return results