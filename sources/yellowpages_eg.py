from playwright.sync_api import sync_playwright
from urllib.parse import quote

def search_yellowpages(field, location, num_results, start=0, api_key=None):
    city = location.split(",")[0].strip().replace(" ", "-")
    clean_field = quote(field.replace(" ", "-"))
    page_num = (start // 15) + 1
    url = f"https://yellowpages.com.eg/en/search/{clean_field}/{city}/p{page_num}"
    
    results = []
    seen = set()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = context.new_page()
            
            # Yellowpages blocks requests heavily, Playwright handles the JS challenge
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            links = page.locator("a[href*='/en/profile/'], a[href*='/en/short-profile/']").all()
            for a in links:
                name = a.inner_text().strip()
                name_lower = name.lower()
                href = a.get_attribute("href")
                
                invalid_terms = ["yellowpages", "profile", "category", "more info", "call now", "review"]
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
            browser.close()
    except Exception as e:
        print(f"Yellow Pages Playwright Error: {e}")
        
    return results