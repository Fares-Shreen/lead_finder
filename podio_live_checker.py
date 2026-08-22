import os
import time
from datetime import datetime
import pandas as pd
from playwright.sync_api import sync_playwright

def _parse_days_ago(iso_string):
    """Converts Podio's ISO timestamp into 'days ago' integer."""
    if not iso_string or iso_string == "Not Found":
        return 9999
    try:
        dt = pd.to_datetime(iso_string).tz_localize(None)
        now = pd.to_datetime(datetime.now()).tz_localize(None)
        return (now - dt).days
    except Exception:
        return 9999

def _extract_podio_data(page):
    """Uses the exact HTML structure we found to extract the active fields."""
    committee = page.evaluate('''() => {
        let field = Array.from(document.querySelectorAll('li.category-field')).find(el => el.innerText.includes('Local Committee'));
        if (field) {
            let selected = field.querySelector('li.selected');
            if (selected) return selected.innerText.trim();
        }
        return "Not Found";
    }''')

    stage = page.evaluate('''() => {
        let field = Array.from(document.querySelectorAll('li.category-field')).find(el => el.innerText.includes('Deal stage') || el.innerText.includes('Deal Stage'));
        if (field) {
            let selected = field.querySelector('li.selected');
            if (selected) return selected.innerText.trim();
        }
        return "Not Found";
    }''')

    timestamps = page.evaluate('''() => {
        let times = Array.from(document.querySelectorAll('.item-activity-wrapper time.timestamp'));
        return times.map(t => t.getAttribute('datetime')).filter(t => t);
    }''')

    return committee, stage, timestamps

def analyze_leads_live(candidate_leads, email, password, progress_cb=None):
    excel_1_deal_accounts = []
    excel_2_companies_to_take = []
    new_leads_to_enrich = []

    if not candidate_leads:
        return [], [], [], None, None

    if not email or not password:
        if progress_cb: progress_cb("⚠️ Missing Podio credentials. Skipping Podio check.")
        return [], [], candidate_leads, None, None

    with sync_playwright() as p:
        # Running visible at high speed so you can watch it work!
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        if progress_cb: progress_cb("🔐 Logging into Podio...")
        page.goto("https://podio.com/login", wait_until="domcontentloaded")
        page.fill('input[name="email"], input[type="email"]', email)
        page.fill('input[name="password"], input[type="password"]', password)
        page.click('button[type="submit"]')

        try:
            page.wait_for_url("**/podio.com/**", timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
        except Exception:
            if progress_cb: progress_cb("❌ Podio Login failed. Check credentials.")
            return [], [], candidate_leads, None, None

        for lead in candidate_leads:
            name = lead["name"]
            if progress_cb: progress_cb(f"🔎 Checking Podio for: {name}")

            try:
                # ==========================================
                # STEP 1: SEARCH DEALS APP
                # ==========================================
                try:
                    page.goto("https://podio.com/aiesecglobal/ams-for-aiesec-in-egypt/apps/deals", wait_until="domcontentloaded")
                except:
                    time.sleep(2)
                    page.goto("https://podio.com/aiesecglobal/ams-for-aiesec-in-egypt/apps/deals", wait_until="domcontentloaded")
                time.sleep(2)

                page.locator('.global-search-trigger, .icon-search, button[aria-label="Search"]').first.click()
                time.sleep(1)
                page.keyboard.type(name)
                page.keyboard.press("Enter")
                time.sleep(4)

                first_result = page.locator('.search-results a, .search-result-item').first
                if first_result.is_visible():
                    first_result.click()
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(4)

                    committee, stage, timestamps = _extract_podio_data(page)
                    # For Deals, we use the LAST comment (newest activity)
                    last_activity = timestamps[-1] if timestamps else None
                    days_ago = _parse_days_ago(last_activity)

                    if progress_cb: progress_cb(f"  🟡 Found in Deals! (Stage: {stage}, LC: {committee}, Inactive: {days_ago} days)")

                    is_alex = "alexandria" in committee.lower()
                    is_active_stage = "raised" in stage.lower() or "signed" in stage.lower()

                    if not is_active_stage:
                        if is_alex or days_ago > 15:
                            excel_1_deal_accounts.append({
                                "Company Name": name,
                                "Deal Link": page.url,
                                "Local Committee": committee,
                                "Deal Stage": stage,
                                "Last Activity": last_activity or "No Comments",
                                "Days Inactive": days_ago,
                                "Action": "Apply to get this account"
                            })
                    continue # Skip to the next lead

                # ==========================================
                # STEP 2: SEARCH COMPANIES APP
                # ==========================================
                try:
                    page.goto("https://podio.com/aiesecglobal/ams-for-aiesec-in-egypt/apps/companies", wait_until="domcontentloaded")
                except:
                    time.sleep(2)
                    page.goto("https://podio.com/aiesecglobal/ams-for-aiesec-in-egypt/apps/companies", wait_until="domcontentloaded")
                time.sleep(2)

                page.locator('.global-search-trigger, .icon-search, button[aria-label="Search"]').first.click()
                time.sleep(1)
                page.keyboard.type(name)
                page.keyboard.press("Enter")
                time.sleep(4)

                first_result = page.locator('.search-results a, .search-result-item').first
                if first_result.is_visible():
                    first_result.click()
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(4)

                    committee, stage, timestamps = _extract_podio_data(page)
                    # For Companies, we use the FIRST comment (oldest activity)
                    first_activity = timestamps[0] if timestamps else None
                    days_ago = _parse_days_ago(first_activity)

                    if progress_cb: progress_cb(f"  🟢 Found in Companies! (LC: {committee}, Inactive: {days_ago} days)")

                    # Applies to ALL LCs if inactive > 15 days
                    if days_ago > 15:
                        excel_2_companies_to_take.append({
                            "Company Name": name,
                            "Company Link": page.url,
                            "Local Committee": committee,
                            "First Activity Date": first_activity or "No Comments",
                            "Days Since Activity": days_ago,
                            "Action": "Company we can take"
                        })
                    continue # Skip to the next lead

                # ==========================================
                # STEP 3: NOT FOUND ANYWHERE -> NEW LEAD
                # ==========================================
                if progress_cb: progress_cb(f"  ✨ Genuine New Lead!")
                new_leads_to_enrich.append(lead)

            except Exception as e:
                if progress_cb: progress_cb(f"  ❌ Error checking {name}: {e}")
                new_leads_to_enrich.append(lead) # Failsafe: treat as new lead if Podio glitches

        browser.close()

    # === REPLACE EVERYTHING AFTER browser.close() WITH THIS ===

    # Save outputs with persistence, deduplication, and a Status column
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    def _save_persistent_excel(new_list, filename):
        path = os.path.join(OUTPUT_DIR, filename)
        
        if not new_list:
            # If no new data, just return the path if it already exists
            return path if os.path.exists(path) else None

        df_new = pd.DataFrame(new_list)
        df_new["Status"] = "Pending"  # Add the default status for the UI dropdown

        if os.path.exists(path):
            df_old = pd.read_excel(path)
            # Combine old and new data
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            # Drop duplicates by Company Name. Keep "first" so we don't overwrite existing "Checked" statuses!
            df_combined.drop_duplicates(subset=["Company Name"], keep="first", inplace=True)
        else:
            df_combined = df_new

        df_combined.to_excel(path, index=False)
        return path

    path1 = _save_persistent_excel(excel_1_deal_accounts, "excel_1_deal_accounts.xlsx")
    path2 = _save_persistent_excel(excel_2_companies_to_take, "excel_2_companies_to_take.xlsx")

    return excel_1_deal_accounts, excel_2_companies_to_take, new_leads_to_enrich, path1, path2