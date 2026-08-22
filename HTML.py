import os
import time
from playwright.sync_api import sync_playwright

def main():
    email = os.environ.get("PODIO_EMAIL", "")
    password = os.environ.get("PODIO_PASSWORD", "")
    company_to_search = "Objects"  # The example company you requested

    if not email or not password:
        print("Please set PODIO_EMAIL and PODIO_PASSWORD environment variables.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        print("1. Logging into Podio...")
        page.goto("https://podio.com/login", wait_until="domcontentloaded")
        page.fill('input[name="email"], input[type="email"]', email)
        page.fill('input[name="password"], input[type="password"]', password)
        page.click('button[type="submit"]')
        
        page.wait_for_url("**/podio.com/**", timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        print("   ✅ Login successful!")
        time.sleep(3)

        print("2. Navigating to Deals App...")
        try:
            page.goto("https://podio.com/aiesecglobal/ams-for-aiesec-in-egypt/apps/deals", wait_until="domcontentloaded")
        except Exception:
            time.sleep(2)
            page.goto("https://podio.com/aiesecglobal/ams-for-aiesec-in-egypt/apps/deals", wait_until="domcontentloaded")
            
        time.sleep(4)

        print(f"3. Searching for '{company_to_search}'...")
        search_icon = page.locator('.global-search-trigger, .icon-search, a[title*="Search"], button[aria-label="Search"]').first
        search_icon.click()
        time.sleep(1.5) 

        page.keyboard.type(company_to_search)
        page.keyboard.press("Enter")
        
        print("4. Waiting for search results...")
        time.sleep(5) 

        first_result = page.locator('.search-results a, .global-search-results a, .search-result-item, .search-result-title').first
        
        if first_result.is_visible():
            print("   ✅ Result found! Clicking the item...")
            first_result.click()
        else:
            print("   ❌ No results found for this company.")
            browser.close()
            return

        print("5. Extracting Data...")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(6) 
        
        # Save the full page HTML locally just to be absolutely sure we have it
        full_html = page.content()
        with open("podio_item_page.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("   ✅ Saved full page HTML to 'podio_item_page.html' in your folder.")

        # Find the HTML immediately surrounding our target fields
        committee_html = page.evaluate('''() => {
            let els = Array.from(document.querySelectorAll('*'));
            let label = els.find(e => e.textContent.trim() === '* Local Committee' || e.textContent.trim() === 'Local Committee');
            return label && label.parentElement ? label.parentElement.innerHTML : "Not found";
        }''')

        stage_html = page.evaluate('''() => {
            let els = Array.from(document.querySelectorAll('*'));
            let label = els.find(e => e.textContent.trim() === '* Deal stage' || e.textContent.trim() === 'Deal stage');
            return label && label.parentElement ? label.parentElement.innerHTML : "Not found";
        }''')

        print("\n--- LOCAL COMMITTEE HTML ---")
        print(committee_html[:2000])
        
        print("\n--- DEAL STAGE HTML ---")
        print(stage_html[:2000])
        
        print("---------------------------\n")
        print("Test complete! Check the console output.")
        browser.close()

if __name__ == "__main__":
    main()