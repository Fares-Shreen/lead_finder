"""
Stand-in "database" for checking whether a company was already found —
plus confirm/hide state, admin deletion, and basic usage stats.

Today this is a local SQLite file (companies.db) so the tool works out of
the box. Later, when you have a real central database, replace the core
functions here (init_db / company_exists / add_company / all_companies /
etc.) with calls to that database's client (Postgres/MySQL/API/etc).
Nothing else in the app needs to change, since app.py and search_engine.py
only ever call these functions.
"""
import hashlib
import sqlite3
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
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
                found_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migrations for existing databases
        try:
            c.execute("ALTER TABLE companies ADD COLUMN confirmed INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        try:
            c.execute("ALTER TABLE companies ADD COLUMN podio_matched_title TEXT")
        except sqlite3.OperationalError:
            pass
            
        try:
            c.execute("ALTER TABLE companies ADD COLUMN podio_link TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE companies ADD COLUMN source_url TEXT")
        except sqlite3.OperationalError:
            pass

        # Tracks how far each source has already searched for a given
        # field+location, so repeat searches ask for the NEXT batch of
        # results instead of the same top results every time.
        c.execute("""
            CREATE TABLE IF NOT EXISTS search_progress (
                source TEXT,
                field_normalized TEXT,
                location_normalized TEXT,
                next_offset INTEGER DEFAULT 0,
                PRIMARY KEY (source, field_normalized, location_normalized)
            )
        """)

        # One row per search run, for the admin usage dashboard.
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


def _normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())


# --- Search pagination progress -------------------------------------------

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
    """Start this source+field+location back from the beginning."""
    with _conn() as c:
        c.execute(
            "DELETE FROM search_progress WHERE source=? AND field_normalized=? AND location_normalized=?",
            (source, _normalize(field), _normalize(location)),
        )


# --- Companies --------------------------------------------------------------

def company_exists(name: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM companies WHERE name_normalized = ?",
            (_normalize(name),),
        ).fetchone()
        return row is not None


def add_company(record: dict):
    """record keys: name, field, location, website, linkedin, emails, phones, source, source_url"""
    with _conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO companies
               (name_normalized, name, field, location, website, linkedin, emails, phones, source, source_url, confirmed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                _normalize(record["name"]),
                record.get("name", ""),
                record.get("field", ""),
                record.get("location", ""),
                record.get("website", ""),
                record.get("linkedin", ""),
                ", ".join(record.get("emails", []) or []),
                ", ".join(record.get("phones", []) or []),
                record.get("source", ""),
                record.get("source_url", ""),
            ),
        )

def save_podio_duplicate(name: str, matched_title: str, link: str):
    """Saves a company found on Podio into the database and marks it as confirmed."""
    with _conn() as c:
        c.execute(
            """INSERT INTO companies (name_normalized, name, confirmed, podio_matched_title, podio_link)
               VALUES (?, ?, 1, ?, ?)
               ON CONFLICT(name_normalized) DO UPDATE SET 
               confirmed=1, 
               podio_matched_title=excluded.podio_matched_title, 
               podio_link=excluded.podio_link""",
            (_normalize(name), name, matched_title, link)
        )

def all_companies(include_confirmed: bool = False):
    """
    By default, returns only NOT-yet-confirmed companies — this is what
    the main list shown to every user should call, since confirmed
    companies are meant to be hidden from the everyday view (they still
    exist in the database, just not shown here).
    """
    cols = ["name", "field", "location", "website", "linkedin", "emails", "phones", "source", "source_url", "confirmed", "found_at"]
    where = "" if include_confirmed else "WHERE confirmed = 0 OR confirmed IS NULL"
    with _conn() as c:
        rows = c.execute(f"SELECT {', '.join(cols)} FROM companies {where} ORDER BY found_at DESC").fetchall()
        return [dict(zip(cols, r)) for r in rows]


def confirmed_companies():
    """Admin-only view: companies marked as confirmed/used or synced from Podio."""
    cols = ["name", "field", "location", "website", "linkedin", "emails", "phones", "source", "source_url", "found_at", "podio_matched_title", "podio_link"]
    with _conn() as c:
        rows = c.execute(
            f"SELECT {', '.join(cols)} FROM companies WHERE confirmed = 1 ORDER BY found_at DESC"
        ).fetchall()
        return [dict(zip(cols, r)) for r in rows]


def set_confirmed(name: str, confirmed: bool = True):
    """Marks a company as confirmed/used (hides it from the normal list,
    keeps it in the database) or un-marks it."""
    with _conn() as c:
        c.execute(
            "UPDATE companies SET confirmed = ? WHERE name_normalized = ?",
            (1 if confirmed else 0, _normalize(name)),
        )


def delete_company(name: str):
    """Permanently removes a company from the database. Admin-only in the UI."""
    with _conn() as c:
        c.execute("DELETE FROM companies WHERE name_normalized = ?", (_normalize(name),))


# --- Usage stats --------------------------------------------------------------

def log_search(field: str, location: str, sources: list, num_per_source: int, api_key=None):
    """
    Records one search run for the admin dashboard. Stores only a short
    hash of the SerpApi key (not the key itself) as a rough, privacy-
    conscious proxy for "which teammate" — this app has no real login
    system, so distinct keys are the closest available signal for
    counting distinct users.
    """
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:12] if api_key else "no-key"
    with _conn() as c:
        c.execute(
            """INSERT INTO search_log (field, location, sources, num_per_source, user_key_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (field, location, ", ".join(sources), num_per_source, key_hash),
        )


def get_stats():
    with _conn() as c:
        total_searches = c.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]
        distinct_users = c.execute("SELECT COUNT(DISTINCT user_key_hash) FROM search_log").fetchone()[0]
        total_companies = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        confirmed_count = c.execute("SELECT COUNT(*) FROM companies WHERE confirmed = 1").fetchone()[0]
        recent = c.execute(
            "SELECT field, location, sources, num_per_source, searched_at FROM search_log ORDER BY searched_at DESC LIMIT 20"
        ).fetchall()
    return {
        "total_searches": total_searches,
        "distinct_users": distinct_users,
        "total_companies": total_companies,
        "confirmed_count": confirmed_count,
        "recent_searches": [
            dict(zip(["field", "location", "sources", "num_per_source", "searched_at"], r)) for r in recent
        ],
    }

def clear_all_data():
    """Wipes all records from the database and resets auto-incrementing IDs."""
    with _conn() as c:
        c.execute("DELETE FROM search_log;")
        c.execute("DELETE FROM search_progress;")
        c.execute("DELETE FROM companies;")
        c.execute("DELETE FROM sqlite_sequence;")