import os
import sys
import time
import asyncio
import datetime
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

with col_podio:
    with st.expander("🔷 Podio Credentials", expanded=not (st.session_state.podio_email and st.session_state.podio_password)):
        st.session_state.podio_email = st.text_input("Podio Email", value=st.session_state.podio_email)
        st.session_state.podio_password = st.text_input("Podio Password", value=st.session_state.podio_password, type="password")

st.divider()

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

def _execute_status_change(target_type, company_name, new_val, row_idx, sheet_tab):
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

tab_search, tab_action_hub, tab_database, tab_admin = st.tabs(["🔎 Run Search", "✅ Team Action Hub", "📋 Local Database", "🔐 Admin"])

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
        num_per_source = st.slider("Results per source (per field)", 5, 50, 15)
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

            all_new_records = []
            for current_field in fields_to_search:
                with st.spinner(f"Running pipeline for {current_field}..."):
                    new_records, _, _, _, _, _, _ = process(
                        current_field, location, sources, num_per_source, progress_cb,
                        api_key=st.session_state.serpapi_key or None,
                        podio_email=st.session_state.podio_email,
                        podio_password=st.session_state.podio_password
                    )
                    all_new_records.extend(new_records)
            
            dedupe.sync_to_google_sheets()
            st.success(f"Pipeline Complete! {len(all_new_records)} brand new leads generated. Synced to Google Sheets.")

# =========================================================================
# TAB 2: TEAM ACTION HUB (15-DAY RESET & SELECTION POP-UP)
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

                    # Quick toggle select input
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

                    st.dataframe(
                        df.style.apply(highlight_green, axis=1),
                        column_config={
                            "Deal Link": st.column_config.LinkColumn(),
                            "Company Link": st.column_config.LinkColumn(),
                            "Checked_Date": st.column_config.TextColumn("Date Used")
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
# TAB 3: LOCAL DATABASE (SELECTION POP-UP & GREEN STATUS)
# =========================================================================
with tab_database:
    dedupe.init_db()
    existing = dedupe.all_companies(include_confirmed=True)
    st.markdown(f"### 📋 Local Master Database ({len(existing)} companies)")
    
    if existing:
        df_local = pd.DataFrame(existing)
        df_local["Status"] = df_local["confirmed"].apply(lambda x: "Checked" if x == 1 else "Pending")

        # Action Selector
        col_db_sel, col_db_btn = st.columns([3, 1])
        with col_db_sel:
            chosen_comp = st.selectbox("Select company to update status:", df_local["name"].tolist(), key="local_db_comp_select")
        with col_db_btn:
            st.write("")
            st.write("")
            is_checked = df_local.loc[df_local["name"] == chosen_comp, "confirmed"].values[0] == 1
            btn_txt = "Uncheck" if is_checked else "✅ Check & Lock"
            if st.button(btn_txt, key="btn_local_db_confirm"):
                confirm_status_dialog("local", chosen_comp, is_checked)

        display_cols = ["name", "field", "location", "website", "linkedin", "emails", "phones", "source", "source_url", "Status", "checked_date", "found_at"]
        clean_display_cols = [c for c in display_cols if c in df_local.columns]
        
        st.dataframe(
            df_local[clean_display_cols].style.apply(highlight_green, axis=1),
            column_config={
                "website": st.column_config.LinkColumn(),
                "source_url": st.column_config.LinkColumn(),
                "linkedin": st.column_config.LinkColumn(),
                "checked_date": st.column_config.TextColumn("Date Checked")
            },
            use_container_width=True
        )

# =========================================================================
# TAB 4: ADMIN CONTROLS
# =========================================================================
with tab_admin:
    st.markdown("### 🔐 Admin Panel")
    admin_pw = st.text_input("Admin Password", type="password", key="admin_panel_pw")
    
    if admin_pw and admin_pw == config.ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("Admin mode active.")
        
        tab_del, tab_dash, tab_danger = st.tabs(["🗑️ Delete from Local DB", "📊 Metrics", "⚠️ Danger Zone"])

        with tab_del:
            st.caption("Delete records from the master Local Database only (leaves Excel 1 & 2 untouched).")
            names = [c["name"] for c in dedupe.all_companies(include_confirmed=True)]
            if names:
                to_delete = st.selectbox("Select company to remove permanently:", names, key="admin_delete_select")
                if st.button("Delete Company", type="primary"):
                    dedupe.delete_company(to_delete)
                    st.success(f"Removed {to_delete!r} from Local Database.")
                    time.sleep(0.5)
                    st.rerun()

        with tab_dash:
            stats = dedupe.get_stats()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Searches", stats["total_searches"])
            c2.metric("Distinct Users", stats["distinct_users"])
            c3.metric("Total in Database", stats["total_companies"])
            c4.metric("Checked Leads", stats["confirmed_count"])

        with tab_danger:
            st.error("Wiping the database will clear all saved companies and reset search progress.")
            if st.button("🧨 Wipe Local Database", type="primary"):
                dedupe.clear_all_data()
                st.success("Database cleared.")
                time.sleep(1)
                st.rerun()
    else:
        st.session_state.is_admin = False