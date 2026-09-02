import os
import datetime
import pandas as pd
import streamlit as st

LOCAL_ACCOUNTS_FILE = "Aiesec_Accounts.xlsx"
ACCOUNTS_SHEET_TAB = "Aiesec_Accounts"

def _get_sheet():
    try:
        import podio_live_checker
        client = podio_live_checker._get_gspread_client()
        if client and "sheet" in st.secrets:
            sh = client.open(st.secrets["sheet"]["name"])
            try:
                return sh.worksheet(ACCOUNTS_SHEET_TAB)
            except Exception:
                # If tab doesn't exist, create it and add headers PLUS the default admin
                ws = sh.add_worksheet(title=ACCOUNTS_SHEET_TAB, rows=100, cols=5)
                ws.append_row(["Email", "Password", "Function", "Created_At"])
                ws.append_row(["admin@aiesec.net", "IGT1979", "Admin", str(datetime.date.today())])
                return ws
    except Exception:
        pass
    return None

def load_accounts() -> pd.DataFrame:
    ws = _get_sheet()
    if ws:
        records = ws.get_all_records()
        if records:
            return pd.DataFrame(records)
        else:
            # If sheet exists but is completely empty (someone deleted the rows)
            ws.append_row(["admin@aiesec.net", "admin", "Admin", str(datetime.date.today())])
            return pd.DataFrame(ws.get_all_records())
    
    # Fallback to local Excel file if no Google Sheet is connected
    if os.path.exists(LOCAL_ACCOUNTS_FILE):
        return pd.read_excel(LOCAL_ACCOUNTS_FILE)
    
    # Seed default admin account if local file does not exist
    default_df = pd.DataFrame([{
        "Email": "admin@aiesec.net",
        "Password": "admin",
        "Function": "Admin",
        "Created_At": str(datetime.date.today())
    }])
    default_df.to_excel(LOCAL_ACCOUNTS_FILE, index=False)
    return default_df

def authenticate(email: str, password: str):
    df = load_accounts()
    if df.empty:
        return None
    match = df[(df["Email"].str.strip().str.lower() == email.strip().lower()) & 
               (df["Password"].astype(str) == str(password))]
    if not match.empty:
        return match.iloc[0].to_dict()
    return None

def add_account(email: str, password: str, function: str) -> bool:
    df = load_accounts()
    if not df.empty and email.strip().lower() in df["Email"].str.strip().str.lower().values:
        return False  # User already exists
    
    new_entry = {
        "Email": email.strip().lower(),
        "Password": str(password).strip(),
        "Function": function,
        "Created_At": str(datetime.date.today())
    }
    
    ws = _get_sheet()
    if ws:
        ws.append_row(list(new_entry.values()))
    else:
        df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
        df.to_excel(LOCAL_ACCOUNTS_FILE, index=False)
    return True

def delete_account(email: str) -> bool:
    ws = _get_sheet()
    if ws:
        df = pd.DataFrame(ws.get_all_records())
        df = df[df["Email"].str.strip().str.lower() != email.strip().lower()]
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        return True
    elif os.path.exists(LOCAL_ACCOUNTS_FILE):
        df = pd.read_excel(LOCAL_ACCOUNTS_FILE)
        df = df[df["Email"].str.strip().str.lower() != email.strip().lower()]
        df.to_excel(LOCAL_ACCOUNTS_FILE, index=False)
        return True
    return False