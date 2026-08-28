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

if "serpapi_key" not in st.session_state: st.session_state.serpapi_key = config.SERPAPI_KEY or ""
if "podio_email" not in st.session_state: st.session_state.podio_email = os.environ.get("PODIO_EMAIL", "")
if "podio_password" not in st.session_state: st.session_state.podio_password = os.environ.get("PODIO_PASSWORD", "")
if "is_admin" not in st.session_state: st.session_state.is_admin = False

col_api, col_podio = st.columns(2)
with col_api:
    with st.expander("🔑 SerpApi Key"):
        st.session_state.serpapi_key = st.text_input("SerpApi API Key", value=st.session_state.serpapi_key, type="password")
with col_podio:
    with st.expander("🔷 Podio Credentials"):
        st.session_state.podio_email = st.text_input("Podio Email", value=st.session_state.podio_email)
        st.session_state.podio_password = st.text_input("Podio Password", value=st.session_state.podio_password, type="password")
st.divider()

# --- PREDICTIVE SCORING HELPER ---
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
    if "Lead Score" not in df_copy.columns: df_copy.insert(0, "Lead Score", scores)
    else: df_copy["Lead Score"] = scores
    return df_copy

def highlight_green(row):
    status_val = str(row.get("Status", ""))
    if status_val == "Checked" or str(row.get("confirmed", "")) in ["1", "True", "true"]:
        return ["background-color: #d4edda; color: #155724; font-weight: 500;"] * len(row)
    return [""] * len(row)

tab_search, tab_manual, tab_upload, tab_database, tab_action = st.tabs([
    "🔎 Run Search Pipeline", 
    "🕵️ Manual Deep Check", 
    "📁 Upload Custom List",
    "📋 Local Master DB", 
    "✅ Team Action Hub"
])

# =========================================================================
# TAB 1: RUN SEARCH
# =========================================================================
with tab_search:
    st.caption("Blazing fast search. Automatically routes clean leads to Master DB and suspects to Manual Check.")
    col1, col2 = st.columns(2)
    with col1:
        field_choices = st.multiselect("Fields", ["Software", "IT", "Sales", "Digital Marketing"], default=["Software"])
    with col2:
        custom_fields = st.text_input("Custom fields (comma separated)")

    fields_to_search = list(field_choices)
    if custom_fields.strip(): fields_to_search.extend([x.strip() for x in custom_fields.split(",") if x.strip()])
    
    with st.form("search_form"):
        location = st.text_input("Location", value="Alexandria, Egypt")
        sources = st.multiselect("Search on", ["Google Maps", "LinkedIn", "Wuzzuf", "Indeed", "Yellow Pages"], default=["Google Maps", "LinkedIn"])
        num_per_source = st.slider("Results per source", 5, 50, 15)
        submitted = st.form_submit_button("🚀 Run Pipeline")

    status_box = st.empty()
    log_lines = []
    def progress_cb(msg):
        log_lines.append(msg)
        status_box.code("\n".join(log_lines[-15:]))

    if submitted:
        if not st.session_state.podio_email:
            st.error("⚠️ Podio credentials required.")
        else:
            total_clean, total_suspects = 0, 0
            for field in set(fields_to_search):
                with st.spinner(f"Running for {field}..."):
                    clean, suspects = process(field, location, sources, num_per_source, progress_cb, st.session_state.serpapi_key)
                    total_clean += len(clean)
                    total_suspects += len(suspects)
            st.success(f"Pipeline Complete! ✅ {total_clean} saved directly to DB. 🕵️ {total_suspects} routed to Manual Check.")

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
                        # Convert to the dict format expected by analyze_leads_live
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
                        
                        # Add cleared ones to the local DB
                        for lead in cleared:
                            dedupe.add_company(lead)
                        dedupe.sync_to_google_sheets()
                        
                    st.success(f"Upload Processed! ✅ {len(ex1)} routed to Deals (Excel 1), {len(ex2)} routed to Companies (Excel 2).")
                    if cleared:
                        st.info(f"{len(cleared)} companies were completely new and have been saved to your Local Database.")
        except Exception as e:
            st.error(f"Error processing file: {e}")

# =========================================================================
# TAB 4: LOCAL DATABASE
# =========================================================================
with tab_database:
    dedupe.init_db()
    existing = dedupe.all_companies()
    st.markdown(f"### 📋 Clean Local Master Database ({len(existing)} companies)")
    if existing:
        df_local = pd.DataFrame(existing)
        df_local = apply_lead_scoring(df_local)
        st.dataframe(df_local, use_container_width=True)

# =========================================================================
# TAB 5: TEAM ACTION HUB
# =========================================================================
with tab_action:
    st.markdown("### Team Action Hub (Google Sheets)")
    st.info("Check Excel 1 (Deals) and Excel 2 (Companies) on Google Sheets to claim routed accounts.")