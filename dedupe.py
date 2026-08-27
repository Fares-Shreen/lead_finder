"""
Hybrid Database: SQLite with Google Sheets sync.
Tracks company status, confirmation dates, and admin modifications.
"""
import hashlib
import sqlite3
import pandas as pd
import streamlit as st
from contextlib import contextmanager
from datetime import datetime
from config import DB_PATH

_CLOUD_SYNC_DONE = False

@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def _get_gspread_client():
    """Initializes Google Sheets client by parsing raw JSON secret."""
    try:
        import json
        import gspread
        from google.oauth2.service_account import Credentials
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(st.secrets["gcp_raw_json"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Google Sheets Auth Error: {e}")
        return None

def init_db():
    global _CLOUD_SYNC_DONE
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                name_normalized TEXT PRIMARY KEY,
                name TEXT,
                field TEXT,
                location TEXT,
                website TEXT,
                linkedin TEXT,
                emails TEXT,
                phones TEXT,
                source TEXT,
                confirmed INTEGER DEFAULT 0,
                checked_date TEXT,
                found_at TEXT DEFAULT CURRENT_TIMESTAMP,
                podio_matched_title TEXT,
                podio_link TEXT,
                source_url TEXT
            )
        """)
        # Ensure checked_date column exists in older SQLite files
        try:
            c.execute("ALTER TABLE companies ADD COLUMN checked_date TEXT")
        except sqlite3.OperationalError:
            pass

        c.execute("""
            CREATE TABLE IF NOT EXISTS search_progress (
                source TEXT,
                field_normalized TEXT,
                location_normalized TEXT,
                next_offset INTEGER DEFAULT 0,
                PRIMARY KEY (source, field_normalized, location_normalized)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS search_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field TEXT,
                location TEXT,
                sources TEXT,
                num_per_source INTEGER,
                user_key_hash TEXT,
                searched_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    if not _CLOUD_SYNC_DONE:
        _pull_from_google_sheets()
        _CLOUD_SYNC_DONE = True

def _pull_from_google_sheets():
    client = _get_gspread_client()
    if not client or "sheet" not in st.secrets:
        return
    try:
        sh = client.open(st.secrets["sheet"]["name"])
        with _conn() as c:
            try:
                records = sh.worksheet("Local_Database").get_all_records()
                for r in records:
                    c.execute("""
                        INSERT OR IGNORE INTO companies 
                        (name_normalized, name, field, location, website, linkedin, emails, phones, source, confirmed, checked_date, found_at, podio_matched_title, podio_link, source_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        r.get("name_normalized", ""), r.get("name", ""), r.get("field", ""), 
                        r.get("location", ""), r.get("website", ""), r.get("linkedin", ""), 
                        str(r.get("emails", "")), str(r.get("phones", "")), r.get("source", ""), 
                        int(r.get("confirmed", 0) if str(r.get("confirmed")).isdigit() else 0),
                        r.get("checked_date", ""),
                        r.get("found_at", ""), r.get("podio_matched_title", ""), 
                        r.get("podio_link", ""), r.get("source_url", "")
                    ))
            except Exception:
                pass
            
            try:
                records = sh.worksheet("Search_Progress").get_all_records()
                for r in records:
                    c.execute("""
                        INSERT OR IGNORE INTO search_progress (source, field_normalized, location_normalized, next_offset)
                        VALUES (?, ?, ?, ?)
                    """, (r.get("source", ""), r.get("field_normalized", ""), r.get("location_normalized", ""), int(r.get("next_offset", 0))))
            except Exception:
                pass

            try:
                records = sh.worksheet("Search_Log").get_all_records()
                for r in records:
                    c.execute("""
                        INSERT OR IGNORE INTO search_log (id, field, location, sources, num_per_source, user_key_hash, searched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (r.get("id"), r.get("field", ""), r.get("location", ""), r.get("sources", ""), int(r.get("num_per_source", 0)), r.get("user_key_hash", ""), r.get("searched_at", "")))
            except Exception:
                pass
    except Exception as e:
        print(f"Error pulling from Google Sheets: {e}")

def sync_to_google_sheets():
    client = _get_gspread_client()
    if not client or "sheet" not in st.secrets:
        return
    try:
        sh = client.open(st.secrets["sheet"]["name"])
        with _conn() as c:
            df_comp = pd.read_sql("SELECT * FROM companies", c)
            df_prog = pd.read_sql("SELECT * FROM search_progress", c)
            df_log = pd.read_sql("SELECT * FROM search_log", c)
            
        _overwrite_worksheet(sh, "Local_Database", df_comp)
        _overwrite_worksheet(sh, "Search_Progress", df_prog)
        _overwrite_worksheet(sh, "Search_Log", df_log)
    except Exception as e:
        print(f"Error syncing to Google Sheets: {e}")

def _overwrite_worksheet(sh, tab_name, df):
    try:
        ws = sh.worksheet(tab_name)
    except Exception:
        ws = sh.add_worksheet(title=tab_name, rows=100, cols=20)
    ws.clear()
    if not df.empty:
        df = df.fillna("")
        ws.update([df.columns.values.tolist()] + df.values.tolist())

def _normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())

def get_search_offset(source: str, field: str, location: str) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT next_offset FROM search_progress WHERE source=? AND field_normalized=? AND location_normalized=?",
            (source, _normalize(field), _normalize(location)),
        ).fetchone()
        return row[0] if row else 0

def advance_search_offset(source: str, field: str, location: str, by: int):
    if by <= 0:
        return
    with _conn() as c:
        c.execute(
            """INSERT INTO search_progress (source, field_normalized, location_normalized, next_offset)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(source, field_normalized, location_normalized)
               DO UPDATE SET next_offset = next_offset + excluded.next_offset""",
            (source, _normalize(field), _normalize(location), by),
        )

def reset_search_offset(source: str, field: str, location: str):
    with _conn() as c:
        c.execute(
            "DELETE FROM search_progress WHERE source=? AND field_normalized=? AND location_normalized=?",
            (source, _normalize(field), _normalize(location)),
        )

def company_exists(name: str) -> bool:
    with _conn() as c:
        row = c.execute("SELECT 1 FROM companies WHERE name_normalized = ?", (_normalize(name),)).fetchone()
        return row is not None

def add_company(record: dict):
    with _conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO companies
               (name_normalized, name, field, location, website, linkedin, emails, phones, source, source_url, confirmed, checked_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '')""",
            (_normalize(record["name"]), record.get("name", ""), record.get("field", ""), record.get("location", ""), 
             record.get("website", ""), record.get("linkedin", ""), ", ".join(record.get("emails", []) or []), 
             ", ".join(record.get("phones", []) or []), record.get("source", ""), record.get("source_url", "")),
        )

def save_podio_duplicate(name: str, matched_title: str, link: str):
    now_str = datetime.now().strftime("%Y-%m-%d")
    with _conn() as c:
        c.execute(
            """INSERT INTO companies (name_normalized, name, confirmed, checked_date, podio_matched_title, podio_link)
               VALUES (?, ?, 1, ?, ?, ?)
               ON CONFLICT(name_normalized) DO UPDATE SET 
               confirmed=1, checked_date=?, podio_matched_title=excluded.podio_matched_title, podio_link=excluded.podio_link""",
            (_normalize(name), name, now_str, matched_title, link, now_str)
        )

def all_companies(include_confirmed: bool = False):
    cols = ["name", "field", "location", "website", "linkedin", "emails", "phones", "source", "source_url", "confirmed", "checked_date", "found_at"]
    where = "" if include_confirmed else "WHERE confirmed = 0 OR confirmed IS NULL"
    with _conn() as c:
        rows = c.execute(f"SELECT {', '.join(cols)} FROM companies {where} ORDER BY found_at DESC").fetchall()
        return [dict(zip(cols, r)) for r in rows]

def update_company_status(name: str, confirmed: bool):
    """Updates status and sets checked_date."""
    val = 1 if confirmed else 0
    date_str = datetime.now().strftime("%Y-%m-%d") if confirmed else ""
    with _conn() as c:
        c.execute(
            "UPDATE companies SET confirmed = ?, checked_date = ? WHERE name_normalized = ?",
            (val, date_str, _normalize(name)),
        )
    sync_to_google_sheets()

def delete_company(name: str):
    with _conn() as c:
        c.execute("DELETE FROM companies WHERE name_normalized = ?", (_normalize(name),))
    sync_to_google_sheets()

def log_search(field: str, location: str, sources: list, num_per_source: int, api_key=None):
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:12] if api_key else "no-key"
    with _conn() as c:
        c.execute(
            "INSERT INTO search_log (field, location, sources, num_per_source, user_key_hash) VALUES (?, ?, ?, ?, ?)",
            (field, location, ", ".join(sources), num_per_source, key_hash)
        )

def get_stats():
    with _conn() as c:
        total_searches = c.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]
        distinct_users = c.execute("SELECT COUNT(DISTINCT user_key_hash) FROM search_log").fetchone()[0]
        total_companies = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        confirmed_count = c.execute("SELECT COUNT(*) FROM companies WHERE confirmed = 1").fetchone()[0]
        recent = c.execute("SELECT field, location, sources, num_per_source, searched_at FROM search_log ORDER BY searched_at DESC LIMIT 20").fetchall()
    return {
        "total_searches": total_searches, "distinct_users": distinct_users,
        "total_companies": total_companies, "confirmed_count": confirmed_count,
        "recent_searches": [dict(zip(["field", "location", "sources", "num_per_source", "searched_at"], r)) for r in recent],
    }

def clear_all_data():
    with _conn() as c:
        c.execute("DELETE FROM search_log;")
        c.execute("DELETE FROM search_progress;")
        c.execute("DELETE FROM companies;")
        c.execute("DELETE FROM sqlite_sequence;")
    sync_to_google_sheets()