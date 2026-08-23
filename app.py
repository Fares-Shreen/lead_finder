import os
import time
import sys
import asyncio
import pandas as pd
import streamlit as st

# --- Force Streamlit Cloud to install the Chromium browser ---
os.system("playwright install chromium")

# --- Windows asyncio fix for Playwright (Kept for local testing) ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import dedupe
import config
from search_engine import process
import podio_live_checker

st.set_page_config(
    page_title="Company Lead Finder",
    page_icon="🔎",
    layout="wide" 
)

hide_streamlit_style = """
    <style>
    div[data-testid="stToolbar"] {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("🔎 Company Lead Finder")
st.caption(
    "Search company directories, cross-reference Podio Deals & Companies in real-time, "
    "and export actionable leads to Google Sheets."
)

if "serpapi_key" not in st.session_state:
    st.session_state.serpapi_key = config.SERPAPI_KEY or ""
if "podio_email" not in st.session_state:
    st.session_state.podio_email = os.environ.get("PODIO_EMAIL", "")
if "podio_password" not in st.session_state:
    st.session_state.podio_password = os.environ.get("PODIO_PASSWORD", "")

col_api, col_podio = st.columns(2)

with col_api:
    with st.expander("🔑 SerpApi Key", expanded=not st.session_state.serpapi_key):
        st.session_state.serpapi_key = st.text_input(
            "SerpApi API Key",
            value=st.session_state.serpapi_key,
            type="password",
            placeholder="Paste your SerpApi key"
        )

with col_podio:
    with st.expander(
        "🔷 Podio Credentials", 
        expanded=not (st.session_state.podio_email and st.session_state.podio_password)
    ):
        st.session_state.podio_email = st.text_input(
            "Podio Email",
            value=st.session_state.podio_email,
            placeholder="e.g. name@aiesec.net"
        )
        st.session_state.podio_password = st.text_input(
            "Podio Password",
            value=st.session_state.podio_password,
            type="password",
            placeholder="Enter Podio password"
        )

st.divider()

tab_search, tab_action_hub, tab_database, tab_admin = st.tabs([
    "🔎 Run Search", 
    "✅ Team Action Hub", 
    "📋 Local Database", 
    "🔐 Admin"
])

# -------------------------------------------------------------------------
# TAB 1: RUN SEARCH
# -------------------------------------------------------------------------
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
        customs = [x.strip() for x in custom_fields_input.split(",") if x.strip()]
        fields_to_search.extend(customs)
    fields_to_search = list(set(fields_to_search))

    with st.form("search_form"):
        location = st.text_input("Location", value="Alexandria, Egypt")
        sources = st.multiselect(
            "Search on",
            ["Google", "LinkedIn", "Yellow Pages", "Clutch"],
            default=["Google", "LinkedIn", "Yellow Pages", "Clutch"],
        )
        num_per_source = st.slider("Results per source (per field)", 5, 50, 15)
        restart = st.checkbox("Start this field + location over from the beginning", value=False)
        submitted = st.form_submit_button("🚀 Run Pipeline")

    status_box = st.empty()
    log_lines = []

    def progress_cb(msg):
        log_lines.append(msg)
        status_box.code("\n".join(log_lines[-15:]))

    if submitted:
        if not fields_to_search:
            st.warning("⚠️ Please select or type at least one field/industry to search for.")
        elif not sources:
            st.warning("⚠️ Pick at least one source to search on.")
        elif not st.session_state.podio_email or not st.session_state.podio_password:
            st.error("⚠️ Podio credentials are required to run the pipeline.")
        else:
            if restart:
                dedupe.init_db()
                for s in sources:
                    for f in fields_to_search:
                        dedupe.reset_search_offset(s, f, location)

            all_new_records = []
            total_skipped = 0

            for current_field in fields_to_search:
                with st.spinner(f"Running pipeline for {current_field} in {location}..."):
                    new_records, skipped_local, deal_accounts, comp_take, excel_master, ex1, ex2 = process(
                        current_field,
                        location,
                        sources,
                        num_per_source,
                        progress_cb,
                        api_key=st.session_state.serpapi_key or None,
                        podio_email=st.session_state.podio_email,
                        podio_password=st.session_state.podio_password
                    )
                    all_new_records.extend(new_records)
                    total_skipped += skipped_local

            st.success(f"Pipeline Complete! {len(all_new_records)} brand new leads generated. Data pushed to Google Sheets.")

            # --- ADD THIS LINE TO BACKUP THE MASTER DATABASE ---
            dedupe.sync_to_google_sheets()

            if all_new_records:
                st.subheader("✨ Brand New Leads (Enriched)")
            if all_new_records:
                st.subheader("✨ Brand New Leads (Enriched)")
                st.dataframe(
                    [
                        {
                            "Company": r["name"],
                            "Field": r.get("field", "N/A"),
                            "Website": r["website"],
                            "Email": ", ".join(r["emails"]),
                            "Phone": ", ".join(r["phones"]),
                            "Source Link": r.get("source_url", ""),
                        }
                        for r in all_new_records
                    ],
                    use_container_width=True,
                    column_config={"Source Link": st.column_config.LinkColumn()}
                )

# -------------------------------------------------------------------------
# TAB 2: TEAM ACTION HUB (GOOGLE SHEETS SYNC)
# -------------------------------------------------------------------------
with tab_action_hub:
    st.markdown("### Team Action Hub (Cloud Google Sheets)")
    st.caption("Changes are saved directly to the shared Google Sheet in real-time.")

    client = podio_live_checker._get_gspread_client()
    sheet_name = st.secrets["sheet"]["name"] if client and "sheet" in st.secrets else None

    if client and sheet_name:
        try:
            sh = client.open(sheet_name)
            
            def highlight_checked(row):
                if str(row.get("Status")) == "Checked":
                    return ["background-color: #d4edda; color: #155724"] * len(row)
                return [""] * len(row)

            # --- Excel 1: Deals ---
            st.subheader("🟡 Excel 1: Deal Accounts")
            try:
                ws1 = sh.worksheet("Excel_1_Deals")
                data1 = ws1.get_all_records()
                if data1:
                    df1 = pd.DataFrame(data1)
                    edited_df1 = st.data_editor(
                        df1.style.apply(highlight_checked, axis=1),
                        column_config={
                            "Deal Link": st.column_config.LinkColumn(),
                            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Checked"], required=True)
                        },
                        use_container_width=True,
                        key="editor_gsheets_1"
                    )
                    if not edited_df1.equals(df1):
                        ws1.clear()
                        ws1.update([edited_df1.columns.values.tolist()] + edited_df1.values.tolist())
                        st.rerun()
                else:
                    st.info("No deal accounts found in Google Sheets yet.")
            except Exception:
                st.info("Tab 'Excel_1_Deals' not found or empty.")

            st.divider()

            # --- Excel 2: Companies ---
            st.subheader("🟢 Excel 2: Companies to Take")
            try:
                ws2 = sh.worksheet("Excel_2_Companies")
                data2 = ws2.get_all_records()
                if data2:
                    df2 = pd.DataFrame(data2)
                    edited_df2 = st.data_editor(
                        df2.style.apply(highlight_checked, axis=1),
                        column_config={
                            "Company Link": st.column_config.LinkColumn(),
                            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Checked"], required=True)
                        },
                        use_container_width=True,
                        key="editor_gsheets_2"
                    )
                    if not edited_df2.equals(df2):
                        ws2.clear()
                        ws2.update([edited_df2.columns.values.tolist()] + edited_df2.values.tolist())
                        st.rerun()
                else:
                    st.info("No companies to take found in Google Sheets yet.")
            except Exception:
                st.info("Tab 'Excel_2_Companies' not found or empty.")

        except Exception as e:
            st.error(f"Failed to connect to Google Sheets tabs: {e}")
    else:
        st.warning("⚠️ Google Sheets credentials are not configured in Streamlit Secrets.")

# -------------------------------------------------------------------------
# TAB 3 & 4: DATABASE AND ADMIN
# -------------------------------------------------------------------------
with tab_database:
    dedupe.init_db()
    existing = dedupe.all_companies()
    st.markdown(f"### 📋 Saved Locally ({len(existing)})")
    if existing:
        st.dataframe(existing, use_container_width=True)

with tab_admin:
    st.markdown("### 🔐 Admin Panel")
    admin_pw = st.text_input("Admin password", type="password", key="admin_pw_input")

    if admin_pw and admin_pw == config.ADMIN_PASSWORD:
        st.success("Unlocked.")
        tab_remove, tab_dashboard, tab_danger = st.tabs(["🗑️ Remove", "📊 Dashboard", "⚠️ Danger Zone"])

        with tab_remove:
            all_now = dedupe.all_companies(include_confirmed=True)
            names = [c["name"] for c in all_now]
            if names:
                to_remove = st.selectbox("Company to remove", names, key="remove_select")
                if st.button("Delete permanently", type="primary"):
                    dedupe.delete_company(to_remove)
                    st.success(f"Removed {to_remove!r}.")
                    st.rerun()

        with tab_dashboard:
            stats = dedupe.get_stats()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total searches", stats["total_searches"])
            c2.metric("Distinct users", stats["distinct_users"])
            c3.metric("Companies in DB", stats["total_companies"])
            c4.metric("Confirmed companies", stats["confirmed_count"])

        with tab_danger:
            st.warning("🚨 **WARNING: This will permanently delete ALL data in the database.**")
            confirm_pw = st.text_input("Confirm Admin Password", type="password", key="confirm_wipe_pw")

            if st.button("🧨 Wipe Entire Database", type="primary"):
                if confirm_pw == config.ADMIN_PASSWORD:
                    dedupe.clear_all_data()
                    st.success("Database successfully wiped clean!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Incorrect password.")
    elif admin_pw:
        st.error("Wrong password.")