import os
import sys
import time
import asyncio
import datetime
import requests
import pandas as pd
import streamlit as st

os.system("playwright install chromium")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import dedupe
import config
from search_engine import process
import podio_live_checker

st.set_page_config(page_title="Company Lead Finder", page_icon="🔎", layout="wide")

hide_streamlit_style = """
    <style>
    div[data-testid="stToolbar"] {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("🔎 Company Lead Finder")
st.caption("Directory scraper, live Podio cross-referencer, and real-time Action Hub.")

# Session state initialization
if "serpapi_key" not in st.session_state: st.session_state.serpapi_key = config.SERPAPI_KEY or ""
if "podio_email" not in st.session_state: st.session_state.podio_email = os.environ.get("PODIO_EMAIL", "")
if "podio_password" not in st.session_state: st.session_state.podio_password = os.environ.get("PODIO_PASSWORD", "")
if "is_admin" not in st.session_state: st.session_state.is_admin = False

col_api, col_podio = st.columns(2)
with col_api:
    with st.expander("🔑 SerpApi Key", expanded=not st.session_state.serpapi_key):
        st.session_state.serpapi_key = st.text_input("SerpApi API Key", value=st.session_state.serpapi_key, type="password")
        st.markdown("""
        <small>
        <b>How to get your free key:</b><br>
        1. <a href="https://serpapi.com/users/sign_up" target="_blank">Click here to sign up on SerpApi</a>.<br>
        2. Verify your email address.<br>
        3. Copy the "Your Private API Key" from your dashboard and paste it above.
        </small>
        """, unsafe_allow_html=True)

with col_podio:
    with st.expander("🔷 Podio Credentials", expanded=not (st.session_state.podio_email and st.session_state.podio_password)):
        st.session_state.podio_email = st.text_input("Podio Email", value=st.session_state.podio_email)
        st.session_state.podio_password = st.text_input("Podio Password", value=st.session_state.podio_password, type="password")

st.divider()

# --- PREDICTIVE LEAD SCORING HELPER ---
def apply_lead_scoring(df):
    """Assigns a score of Hot, Warm, or Cold based on available contact info richness."""
    if df.empty: return df
    df_copy = df.copy()
    
    scores = []
    for _, row in df_copy.iterrows():
        score = 0
        if row.get("phones"): score += 40
        if row.get("emails"): score += 30
        if row.get("linkedin"): score += 20
        if row.get("website"): score += 10
        
        if score >= 70: scores.append("🔥 Hot")
        elif score >= 40: scores.append("☀️ Warm")
        else: scores.append("❄️ Cold")
        
    if "Lead Score" not in df_copy.columns:
        df_copy.insert(0, "Lead Score", scores)
    else:
        df_copy["Lead Score"] = scores
    return df_copy

# --- CONFIRMATION DIALOG MODAL ---
@st.dialog("⚠️ Confirm Status Change")
def confirm_status_dialog(target_type, company_name, current_val, row_idx=None, sheet_tab=None):
    action_text = "mark this company as **USED / CHECKED** (turns green)" if not current_val else "uncheck this company (return to normal)"
    st.write(f"Are you sure you want to {action_text} for **{company_name}**?")
    
    if current_val and not st.session_state.is_admin:
        st.warning("🔒 Only an Admin can uncheck an already used company.")
        admin_pass = st.text_input("Enter Admin Password to proceed:", type="password")
        if st.button("Confirm Uncheck", type="primary"):
            if admin_pass == config.ADMIN_PASSWORD:
                _execute_status_change(target_type, company_name, False, row_idx, sheet_tab)
                st.success("Admin authorized. Status reset.")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Incorrect Admin Password.")
    else:
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ Yes, Confirm", type="primary", use_container_width=True):
                _execute_status_change(target_type, company_name, not current_val, row_idx, sheet_tab)
                st.rerun()
        with col_no:
            if st.button("❌ Cancel", use_container_width=True):
                st.rerun()

def _execute_status_change(target_type, company_name, new_val, row_idx=None, sheet_tab=None):
    if target_type == "local":
        dedupe.update_company_status(company_name, new_val)
    elif target_type == "sheet":
        client = podio_live_checker._get_gspread_client()
        sh = client.open(st.secrets["sheet"]["name"])
        ws = sh.worksheet(sheet_tab)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%d")
        df.at[row_idx, "Status"] = "Checked" if new_val else "Pending"
        df.at[row_idx, "Checked_Date"] = now_str if new_val else ""
        
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())

    # --- AUTOMATED WEBHOOK (CRM PUSH) ---
    if new_val == True: 
        try:
            with dedupe._conn() as c:
                row = c.execute("SELECT * FROM companies WHERE name_normalized = ?", (dedupe._normalize(company_name),)).fetchone()
                
            if row:
                webhook_payload = {
                    "company_name": row[1],
                    "field": row[2],
                    "location": row[3],
                    "website": row[4],
                    "linkedin": row[5],
                    "emails": row[6],
                    "phones": row[7]
                }
                
                # Replace this URL with your actual Zapier / Make.com webhook URL
                webhook_url = "https://hooks.zapier.com/hooks/catch/your_id_here/"
                try:
                    requests.post(webhook_url, json=webhook_payload, timeout=2)
                except requests.exceptions.RequestException:
                    pass # Ignore timeouts if the dummy URL is still in place
        except Exception as e:
            print(f"Webhook failed: {e}")

# --- 15-DAY RESET HELPER ---
def apply_15_day_reset(df):
    if "Status" not in df.columns: df["Status"] = "Pending"
    if "Checked_Date" not in df.columns: df["Checked_Date"] = ""
    
    now = datetime.datetime.now()
    changed = False
    for idx, row in df.iterrows():
        if row["Status"] == "Checked":
            date_str = str(row.get("Checked_Date", "")).strip()
            if not date_str:
                df.at[idx, "Checked_Date"] = now.strftime("%Y-%m-%d")
                changed = True
            else:
                try:
                    checked_date = pd.to_datetime(date_str)
                    if (now - checked_date).days > 15:
                        df.at[idx, "Status"] = "Pending"
                        df.at[idx, "Checked_Date"] = ""
                        changed = True
                except Exception:
                    df.at[idx, "Checked_Date"] = now.strftime("%Y-%m-%d")
                    changed = True
    return df, changed

def highlight_green(row):
    status_val = str(row.get("Status", ""))
    is_confirmed = str(row.get("confirmed", ""))
    if status_val == "Checked" or is_confirmed in ["1", "True", "true"]:
        return ["background-color: #d4edda; color: #155724; font-weight: 500;"] * len(row)
    return [""] * len(row)

tab_search, tab_manual, tab_upload, tab_action_hub, tab_database, tab_admin = st.tabs([
    "🔎 Run Search", 
    "🕵️ Manual Deep Check", 
    "📁 Upload Custom List", 
    "✅ Team Action Hub", 
    "📋 Local Database", 
    "🔐 Admin"
])

# =========================================================================
# TAB 1: RUN SEARCH
# =========================================================================
with tab_search:
    col1, col2 = st.columns(2)
    with col1:
        field_choices = st.multiselect(
            "Select Fields",
            ["Software", "IT", "Digital Marketing", "Sales", "Video Editing", "Accounting", "English Teaching", "French Teaching"],
            default=["Software"]
        )
    with col2:
        custom_fields_input = st.text_input("And/or enter custom fields", placeholder="e.g. Real Estate")

    fields_to_search = list(field_choices)
    if custom_fields_input.strip():
        fields_to_search.extend([x.strip() for x in custom_fields_input.split(",") if x.strip()])
    fields_to_search = list(set(fields_to_search))

    with st.form("search_form"):
        location = st.text_input("Location", value="Alexandria, Egypt")
        sources = st.multiselect(
            "Search on",
            ["Google Maps", "LinkedIn", "Yellow Pages", "Wuzzuf", "Indeed"],
            default=["Google Maps", "LinkedIn", "Wuzzuf", "Indeed"]
        )
        num_per_source = st.slider("Results per source (per field)", 10, 100, 25)
        restart = st.checkbox("Start this field + location over from the beginning", value=False)
        submitted = st.form_submit_button("🚀 Run Pipeline")

    status_box = st.empty()
    log_lines = []
    def progress_cb(msg):
        log_lines.append(msg)
        status_box.code("\n".join(log_lines[-15:]))

    if submitted:
        if not fields_to_search or not sources:
            st.warning("⚠️ Please select fields and sources.")
        elif not st.session_state.podio_email or not st.session_state.podio_password:
            st.error("⚠️ Podio credentials are required.")
        else:
            if restart:
                dedupe.init_db()
                for s in sources:
                    for f in fields_to_search:
                        dedupe.reset_search_offset(s, f, location)

            total_clean, total_suspects = 0, 0
            for current_field in fields_to_search:
                with st.spinner(f"Running pipeline for {current_field}..."):
                    clean_leads, suspect_leads = process(
                        current_field, location, sources, num_per_source, progress_cb,
                        api_key=st.session_state.serpapi_key or None,
                        podio_email=st.session_state.podio_email,
                        podio_password=st.session_state.podio_password
                    )
                    total_clean += len(clean_leads)
                    total_suspects += len(suspect_leads)
            
            st.success(f"Pipeline Complete! ✅ {total_clean} new leads saved directly to DB. 🕵️ {total_suspects} suspects routed to Manual Check.")

# =========================================================================
# TAB 2: MANUAL DEEP CHECK (PLAYWRIGHT)
# =========================================================================
with tab_manual:
    st.markdown("### 🕵️ Need Podio Check Queue")
    st.caption("These fully-enriched companies triggered a flag on the fast API. Run Playwright to verify them.")
    
    suspects = dedupe.get_suspects_from_sheet()
    
    if not suspects:
        st.success("🎉 No suspects in the queue! You are all caught up.")
    else:
        st.info(f"There are **{len(suspects)}** companies waiting for deep Playwright verification.")
        df_sus = pd.DataFrame(suspects)
        st.dataframe(df_sus, use_container_width=True)
        
        batch_size = st.slider("Select batch size to process:", 5, 50, 25)
        
        check_status = st.empty()
        log_lines_p = []
        def prog_playwright(msg):
            log_lines_p.append(msg)
            check_status.code("\n".join(log_lines_p[-10:]))
            
        if st.button("🤖 Run Playwright Deep Check"):
            batch = suspects[:batch_size]
            names_to_remove = [c["name"] for c in batch]
            
            with st.spinner("Firing up Playwright headless browser..."):
                excel1, excel2, cleared = podio_live_checker.analyze_leads_live(
                    batch, st.session_state.podio_email, st.session_state.podio_password, prog_playwright
                )
            
            for lead in cleared:
                dedupe.add_company(lead)
            dedupe.sync_to_google_sheets()
            
            dedupe.remove_suspects_from_sheet(names_to_remove)
            st.success(f"Processed! {len(excel1)} to Deals, {len(excel2)} to Companies, {len(cleared)} safely moved to Local DB.")
            time.sleep(2)
            st.rerun()

# =========================================================================
# TAB 3: UPLOAD CUSTOM LIST
# =========================================================================
with tab_upload:
    st.markdown("### 📁 Upload Custom Excel / CSV")
    st.caption("Upload your own list of companies to automatically check them against Podio and route to Excel 1 & 2.")
    
    uploaded_file = st.file_uploader("Upload File (.xlsx, .csv)", type=["xlsx", "xls", "csv"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)
                
            st.dataframe(df_upload.head(5), use_container_width=True)
            
            col_options = df_upload.columns.tolist()
            name_col = st.selectbox("Which column contains the Company Name?", col_options)
            
            if st.button("🤖 Run Podio Check on Uploaded List", type="primary"):
                custom_candidates = []
                for _, row in df_upload.iterrows():
                    comp_name = str(row[name_col]).strip()
                    if comp_name and comp_name.lower() != "nan":
                        custom_candidates.append({
                            "name": comp_name,
                            "field": "Custom Upload",
                            "location": "Custom Upload",
                            "source": "Manual Upload"
                        })
                        
                if not custom_candidates:
                    st.warning("No valid company names found in the selected column.")
                else:
                    upload_status = st.empty()
                    upload_logs = []
                    def prog_upload(msg):
                        upload_logs.append(msg)
                        upload_status.code("\n".join(upload_logs[-10:]))
                        
                    with st.spinner(f"Processing {len(custom_candidates)} uploaded companies through Playwright..."):
                        ex1, ex2, cleared = podio_live_checker.analyze_leads_live(
                            custom_candidates, st.session_state.podio_email, st.session_state.podio_password, prog_upload
                        )
                        
                        for lead in cleared:
                            dedupe.add_company(lead)
                        dedupe.sync_to_google_sheets()
                        
                    st.success(f"Upload Processed! ✅ {len(ex1)} routed to Deals (Excel 1), {len(ex2)} routed to Companies (Excel 2).")
                    if cleared:
                        st.info(f"{len(cleared)} companies were completely new and have been saved to your Local Database.")
        except Exception as e:
            st.error(f"Error processing file: {e}")

# =========================================================================
# TAB 4: TEAM ACTION HUB
# =========================================================================
with tab_action_hub:
    st.markdown("### Team Action Hub (Google Sheets)")
    st.caption("Checked items turn green and automatically reset to Pending after 15 days.")

    client = podio_live_checker._get_gspread_client()
    sheet_name = st.secrets["sheet"]["name"] if client and "sheet" in st.secrets else None

    if client and sheet_name:
        try:
            sh = client.open(sheet_name)

            def render_hub_table(ws_name, title):
                st.subheader(title)
                try:
                    ws = sh.worksheet(ws_name)
                    data = ws.get_all_records()
                    if not data:
                        st.info(f"No records in {ws_name}.")
                        return

                    df = pd.DataFrame(data)
                    df, reset_happened = apply_15_day_reset(df)
                    if reset_happened:
                        ws.clear()
                        ws.update([df.columns.values.tolist()] + df.values.tolist())

                    col_sel, col_btn = st.columns([3, 1])
                    with col_sel:
                        company_names = df["Company Name"].tolist() if "Company Name" in df.columns else df.iloc[:, 0].tolist()
                        selected_target = st.selectbox(f"Select company to change status ({ws_name}):", company_names, key=f"select_{ws_name}")
                    with col_btn:
                        st.write("")
                        st.write("")
                        target_row_idx = company_names.index(selected_target)
                        current_state = df.at[target_row_idx, "Status"] == "Checked"
                        btn_label = "Uncheck" if current_state else "✅ Check & Use"
                        if st.button(btn_label, key=f"btn_pop_{ws_name}"):
                            confirm_status_dialog("sheet", selected_target, current_state, target_row_idx, ws_name)

                    # Apply predictive scoring for display only
                    df_display = apply_lead_scoring(df)

                    st.dataframe(
                        df_display.style.apply(highlight_green, axis=1),
                        column_config={
                            "Deal Link": st.column_config.LinkColumn(),
                            "Company Link": st.column_config.LinkColumn(),
                            "Checked_Date": st.column_config.TextColumn("Date Used"),
                            "Lead Score": st.column_config.TextColumn("Score")
                        },
                        use_container_width=True
                    )
                except Exception as ex:
                    st.info(f"Tab '{ws_name}' is currently empty or loading: {ex}")

            render_hub_table("Excel_1_Deals", "🟡 Excel 1: Deal Accounts")
            st.divider()
            render_hub_table("Excel_2_Companies", "🟢 Excel 2: Companies to Take")

        except Exception as e:
            st.error(f"Failed to connect to Google Sheets tabs: {e}")
    else:
        st.warning("⚠️ Google Sheets credentials are not configured in Streamlit Secrets.")

# =========================================================================
# TAB 5: LOCAL DATABASE
# =========================================================================
with tab_database:
    dedupe.init_db()
    
    is_admin = st.session_state.get("is_admin", False)
    existing = dedupe.all_companies(include_confirmed=is_admin)
    
    if is_admin:
        st.markdown(f"### 📋 Local Master Database - ADMIN VIEW ({len(existing)} companies)")
        st.caption("Admin mode: Viewing ALL companies including Checked ones.")
    else:
        st.markdown(f"### 📋 Local Master Database ({len(existing)} pending companies)")
        st.caption("Checked companies are hidden from this view. Use the Admin panel to inspect checked leads.")
    
    if existing:
        df_local = pd.DataFrame(existing)
        df_local["Status"] = df_local["confirmed"].apply(lambda x: "Checked" if x == 1 else "Pending")

        col_db_sel, col_db_btn = st.columns([3, 1])
        with col_db_sel:
            chosen_comp = st.selectbox("Select company to update status:", df_local["name"].tolist(), key="local_db_comp_select")
        with col_db_btn:
            st.write("")
            st.write("")
            if chosen_comp:
                is_checked = df_local.loc[df_local["name"] == chosen_comp, "confirmed"].values[0] == 1
                btn_txt = "Uncheck" if is_checked else "✅ Check & Lock"
                if st.button(btn_txt, key="btn_local_db_confirm"):
                    confirm_status_dialog("local", chosen_comp, is_checked)

        # Apply lead scoring for display
        df_local = apply_lead_scoring(df_local)

        display_cols = ["Lead Score", "name", "field", "location", "website", "linkedin", "emails", "phones", "source", "source_url", "Status", "checked_date", "found_at"]
        clean_display_cols = [c for c in display_cols if c in df_local.columns]
        
        st.dataframe(
            df_local[clean_display_cols].style.apply(highlight_green, axis=1),
            column_config={
                "website": st.column_config.LinkColumn(),
                "source_url": st.column_config.LinkColumn(),
                "linkedin": st.column_config.LinkColumn(),
                "checked_date": st.column_config.TextColumn("Date Checked"),
                "Lead Score": st.column_config.TextColumn("Score")
            },
            use_container_width=True
        )
    else:
        st.info("No available companies to display.")

# =========================================================================
# TAB 6: ADMIN CONTROLS
# =========================================================================
with tab_admin:
    st.markdown("### 🔐 Admin Panel")
    admin_pw = st.text_input("Admin Password", type="password", key="admin_panel_pw")
    
    if admin_pw and admin_pw == config.ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("Admin mode unlocked.")
        
        tab_checked, tab_dash, tab_del, tab_danger = st.tabs([
            "🟢 Checked Companies", 
            "📊 Dashboard", 
            "🗑️ Delete from Local DB", 
            "⚠️ Danger Zone"
        ])

        with tab_checked:
            st.subheader("🟢 Checked / Used Companies in Local Database")
            st.caption("These companies are currently hidden from normal users.")
            
            checked_list = dedupe.confirmed_companies()
            if checked_list:
                df_checked = pd.DataFrame(checked_list)
                df_checked["Status"] = "Checked"

                col_chk_sel, col_chk_btn = st.columns([3, 1])
                with col_chk_sel:
                    comp_to_uncheck = st.selectbox("Select company to Uncheck (return to normal):", df_checked["name"].tolist(), key="admin_uncheck_select")
                with col_chk_btn:
                    st.write("")
                    st.write("")
                    if st.button("🔄 Uncheck Company", type="primary"):
                        dedupe.update_company_status(comp_to_uncheck, False)
                        st.success(f"Restored {comp_to_uncheck!r} to pending status.")
                        time.sleep(0.5)
                        st.rerun()

                df_checked = apply_lead_scoring(df_checked)
                cols_to_show = ["Lead Score", "name", "field", "location", "website", "linkedin", "emails", "phones", "source", "source_url", "checked_date", "found_at"]
                clean_cols = [c for c in cols_to_show if c in df_checked.columns]
                
                st.dataframe(
                    df_checked[clean_cols].style.apply(highlight_green, axis=1),
                    column_config={
                        "website": st.column_config.LinkColumn(),
                        "source_url": st.column_config.LinkColumn(),
                        "linkedin": st.column_config.LinkColumn(),
                        "checked_date": st.column_config.TextColumn("Date Used"),
                        "Lead Score": st.column_config.TextColumn("Score")
                    },
                    use_container_width=True
                )
            else:
                st.info("No companies are currently marked as Checked / Used in the Local Database.")

        with tab_dash:
            stats = dedupe.get_stats()
            st.subheader("📊 Performance & Activity Dashboard")
            dash_view = st.radio("Select Timeframe:", ["📅 Today (Per Day)", "🗓️ Last 7 Days (Per Week)", "🌐 Overall (All-Time)"], horizontal=True)
            
            if dash_view == "📅 Today (Per Day)":
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Searches Run Today", stats["searches"]["today"])
                c2.metric("Companies Added Today", stats["companies"]["today"])
                c3.metric("Leads Checked Today", stats["checked"]["today"])
                c4.metric("Active Users Today", stats["users"]["today"])
            elif dash_view == "🗓️ Last 7 Days (Per Week)":
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Searches (7 Days)", stats["searches"]["week"])
                c2.metric("Companies Added (7 Days)", stats["companies"]["week"])
                c3.metric("Leads Checked (7 Days)", stats["checked"]["week"])
                c4.metric("Active Users (7 Days)", stats["users"]["week"])
            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Searches", stats["searches"]["overall"])
                c2.metric("Total Companies in DB", stats["companies"]["overall"])
                c3.metric("Total Checked Leads", stats["checked"]["overall"])
                c4.metric("Total Unique Users", stats["users"]["overall"])

            st.divider()
            st.subheader("🕒 Recent Search Activity")
            if stats["recent_searches"]:
                st.dataframe(pd.DataFrame(stats["recent_searches"]), use_container_width=True)
            else:
                st.info("No search activity recorded yet.")

        with tab_del:
            st.caption("Delete records from the master Local Database only.")
            names = [c["name"] for c in dedupe.all_companies(include_confirmed=True)]
            if names:
                to_delete = st.selectbox("Select company to remove permanently:", names, key="admin_delete_select")
                if st.button("Delete Company", type="primary"):
                    dedupe.delete_company(to_delete)
                    st.success(f"Removed {to_delete!r} from Local Database.")
                    time.sleep(0.5)
                    st.rerun()

        with tab_danger:
            st.error("Wiping the database will clear all saved companies and reset search progress.")
            if st.button("🧨 Wipe Local Database", type="primary"):
                dedupe.clear_all_data()
                st.success("Database cleared.")
                time.sleep(1)
                st.rerun()
    else:
        st.session_state.is_admin = False