"""
Orchestrates the whole flow with Live Podio UI checking.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import dedupe
import podio_live_checker
from extractor import enrich_from_website
from excel_writer import append_companies
from sources.serpapi_search import search_google_companies, search_linkedin_companies
from sources.yellowpages_eg import search_yellowpages
from sources.clutch import search_clutch
from config import MAX_WORKERS_SOURCES, MAX_WORKERS_ENRICH

SOURCE_FUNCS = {
    "Google": lambda field, location, num, offset, api_key: search_google_companies(field, location, num, start=offset, api_key=api_key),
    "LinkedIn": lambda field, location, num, offset, api_key: search_linkedin_companies(field, location, num, start=offset, api_key=api_key),
    "Yellow Pages": lambda field, location, num, offset, api_key: search_yellowpages(
        field, location, num, start_page=1 + offset, max_pages=max(3, num // 15 + 2)
    ),
    "Clutch": lambda field, location, num, offset, api_key: search_clutch(
        field, location, num, start=offset, api_key=api_key
    ),
}

OFFSET_STEP = {"Google": 10, "LinkedIn": 10, "Yellow Pages": 1, "Clutch": 10}

def run_sources(field, location, sources, num_per_source=10, progress_cb=None, api_key=None):
    raw_hits = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS_SOURCES, len(sources) or 1)) as pool:
        futures = {}
        for s in sources:
            if s not in SOURCE_FUNCS:
                continue
            offset = dedupe.get_search_offset(s, field, location)
            fut = pool.submit(SOURCE_FUNCS[s], field, location, num_per_source, offset, api_key)
            futures[fut] = s
        for fut in as_completed(futures):
            source_name = futures[fut]
            try:
                hits = fut.result()
            except Exception as e:
                hits = []
                if progress_cb: progress_cb(f"⚠ {source_name} failed: {e}")
            if progress_cb: progress_cb(f"✓ {source_name}: {len(hits)} raw result(s)")
            dedupe.advance_search_offset(source_name, field, location, OFFSET_STEP.get(source_name, 0))
            raw_hits.extend(hits)
    return raw_hits

def _merge_duplicate_hits(raw_hits):
    merged = {}
    for hit in raw_hits:
        name = (hit.get("name") or "").strip()
        if not name: continue
        key = name.lower()
        source_url = hit.get("detail_url") or hit.get("linkedin") or hit.get("website") or ""

        if key not in merged:
            merged[key] = {
                "name": name,
                "website": hit.get("website"),
                "linkedin": hit.get("linkedin"),
                "phone": hit.get("phone"),
                "source_url": source_url,
                "sources": {hit.get("source", "")},
            }
        else:
            m = merged[key]
            m["website"] = m["website"] or hit.get("website")
            m["linkedin"] = m["linkedin"] or hit.get("linkedin")
            m["phone"] = m["phone"] or hit.get("phone")
            m["source_url"] = m["source_url"] or source_url
            m["sources"].add(hit.get("source", ""))
    return list(merged.values())

def process(field, location, sources, num_per_source=10, progress_cb=None, api_key=None, podio_email=None, podio_password=None):
    dedupe.init_db()
    dedupe.log_search(field, location, sources, num_per_source, api_key)

    raw_hits = run_sources(field, location, sources, num_per_source, progress_cb, api_key)
    candidates = _merge_duplicate_hits(raw_hits)

    not_in_local_db = []
    skipped_local = 0
    for c in candidates:
        if dedupe.company_exists(c["name"]):
            skipped_local += 1
            continue
        not_in_local_db.append(c)

    if progress_cb: progress_cb(f"Found {len(not_in_local_db)} new candidate(s). Launching live Podio check...")

    # Launch Playwright to check Deals & Companies
    deal_accounts, companies_to_take, to_enrich, excel1_path, excel2_path = podio_live_checker.analyze_leads_live(
        not_in_local_db, podio_email, podio_password, progress_cb
    )

    if progress_cb: progress_cb(f"Enriching {len(to_enrich)} genuine new leads...")

    def _do_enrich(c):
        info = enrich_from_website(c["website"]) if c["website"] else {"emails": [], "phones": [], "linkedin": None}
        phones = info.get("phones", [])
        if c.get("phone") and c["phone"] not in phones:
            phones = [c["phone"]] + phones

        emails = info.get("emails", [])
        if not emails and not phones:
            fallback_link = c.get("source_url") or c.get("website") or "No link available"
            emails = [f"Source: {fallback_link}"]

        return {
            "name": c["name"],
            "field": field,
            "location": location,
            "website": c["website"],
            "linkedin": c["linkedin"] or info.get("linkedin"),
            "emails": emails,
            "phones": phones,
            "source": ", ".join(sorted(s for s in c["sources"] if s)),
            "source_url": c.get("source_url", ""),
        }

    new_records = []
    if to_enrich:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_ENRICH) as pool:
            futures = [pool.submit(_do_enrich, c) for c in to_enrich]
            for fut in as_completed(futures):
                rec = fut.result()
                new_records.append(rec)
                dedupe.add_company(rec)

    excel_master_path = None
    if new_records:
        excel_master_path = append_companies(new_records)

    return new_records, skipped_local, deal_accounts, companies_to_take, excel_master_path, excel1_path, excel2_path