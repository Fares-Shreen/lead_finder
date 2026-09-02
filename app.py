import base64
import os
import sys
import time
import asyncio
import datetime
import requests
import pandas as pd
import streamlit as st
from streamlit import components

os.system("playwright install chromium")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import dedupe
import config
from search_engine import process
import podio_live_checker
import account_manager  # Make sure account_manager.py is in the same directory

# =========================================================================
# PAGE CONFIG & AIESEC BRANDING CSS
# =========================================================================
st.set_page_config(page_title="AIESEC Lead Engine", page_icon="👤", layout="wide")

AIESEC_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/AIESEC_Logo.svg/512px-AIESEC_Logo.svg.png"
AIESEC_BLUE = "#037ef3"

aiesec_style = f"""
    <style>
    /* Hide Streamlit components */
    div[data-testid="stToolbar"] {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}

    /* AIESEC Branding Overrides */
    .stButton>button[kind="primary"] {{
        background-color: {AIESEC_BLUE}; 
        color: white;
        border: none;
    }}
    .stButton>button[kind="primary"]:hover {{
        background-color: #0266c8;
    }}
    h1, h2, h3 {{
        color: {AIESEC_BLUE} !important;
    }}
    </style>
"""
st.markdown(aiesec_style, unsafe_allow_html=True)

# =========================================================================
# SESSION & AUTHENTICATION STATE
# =========================================================================
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "user_function" not in st.session_state: st.session_state.user_function = ""
if "is_admin" not in st.session_state: st.session_state.is_admin = False

if "serpapi_key" not in st.session_state: st.session_state.serpapi_key = config.SERPAPI_KEY or ""
if "podio_email" not in st.session_state: st.session_state.podio_email = os.environ.get("PODIO_EMAIL", "")
if "podio_password" not in st.session_state: st.session_state.podio_password = os.environ.get("PODIO_PASSWORD", "")
if "auto_run_active" not in st.session_state: st.session_state.auto_run_active = False
if "auto_run_cycle" not in st.session_state: st.session_state.auto_run_cycle = 0

# -------------------------------------------------------------------------
# LOGIN GATE (WITH AIESEC LOGO)
# -------------------------------------------------------------------------
if not st.session_state.authenticated:
    _, center_col, _ = st.columns([1, 1.2, 1])
    with center_col:
        st.markdown(f"<div style='text-align: center;'><img src='{AIESEC_LOGO_URL}' width='180'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; margin-top: 10px;'>Sign In to Lead Engine</h2>", unsafe_allow_html=True)
        st.caption("<div style='text-align: center;'>AIESEC CRM & B2B Pipeline Access</div>", unsafe_allow_html=True)
        st.write("")
        
        with st.form("login_form"):
            in_email = st.text_input("AIESEC Email Address")
            in_password = st.text_input("Password", type="password")
            submit_btn = st.form_submit_button("Sign In", use_container_width=True, type="primary")

            if submit_btn:
                user_info = account_manager.authenticate(in_email, in_password)
                if user_info:
                    st.session_state.authenticated = True
                    st.session_state.user_email = user_info["Email"]
                    st.session_state.user_function = user_info["Function"]
                    st.session_state.is_admin = (user_info["Function"].upper() == "ADMIN")
                    st.success(f"Welcome back, {user_info['Email']}!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
    st.stop()  # Halt rendering until signed in

# -------------------------------------------------------------------------
# LOGGED-IN SIDEBAR
# -------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"<div style='text-align: center; margin-bottom: 20px;'><img src='{AIESEC_LOGO_URL}' width='140'></div>", unsafe_allow_html=True)
    st.markdown(f"**Account:** `{st.session_state.user_email}`")
    
    # Brand matching badges
    badge_color = AIESEC_BLUE if st.session_state.is_admin else "#00c16e"
    st.markdown(f"**Function:** <span style='background-color:{badge_color}; color:white; padding:3px 8px; border-radius:4px; font-weight:bold;'>{st.session_state.user_function}</span>", unsafe_allow_html=True)
    
    st.divider()
    if st.button("🚪 Log Out", use_container_width=True):
        for key in ["authenticated", "user_email", "user_function", "is_admin"]:
            st.session_state[key] = False if type(st.session_state[key]) == bool else ""
        st.rerun()

st.title("AIESEC B2B Lead Engine")
st.caption("Directory scraper, live Podio cross-referencer, and real-time Action Hub.")

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

    if new_val == True: 
        try:
            with dedupe._conn() as c:
                row = c.execute("SELECT * FROM companies WHERE name_normalized = ?", (dedupe._normalize(company_name),)).fetchone()
            if row:
                webhook_payload = {
                    "company_name": row[1], "field": row[2], "location": row[3],
                    "website": row[4], "linkedin": row[5], "emails": row[6], "phones": row[7]
                }
                webhook_url = "https://hooks.zapier.com/hooks/catch/your_id_here/"
                try: requests.post(webhook_url, json=webhook_payload, timeout=2)
                except requests.exceptions.RequestException: pass
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

# Dynamic Tab Loading based on permissions
tab_titles = [
    "🔎 Run Search", 
    "🕵️ Manual Deep Check", 
    "📁 Upload Custom List", 
    "✅ Team Action Hub", 
    "📋 Local Database"
]
if st.session_state.is_admin:
    tab_titles.append("🔐 Admin & Accounts Panel")

tabs = st.tabs(tab_titles)
tab_search, tab_manual, tab_upload, tab_action_hub, tab_database = tabs[:5]
if st.session_state.is_admin:
    tab_admin = tabs[5]

# =========================================================================
# TAB 1: RUN SEARCH
# =========================================================================
with tab_search:
    st.markdown("### 🔎 Market Research & Discovery")
    
    # --- FUNCTION TAGGING ---
    if st.session_state.is_admin:
        assigned_function = st.selectbox("Assign Discovered Leads To:", ["IGT", "IGV", "B2B"])
    else:
        assigned_function = st.session_state.user_function
        st.info(f"Leads discovered in this search will be automatically tagged for **{assigned_function}**.")
    
    col1, col2 = st.columns(2)
    with col1:
        field_choices = st.multiselect(
            "Select Fields",
            ["Software", "IT", "Digital Marketing", "Sales", "Video Editing", "Accounting", "English Center", "French Center"],
            default=["Software"]
        )
    with col2:
        custom_fields_input = st.text_input("And/or enter custom fields", placeholder="e.g. Real Estate")

    fields_to_search = list(field_choices)
    if custom_fields_input.strip():
        fields_to_search.extend([x.strip() for x in custom_fields_input.split(",") if x.strip()])
    fields_to_search = list(set(fields_to_search))

    location = st.text_input("Location", value="Alexandria, Egypt")
    sources = st.multiselect(
        "Search on",
        ["Google Maps", "LinkedIn", "Yellow Pages", "Wuzzuf", "Indeed"],
        default=["Google Maps", "LinkedIn", "Wuzzuf", "Indeed"]
    )
    num_per_source = st.slider("Results per source (per field)", 10, 100, 100, step=10)
    restart = st.checkbox("Start this field + location over from the beginning", value=False)

    col_btn_once, col_btn_auto = st.columns(2)
    
    with col_btn_once:
        run_once_clicked = st.button("🚀 Run Once", use_container_width=True, disabled=st.session_state.auto_run_active)
        
    with col_btn_auto:
        if not st.session_state.auto_run_active:
            if st.button("🔄 Start Auto-Run Pipeline", type="primary", use_container_width=True):
                st.session_state.auto_run_active = True
                st.session_state.auto_run_cycle = 0
                st.rerun()
        else:
            if st.button("🛑 Stop Auto-Run Pipeline", type="secondary", use_container_width=True):
                st.session_state.auto_run_active = False
                st.rerun()

    status_box = st.empty()
    log_lines = []
    def progress_cb(msg):
        log_lines.append(msg)
        status_box.code("\n".join(log_lines[-15:]))

    should_run = run_once_clicked or st.session_state.auto_run_active

    if should_run:
        if not fields_to_search or not sources:
            st.warning("⚠️ Please select fields and sources.")
            st.session_state.auto_run_active = False
        elif not st.session_state.podio_email or not st.session_state.podio_password:
            st.error("⚠️ Podio credentials are required.")
            st.session_state.auto_run_active = False
        else:
            if restart and not st.session_state.auto_run_active:
                dedupe.init_db()
                for s in sources:
                    for f in fields_to_search:
                        dedupe.reset_search_offset(s, f, location)

            st.session_state.auto_run_cycle += 1
            if st.session_state.auto_run_active:
                st.info(f"🔄 **Auto-Run Active — Cycle #{st.session_state.auto_run_cycle}** (Offsets automatically advancing)")

            total_clean, total_suspects = 0, 0
            for current_field in fields_to_search:
                with st.spinner(f"Running pipeline for {current_field}..."):
                    clean_leads, suspect_leads = process(
                        current_field, location, sources, num_per_source, progress_cb,
                        api_key=st.session_state.serpapi_key or None,
                        podio_email=st.session_state.podio_email,
                        podio_password=st.session_state.podio_password,
                        function_type=assigned_function
                    )
                    total_clean += len(clean_leads)
                    total_suspects += len(suspect_leads)
            
            st.success(f"Cycle Complete! ✅ {total_clean} new leads saved to DB. 🕵️ {total_suspects} suspects routed to Manual Check.")

            if st.session_state.auto_run_active:
                if total_clean == 0 and total_suspects == 0:
                    st.warning("🏁 No more new results found across all sources. Auto-run stopped.")
                    st.session_state.auto_run_active = False
                else:
                    st.toast(f"Cycle #{st.session_state.auto_run_cycle} complete. Next round starting in 3 seconds...", icon="⏳")
                    time.sleep(3)
                    st.rerun()

# =========================================================================
# TAB 2: MANUAL DEEP CHECK (PLAYWRIGHT)
# =========================================================================
with tab_manual:
    st.markdown("### 🕵️ Need Podio Check Queue")
    st.caption("These fully-enriched companies triggered a flag on the fast API. Run Playwright to verify them.")
    
    if st.session_state.is_admin:
        manual_assigned_function = st.selectbox("Assign Verified Suspects To:", ["IGT", "IGV", "B2B"], key="manual_func")
    else:
        manual_assigned_function = st.session_state.user_function

    suspects = dedupe.get_suspects_from_sheet()
    
    if not suspects:
        st.success("🎉 No suspects in the queue! You are all caught up.")
    else:
        st.info(f"There are **{len(suspects)}** companies waiting for deep Playwright verification.")
        df_sus = pd.DataFrame(suspects)
        st.dataframe(df_sus, use_container_width=True)
        
        batch_size = st.slider("Select batch size to process:", 10, 200, 100, step=10)
        
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
                lead["function_type"] = manual_assigned_function
                dedupe.add_company(lead)
            dedupe.sync_to_google_sheets()
            
            dedupe.remove_suspects_from_sheet(names_to_remove)
            st.success(f"Processed! {len(excel1)} to Deals, {len(excel2)} to Companies, {len(cleared)} safely moved to Local DB.")
            time.sleep(2)
            st.rerun()

# =========================================================================
# TAB 3: UPLOAD CUSTOM LIST (UPDATED FOR AUTO-RUN)
# =========================================================================
with tab_upload:
    st.markdown("### 📁 Upload Custom Excel / CSV")
    
    if st.session_state.is_admin:
        upload_assigned_function = st.selectbox("Assign Uploaded Leads To:", ["IGT", "IGV", "B2B"], key="upload_func")
    else:
        upload_assigned_function = st.session_state.user_function
        
    if "auto_run" not in st.session_state:
        st.session_state.auto_run = False
        
    uploaded_file = st.file_uploader("Upload File (.xlsx, .csv)", type=["xlsx", "xls", "csv"])
    
    if uploaded_file:
        try:
            file_id = f"{uploaded_file.name}_{uploaded_file.size}"
            if st.session_state.get("current_upload_id") != file_id:
                st.session_state.current_upload_id = file_id
                if uploaded_file.name.endswith(".csv"):
                    df_up = pd.read_csv(uploaded_file)
                else:
                    df_up = pd.read_excel(uploaded_file)
                
                if "Podio Checked" not in df_up.columns:
                    df_up.insert(0, "Podio Checked", 0)
                st.session_state.upload_df = df_up
                st.session_state.trigger_download = False
                st.session_state.auto_run = False

            df_upload = st.session_state.upload_df
            pending_count = len(df_upload[df_upload["Podio Checked"] == 0])
            
            st.info(f"**{pending_count}** companies remaining to be checked out of {len(df_upload)} total.")
            
            col_options = df_upload.columns.tolist()
            default_col = col_options.index("Account Name") if "Account Name" in col_options else 0
            name_col = st.selectbox("Which column contains the Company Name?", col_options, index=default_col)
            
            col_mode, col_size = st.columns(2)
            with col_mode:
                process_mode = st.radio("Processing Mode:", ["Batch Processing", "Process All Remaining"])
            with col_size:
                if process_mode == "Batch Processing":
                    batch_size = st.slider("Batch Size", 5, 100, 25)
                else:
                    batch_size = pending_count

            if pending_count > 0:
                st.divider()
                
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("▶️ Start Auto-Run Pipeline", type="primary", use_container_width=True):
                        st.session_state.auto_run = True
                        st.rerun()
                with btn_col2:
                    if st.button("🛑 Stop Auto-Run", use_container_width=True):
                        st.session_state.auto_run = False
                        st.rerun()
                with btn_col3:
                    run_single = st.button(f"🤖 Run 1 Batch ({batch_size})", use_container_width=True)

                if st.session_state.auto_run:
                    st.warning("⚠️ Auto-Run is ACTIVE. The pipeline is running continuously...")

                if st.session_state.auto_run or run_single:
                    pending_indices = df_upload[df_upload["Podio Checked"] == 0].head(batch_size).index
                    
                    custom_candidates = []
                    for idx in pending_indices:
                        comp_name = str(df_upload.loc[idx, name_col]).strip()
                        if comp_name and comp_name.lower() != "nan":
                            custom_candidates.append({
                                "name": comp_name,
                                "field": "Custom Upload",
                                "location": "Custom Upload",
                                "source": "Manual Upload",
                                "_upload_idx": idx 
                            })
                            
                    if not custom_candidates:
                        st.warning("No valid company names found in the selected batch.")
                        st.session_state.auto_run = False 
                    else:
                        upload_status = st.empty()
                        upload_logs = []
                        def prog_upload(msg):
                            upload_logs.append(msg)
                            upload_status.code("\n".join(upload_logs[-10:]))
                            
                        with st.spinner(f"Processing {len(custom_candidates)} uploaded companies..."):
                            ex1, ex2, cleared = podio_live_checker.analyze_leads_live(
                                custom_candidates, st.session_state.podio_email, st.session_state.podio_password, prog_upload
                            )
                            
                            for cand in custom_candidates:
                                st.session_state.upload_df.loc[cand["_upload_idx"], "Podio Checked"] = 1
                            
                            for lead in cleared:
                                lead.pop("_upload_idx", None)
                                lead["function_type"] = upload_assigned_function 
                                dedupe.add_company(lead)
                            dedupe.sync_to_google_sheets()
                            
                        st.success(f"Batch Processed! ✅ {len(ex1)} to Deals, {len(ex2)} to Companies.")
                        
                        if st.session_state.auto_run:
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.session_state.trigger_download = True
                            time.sleep(1.5)
                            st.rerun()
            else:
                st.session_state.auto_run = False
                st.success("🎉 All companies in this file have been checked! You can download the finalized file below.")
            
            st.divider()
            
            csv_data = st.session_state.upload_df.to_csv(index=False).encode('utf-8')
            
            if st.session_state.get("trigger_download") or (pending_count == 0 and "downloaded" not in st.session_state):
                st.session_state.trigger_download = False 
                st.session_state.downloaded = True 
                
                b64 = base64.b64encode(csv_data).decode()
                filename = f"processed_{uploaded_file.name}.csv"
                
                js_code = f"""
                    <a id="auto-download" href="data:file/csv;base64,{b64}" download="{filename}"></a>
                    <script>
                        document.getElementById('auto-download').click();
                    </script>
                """
                components.html(js_code, height=0)
            
            st.download_button(
                label="📥 Download Updated CSV (with Podio Checked Status)",
                data=csv_data,
                file_name=f"processed_{uploaded_file.name}.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error processing file: {e}")
            st.session_state.auto_run = False 

# =========================================================================
# TAB 4: TEAM ACTION Hub (ROW-SELECTION CHECKBOXES)
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

                    df_display = apply_lead_scoring(df)
                    
                    df_display.reset_index(drop=True, inplace=True)
                    df_display.insert(0, "No.", df_display.index + 1)

                    event = st.dataframe(
                        df_display.style.apply(highlight_green, axis=1),
                        column_config={
                            "No.": st.column_config.NumberColumn("No.", width="small"),
                            "Deal Link": st.column_config.LinkColumn(),
                            "Company Link": st.column_config.LinkColumn(),
                            "Checked_Date": st.column_config.TextColumn("Date Used"),
                            "Lead Score": st.column_config.TextColumn("Score")
                        },
                        use_container_width=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key=f"hub_table_{ws_name}"
                    )

                    selected_rows = event.selection.rows
                    if selected_rows:
                        target_row_idx = selected_rows[0]
                        comp_col = "Company Name" if "Company Name" in df.columns else df.columns[0]
                        selected_target = str(df.at[target_row_idx, comp_col])
                        current_state = df.at[target_row_idx, "Status"] == "Checked"
                        
                        btn_label = f"Uncheck '{selected_target}'" if current_state else f"✅ Check & Use '{selected_target}'"
                        if st.button(btn_label, type="primary", key=f"btn_hub_select_{ws_name}"):
                            confirm_status_dialog("sheet", selected_target, current_state, target_row_idx, ws_name)

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
# TAB 5: LOCAL DATABASE (ROLE-ISOLATED)
# =========================================================================
with tab_database:
    dedupe.init_db()
    existing = dedupe.all_companies(include_confirmed=st.session_state.is_admin)
    
    if existing:
        df_local = pd.DataFrame(existing)
        
        if "function_type" not in df_local.columns:
            df_local["function_type"] = "IGT" # Fallback if missing
            
        if "source" in df_local.columns:
            df_local = df_local[df_local["source"] != "Manual Upload"]
        elif "Source" in df_local.columns:
            df_local = df_local[df_local["Source"] != "Manual Upload"]

        # ROLE-BASED ISOLATION: Hide companies belonging to other functions
        if not st.session_state.is_admin:
            df_local = df_local[df_local["function_type"] == st.session_state.user_function]

        display_count = len(df_local)

        if st.session_state.is_admin:
            st.markdown(f"### 📋 Local Master Database - ADMIN VIEW ({display_count} companies)")
            st.caption("Admin mode: Viewing ALL companies including Checked ones.")
        else:
            st.markdown(f"### 📋 Local Master Database ({display_count} pending companies)")
            st.caption(f"Showing only leads designated for {st.session_state.user_function}.")
        
        if df_local.empty:
            st.warning("⚠️ No available companies match your current view/permissions.")
        else:
            df_local.reset_index(drop=True, inplace=True)
            df_local.insert(0, "No.", df_local.index + 1)
            
            df_local["Status"] = df_local["confirmed"].apply(lambda x: "Checked" if x == 1 else "Pending")
            df_local = apply_lead_scoring(df_local)

            display_cols = ["No.", "Lead Score", "function_type", "name", "field", "location", "website", "linkedin", "emails", "phones", "source", "source_url", "Status", "checked_date", "found_at"]
            clean_display_cols = [c for c in display_cols if c in df_local.columns]
            df_display = df_local[clean_display_cols]

            selection_event = st.dataframe(
                df_display.style.apply(highlight_green, axis=1),
                column_config={
                    "No.": st.column_config.NumberColumn("No.", width="small"),
                    "function_type": st.column_config.TextColumn("Function"),
                    "website": st.column_config.LinkColumn(),
                    "source_url": st.column_config.LinkColumn(),
                    "linkedin": st.column_config.LinkColumn(),
                    "checked_date": st.column_config.TextColumn("Date Checked"),
                    "Lead Score": st.column_config.TextColumn("Score")
                },
                use_container_width=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="local_db_table_select"
            )

            selected_row_indices = selection_event.selection.rows
            
            if selected_row_indices:
                selected_companies = df_display.iloc[selected_row_indices]["name"].tolist()
                
                col_act1, col_act2 = st.columns([2, 1])
                with col_act1:
                    st.info(f"Selected **{len(selected_companies)}** company(s): {', '.join(selected_companies[:3])}{'...' if len(selected_companies) > 3 else ''}")
                with col_act2:
                    if st.button(f"✅ Mark Selected as Checked ({len(selected_companies)})", type="primary", use_container_width=True):
                        for comp in selected_companies:
                            dedupe.update_company_status(comp, True)
                        st.success(f"Updated {len(selected_companies)} companies to Checked!")
                        time.sleep(0.8)
                        st.rerun()
    else:
        st.markdown("### 📋 Local Master Database (0 pending companies)")
        st.info("No available companies to display.")

# =========================================================================
# TAB 6: ADMIN CONTROLS (VISIBLE ONLY TO ADMIN)
# =========================================================================
if st.session_state.is_admin:
    with tab_admin:
        st.markdown("### 🔐 AIESEC Administrative Control Center")
        
        tab_users, tab_dash, tab_del, tab_danger = st.tabs([
            "👥 Account Management", 
            "📊 Function-Wise Dashboard", 
            "🗑️ Delete from Local DB", 
            "⚠️ Danger Zone"
        ])

        # --- SUB-TAB 1: ACCOUNT MANAGEMENT ---
        with tab_users:
            st.subheader("Manage User Accounts")
            
            with st.expander("➕ Register New Account", expanded=False):
                with st.form("add_user_form"):
                    new_email = st.text_input("New Member Email")
                    new_pass = st.text_input("Temporary Password", type="password")
                    new_func = st.selectbox("Role / Function", ["IGT", "IGV", "B2B", "Admin"])
                    btn_create = st.form_submit_button("Create Account", type="primary")

                    if btn_create:
                        if new_email and new_pass:
                            success = account_manager.add_account(new_email, new_pass, new_func)
                            if success:
                                st.success(f"Account for {new_email} ({new_func}) created successfully!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("An account with that email already exists.")
                        else:
                            st.warning("Please fill in both email and password fields.")

            st.divider()
            st.subheader("Active Accounts List")
            accounts_df = account_manager.load_accounts()
            if not accounts_df.empty:
                display_acc_df = accounts_df.copy()
                display_acc_df["Password"] = "••••••••"  # Mask passwords in the UI
                st.dataframe(display_acc_df, use_container_width=True)

                del_email = st.selectbox("Select an account to remove:", accounts_df["Email"].tolist())
                if st.button("🗑️ Delete Account", type="secondary"):
                    if del_email == st.session_state.user_email:
                        st.error("You cannot delete your own active Admin account.")
                    else:
                        account_manager.delete_account(del_email)
                        st.success(f"Removed account {del_email}.")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.info("No accounts currently registered.")

        # --- SUB-TAB 2: FUNCTION-WISE DASHBOARD ---
        with tab_dash:
            st.subheader("📊 Performance & Activity Dashboard")
            
            chosen_func = st.radio("Filter Statistics by Functional Track:", ["All", "IGT", "IGV", "B2B"], horizontal=True)
            
            all_records = dedupe.all_companies(include_confirmed=True)
            if all_records:
                df_all = pd.DataFrame(all_records)
                if "function_type" not in df_all.columns:
                    df_all["function_type"] = "Unassigned"

                # Filter according to choice
                if chosen_func != "All":
                    df_func = df_all[df_all["function_type"] == chosen_func]
                else:
                    df_func = df_all

                total_func_companies = len(df_func)
                checked_func_companies = len(df_func[df_func.get("confirmed", 0) == 1])
                pending_func_companies = total_func_companies - checked_func_companies

                c1, c2, c3 = st.columns(3)
                c1.metric(f"Total Leads ({chosen_func})", total_func_companies)
                c2.metric("Checked Leads", checked_func_companies)
                c3.metric("Pending Leads", pending_func_companies)

                st.divider()
                st.subheader(f"Raw Companies Data in {chosen_func}")
                df_func_display = df_func.copy().reset_index(drop=True)
                df_func_display.insert(0, "No.", df_func_display.index + 1)
                st.dataframe(df_func_display, use_container_width=True)
            else:
                st.info("No company records found in the database yet.")

        # --- SUB-TAB 3: DELETE FROM DB ---
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

        # --- SUB-TAB 4: DANGER ZONE ---
        with tab_danger:
            st.error("Wiping the database will clear all saved companies and reset search progress.")
            if st.button("🧨 Wipe Local Database", type="primary"):
                dedupe.clear_all_data()
                st.success("Database cleared.")
                time.sleep(1)
                st.rerun()