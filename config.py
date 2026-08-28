"""
Central configuration.

Fill these in (or set as environment variables with the same names)
before running the app.

WHY SERPAPI INSTEAD OF GOOGLE'S OWN CUSTOM SEARCH API:
Google's Custom Search JSON API is closed to new signups as of 2025 and
is being fully discontinued on January 1, 2027 (per Google's own developer
docs), so it isn't a viable long-term option for a new project. SerpApi
gives real Google results (and, via a `site:linkedin.com/company` query,
real LinkedIn company pages) with a durable free tier instead: 250 real
searches/month, recurring every month, no credit card required to start.

Get a free key here: https://serpapi.com/users/sign_up
(your key appears on your SerpApi dashboard after signing up)

Free tier: 250 searches/month, recurring, forever (Aug 2026 pricing).
Paid tiers start at $25/month for 1,000 searches if you ever need more —
though Yellow Pages and Clutch need no key at all and have no cap, so lean
on those first.
"""
import os

# --- SerpApi (covers general web search + LinkedIn company pages) ---
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

# --- Admin panel (remove companies, confirmed list, usage dashboard) -----
# SECURITY NOTE: the default below is a plaintext fallback so the app
# works immediately. Since this repo is going to GitHub, that default
# will be permanently visible in your commit history even if you change
# it later. Before you push, set ADMIN_PASSWORD as a Streamlit Cloud
# "Secret" instead (same place as SERPAPI_KEY) so the real password
# never lives in the source code.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "$IGT_TEAM_SHAHD$")

# --- Networking ---
REQUEST_TIMEOUT = 12          # seconds per HTTP request
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
MAX_WORKERS_SOURCES = 4       # parallel directory sources
MAX_WORKERS_ENRICH = 8        # parallel "visit website, get email/phone"

# --- Storage ---
DB_PATH = os.path.join(os.path.dirname(__file__), "companies.db")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
