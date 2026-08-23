import os
import time
from datetime import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
import streamlit as st

def _get_gspread_client():
    """Initializes Google Sheets client using Streamlit secrets with forced key cleanup."""
    try:
        import gspread
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # ---------------------------------------------------------
        # THE ULTIMATE KEY CLEANER
        # ---------------------------------------------------------
        key = creds_dict["private_key"]
        
        # 1. Convert literal text slashes to real newlines
        key = key.replace("\\n", "\n") 
        
        # 2. Strip hidden spaces from the beginning/end of every single line
        key = "\n".join([line.strip() for line in key.split("\n") if line.strip()])
        
        creds_dict["private_key"] = key
        
        # Use gspread's native dictionary login
        return gspread.service_account_from_dict(creds_dict)
        
    except Exception as e:
        print(f"Google Sheets Auth Error: {e}")
        return None

def _sync_to_google_sheet(new_list, sheet_tab_name):
    """Pulls data from Google Sheet, merges new data, removes duplicates, and updates."""
    client = _get_gspread_client()
    
    # Fail gracefully if secrets aren't set up yet
    if not client or "sheet" not in st.secrets:
        return None

    sheet_name = st.secrets["sheet"]["name"]

    try:
        sh = client.open(sheet_name)
        try:
            worksheet = sh.worksheet(sheet_tab_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=sheet_tab_name, rows=100, cols=20)

        existing_data = worksheet.get_all_records()
        
        if new_list:
            df_new = pd.DataFrame(new_list)
            if "Status" not in df_new.columns:
                df_new["Status"] = "Pending"

            if existing_data:
                df_old = pd.DataFrame(existing_data)
                df_combined = pd.concat([df_old, df_new], ignore_index=True)
                df_combined.drop_duplicates(subset=["Company Name"], keep="first", inplace=True)
            else:
                df_combined = df_new

            worksheet.clear()
            worksheet.update([df_combined.columns.values.tolist()] + df_combined.values.tolist())
            return df_combined
        elif existing_data:
            return pd.DataFrame(existing_data)
        
        return pd.DataFrame()
    except Exception as e:
        print(f"Error syncing with Google Sheets: {e}")
        return None

def _parse_days_ago(iso_string):
    if not iso_string or iso_string == "Not Found":
        return 9999
    try:
        dt = pd.to_datetime(iso_string).tz_localize(None)
        now = pd.to_datetime(datetime.now()).tz_localize(None)
        return (now - dt).days
    except Exception:
        return 9999

def _extract_podio_data(page):
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
        browser = p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
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
                                "Action": "Apply to get this account",
                                "Status": "Pending"
                            })
                    continue

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
                    first_activity = timestamps[0] if timestamps else None
                    days_ago = _parse_days_ago(first_activity)

                    if progress_cb: progress_cb(f"  🟢 Found in Companies! (LC: {committee}, Inactive: {days_ago} days)")

                    if days_ago > 15:
                        excel_2_companies_to_take.append({
                            "Company Name": name,
                            "Company Link": page.url,
                            "Local Committee": committee,
                            "First Activity Date": first_activity or "No Comments",
                            "Days Since Activity": days_ago,
                            "Action": "Company we can take",
                            "Status": "Pending"
                        })
                    continue

                if progress_cb: progress_cb(f"  ✨ Genuine New Lead!")
                new_leads_to_enrich.append(lead)

            except Exception as e:
                if progress_cb: progress_cb(f"  ❌ Error checking {name}: {e}")
                new_leads_to_enrich.append(lead)

        browser.close()

    # PUSH TO GOOGLE SHEETS!
    _sync_to_google_sheet(excel_1_deal_accounts, "Excel_1_Deals")
    _sync_to_google_sheet(excel_2_companies_to_take, "Excel_2_Companies")

    return excel_1_deal_accounts, excel_2_companies_to_take, new_leads_to_enrich, "Google Sheets (Excel 1)", "Google Sheets (Excel 2)"