import os
import re
from datetime import datetime
import pandas as pd

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "podio_exports")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def _normalize(name):
    if not name or pd.isna(name):
        return ""
    return re.sub(r"[^\w\s]", "", str(name)).strip().lower()


def _parse_days_ago(date_val):
    if not date_val or pd.isna(date_val):
        return 9999
    try:
        dt = pd.to_datetime(date_val)
        return (datetime.now() - dt).days
    except Exception:
        return 9999


def load_podio_data():
    deals_path = os.path.join(DOWNLOAD_DIR, "deals_export.xlsx")
    comp_path = os.path.join(DOWNLOAD_DIR, "companies_export.xlsx")

    deals_df = pd.read_excel(deals_path) if os.path.exists(deals_path) else pd.DataFrame()
    comp_df = pd.read_excel(comp_path) if os.path.exists(comp_path) else pd.DataFrame()

    return deals_df, comp_df


def analyze_leads_detailed(candidate_leads):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    deals_df, comp_df = load_podio_data()

    def get_col(df, options):
        for col in df.columns:
            if any(opt.lower() in str(col).lower() for opt in options):
                return col
        return None

    deal_company_col = get_col(deals_df, ["company reference", "company", "title"])
    deal_committee_col = get_col(deals_df, ["local committee", "committee", "lc"])
    deal_stage_col = get_col(deals_df, ["deal stage", "stage", "status"])
    deal_activity_col = get_col(deals_df, ["last comment", "last activity", "updated on", "created on"])
    deal_link_col = get_col(deals_df, ["link", "item url", "url"])

    comp_name_col = get_col(comp_df, ["company name", "name", "title"])
    comp_committee_col = get_col(comp_df, ["local committee", "committee", "lc"])
    comp_activity_col = get_col(comp_df, ["first comment", "first activity", "created on", "date"])
    comp_link_col = get_col(comp_df, ["link", "item url", "url"])

    excel_1_deal_accounts = []
    excel_2_companies_to_take = []
    new_leads_to_enrich = []

    for lead in candidate_leads:
        name = lead["name"]
        norm_name = _normalize(name)
        if not norm_name:
            continue

        # 1. Check Deals App
        deal_match = None
        if not deals_df.empty and deal_company_col:
            matches = deals_df[deals_df[deal_company_col].apply(_normalize) == norm_name]
            if not matches.empty:
                deal_match = matches.iloc[0]

        if deal_match is not None:
            committee = str(deal_match.get(deal_committee_col, "")).strip()
            stage = str(deal_match.get(deal_stage_col, "")).strip().lower()
            activity_date = deal_match.get(deal_activity_col)
            days_ago = _parse_days_ago(activity_date)
            deal_link = deal_match.get(deal_link_col, "https://podio.com")

            if "raised" in stage or "signed" in stage:
                continue

            is_alex = "alexandria" in committee.lower()

            if is_alex or days_ago > 15:
                excel_1_deal_accounts.append({
                    "Company Name": name,
                    "Deal Link": deal_link,
                    "Local Committee": committee,
                    "Deal Stage": stage.title(),
                    "Last Activity": str(activity_date),
                    "Days Inactive": days_ago,
                    "Action": "Apply to get this account",
                })
            continue

        # 2. Check Companies App
        comp_match = None
        if not comp_df.empty and comp_name_col:
            matches = comp_df[comp_df[comp_name_col].apply(_normalize) == norm_name]
            if not matches.empty:
                comp_match = matches.iloc[0]

        if comp_match is not None:
            committee = str(comp_match.get(comp_committee_col, "")).strip()
            first_activity_date = comp_match.get(comp_activity_col)
            days_ago = _parse_days_ago(first_activity_date)
            comp_link = comp_match.get(comp_link_col, "https://podio.com")

            if days_ago > 15:
                excel_2_companies_to_take.append({
                    "Company Name": name,
                    "Company Link": comp_link,
                    "Local Committee": committee,
                    "First Activity Date": str(first_activity_date),
                    "Days Since Activity": days_ago,
                    "Action": "Company we can take",
                })
            continue

        # 3. Genuine New Lead
        new_leads_to_enrich.append(lead)

    path1, path2 = None, None
    if excel_1_deal_accounts:
        path1 = os.path.join(OUTPUT_DIR, "excel_1_deal_accounts.xlsx")
        pd.DataFrame(excel_1_deal_accounts).to_excel(path1, index=False)

    if excel_2_companies_to_take:
        path2 = os.path.join(OUTPUT_DIR, "excel_2_companies_to_take.xlsx")
        pd.DataFrame(excel_2_companies_to_take).to_excel(path2, index=False)

    return excel_1_deal_accounts, excel_2_companies_to_take, new_leads_to_enrich, path1, path2