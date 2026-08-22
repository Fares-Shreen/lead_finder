# Company Lead Finder

Searches Google, LinkedIn, Yellow Pages Egypt and Clutch **in parallel** for
companies in a given field + location, skips any company already saved
(so nothing gets re-added or re-scraped), pulls email/phone/LinkedIn/website
from the company's own site, and exports the new results to Excel.

## Setup
```bash
pip install -r requirements.txt
```

You need a free SerpApi key for the Google and LinkedIn sources (Yellow
Pages and Clutch don't need a key). **Note:** Google's own Custom Search
API is closed to new signups and shutting down entirely on Jan 1, 2027, so
this uses SerpApi instead — 250 real Google searches/month, recurring,
free, no credit card needed:
1. https://serpapi.com/users/sign_up → sign up (no card required)
2. Copy your API key from your SerpApi dashboard

Set it as an environment variable before running:
```bash
export SERPAPI_KEY="your-key"
```

## Run
```bash
streamlit run app.py
```
Opens a page with 3 inputs — **Field**, **Location**, **Sources** — plus a
"results per source" slider. Submitting runs all chosen sources at once
(threaded), shows live progress, and gives you a downloadable `.xlsx`.

## How the pieces fit together
- `sources/` — one file per directory (Google/LinkedIn via SerpApi,
  Yellow Pages Egypt, Clutch) — each returns a plain
  list of `{name, website/linkedin, source}` dicts.
- `extractor.py` — visits a company's own website and its contact page to
  pull emails, phone numbers, and a LinkedIn link with regex/HTML parsing.
- `dedupe.py` — the "have we seen this company before?" check. **Today
  it's a local SQLite file** (`companies.db`) so the app works standalone.
  When you have a real central database, swap the 4 functions in this
  file for calls to that database — `app.py` and `search_engine.py` don't
  need to change at all.
- `excel_writer.py` — appends only genuinely new companies to the sheet.
- `search_engine.py` — the orchestrator: runs sources in parallel threads,
  dedupes, enriches only the new ones in parallel, writes Excel.

## Deploying for your team (GitHub → Streamlit Community Cloud)

Vercel can't run this app at all — it only runs stateless serverless
functions, and Streamlit needs a real, always-on server with a persistent
connection. The workflow you actually want (push to GitHub → click Deploy
on a dashboard) exists for Streamlit itself instead:

1. Push this whole folder to a GitHub repo (public, or private on your
   own account — Community Cloud supports both, though the free tier
   only runs one private app at a time).
2. Go to **share.streamlit.io**, sign in with GitHub.
3. **New app** → pick your repo/branch → main file path: `app.py` → Deploy.
4. *(Optional)* Under **Advanced settings → Secrets**, you can set a
   server-wide default key so people don't have to paste one in:
   ```
   SERPAPI_KEY = "your-key-here"
   ```
   This isn't required — the app already asks each visitor for their own
   key. It just saves you (or a teammate) a step during testing.

You'll get a shareable `yourapp.streamlit.app` URL teammates can open directly.

**Two honest things to know about running this as a shared team app,
both because it's a bigger jump than the solo-desktop use case so far:**

- **SQLite (`companies.db`) is fine for light team use, not heavy
  concurrent use.** Community Cloud runs one instance that all visitors
  share, so `companies.db` and the Excel file genuinely *are* shared
  across teammates — which is what you want. But if several people run
  searches at the exact same moment, SQLite can occasionally throw a
  "database is locked" error under real write contention. For occasional
  use by a small team this is unlikely to bite; if it does, that's
  exactly the moment to do the real-database swap in `dedupe.py` we
  already designed for.
- **The free tier sleeps after ~12 hours idle** and caps memory around
  1GB — a real headless Chromium browser (for the Clutch fallback) eats
  into that budget, so Clutch may be the first thing to fail under
  memory pressure even if Yellow Pages/Google/LinkedIn keep working fine.
  If Clutch matters a lot to your team, Railway or Render (paid, but
  cheap, always-on, more memory) is the more reliable home for this app
  — happy to prep that instead if it becomes worth it.


- **LinkedIn and Google cannot be scraped directly** — both actively block
  bots with CAPTCHAs/login walls, and doing so breaks their Terms of
  Service. This tool instead uses Google's *official* Custom Search API,
  which returns real Google results (and LinkedIn company-page results via
  a `site:linkedin.com/company` query) without violating anyone's ToS.
  This is the only reliable way to do this long-term — a raw scraper
  against Google/LinkedIn will get blocked within minutes.
- **Yellow Pages Egypt and Clutch selectors are best-effort.** I based
  them on the real, live structure of yellowpages.com.eg, but any
  directory site can change its HTML at any time, and Clutch sits behind
  Cloudflare bot-protection on some pages. If a source returns 0 results,
  open that site, run a manual search, and update the CSS selectors in
  `sources/yellowpages_eg.py` / `sources/clutch.py` accordingly — the rest
  of the pipeline doesn't need to change.
- **Email/phone extraction only works if the info is on the page itself**
  (not hidden behind a "click to reveal" JS widget or an image).
- Please scrape at a reasonable rate and respect each site's
  `robots.txt` and Terms of Service — this is meant for legitimate B2B
  lead generation, not high-volume harvesting.

## Podio duplicate check, confirm/hide, and admin panel

- **Podio check**: before a newly found company is added to our database
  or Excel, it's checked against your Podio "Companies" app search
  endpoint. If Podio already has it, it's skipped instead of duplicated.
  **I could not test this myself** — podio.com's robots.txt blocks my
  fetch tool entirely — so verify it works before trusting it:
  ```
  python check_podio.py "a real company name already in your Podio"
  python check_podio.py "some made up company xyz123"
  ```
  First should print FOUND, second NOT FOUND. If either is wrong, send me
  everything it prints and I'll fix the parsing in `podio_check.py`.

- **Confirm & hide**: check the box next to any saved company to confirm
  you've used it — a popup asks you to confirm, then it's hidden from the
  everyday list (but stays in the database, and admins can still see it).

- **Admin panel** (password-gated, default password set in `config.py`):
  remove a company permanently, view the confirmed/hidden companies, and
  a usage dashboard (total searches, distinct users — approximated by
  distinct SerpApi keys, since there's no real login system — companies
  in the DB, and confirmed count).

  **Before you push to GitHub**, move the admin password out of the
  source code: set `ADMIN_PASSWORD` as a Streamlit Cloud Secret (same
  place as `SERPAPI_KEY`), so it isn't permanently visible in your repo's
  commit history.

## Swapping in your real database later
Everything that touches storage goes through `dedupe.py`. Replace:
- `company_exists(name)` → `SELECT 1 FROM your_table WHERE name = ...`
- `add_company(record)` → `INSERT INTO your_table ...`
- `all_companies()` → your table's read query

No changes needed anywhere else.
py -m streamlit run app.py
