import concurrent.futures
from collections import Counter
from urllib.parse import urlparse
from podio_check import check_podio

from sources.linkedin import search_linkedin_companies
from sources.yellowpages_eg import search_yellowpages
from sources.wuzzuf import search_wuzzuf
from sources.indeed import search_indeed
from sources.google_maps import search_google_maps
import dedupe
import extractor
from lead_quality import sanitize_lead
from company_location import TARGET_LOCATION

SOURCE_FUNCS = {
    "Google Maps": search_google_maps,
    "LinkedIn": search_linkedin_companies,
    "Yellow Pages": search_yellowpages,
    "Wuzzuf": search_wuzzuf,
    "Indeed": search_indeed
}

OFFSET_STEP = { "Google Maps": 5, "LinkedIn": 10, "Yellow Pages": 10, "Wuzzuf": 10, "Indeed": 10 }

def podio_api_precheck(company_name: str):
    """True = exact match, False = no match, None = check unavailable."""
    result = check_podio(company_name)
    if result["status"] == "unknown":
        return None
    return result["exists"]

def process(field, location, sources, num_per_source, progress_cb=None, api_key=None, podio_email=None, podio_password=None, function_type="IGT", created_by="", run_report=None):
    location = TARGET_LOCATION
    report = run_report if run_report is not None else {}
    report.update(source_errors={}, source_counts={}, podio_matches=0, podio_unavailable=0)
    if not sources:
        return [], []
    raw_candidates = []
    
    if progress_cb: progress_cb("📥 Launching SerpApi scrapers simultaneously...")
    def fetch_source(source_name):
        offset = dedupe.get_search_offset(source_name, field, location)
        try:
            results = SOURCE_FUNCS[source_name](field, location, num_per_source, offset, api_key)
            dedupe.advance_search_offset(source_name, field, location, OFFSET_STEP.get(source_name, 10))
            return source_name, results, None
        except Exception as e:
            return source_name, [], str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = [executor.submit(fetch_source, s) for s in sources]
        for future in concurrent.futures.as_completed(futures):
            source_name, results, error = future.result()
            if error:
                report["source_errors"][source_name] = error
                if progress_cb: progress_cb(f"❌ Error in {source_name}: {error}")
            else:
                report["source_counts"][source_name] = len(results)
                if progress_cb: progress_cb(f"✅ {source_name}: Found {len(results)} location-qualified company profiles.")
                diagnostics = getattr(results, "diagnostics", {})
                if progress_cb and diagnostics:
                    progress_cb(f"🔬 {source_name}: " + "; ".join(f"{label}: {count}" for label, count in diagnostics.items()))
                for r in results:
                    r["field"] = field
                    r["function_type"] = function_type
                    r["created_by"] = created_by
                    raw_candidates.append(r)

    filtered_candidates = []
    rejected_by_quality = 0
    duplicate_count = 0
    existing_suspect_count = 0
    rejection_reasons = Counter()
    seen_names = set()
    seen_domains = set()

    for lead in raw_candidates:
        lead, reason = sanitize_lead(lead)
        if not lead:
            rejected_by_quality += 1
            rejection_reasons[reason] += 1
            continue
        c_name = lead["name"].strip()
        c_lower = c_name.lower()
        if c_lower in seen_names or dedupe.company_exists(c_name):
            duplicate_count += 1
            continue
        if dedupe.is_suspect(c_name):
            existing_suspect_count += 1
            continue
        domain = ""
        if lead.get("website"):
            parsed = urlparse(lead["website"])
            domain = parsed.netloc.replace("www.", "").lower()
            if domain in seen_domains:
                duplicate_count += 1
                continue
                
        seen_names.add(c_lower)
        if domain: seen_domains.add(domain)
        filtered_candidates.append(lead)

    if progress_cb and rejected_by_quality:
        details = ", ".join(f"{reason}: {count}" for reason, count in rejection_reasons.items())
        progress_cb(f"🧹 Removed {rejected_by_quality} results ({details}).")
    if progress_cb:
        progress_cb(f"📋 {len(filtered_candidates)} new companies | {duplicate_count} already saved/duplicate | {existing_suspect_count} already awaiting Podio check.")

    if not filtered_candidates:
        if progress_cb:
            progress_cb("ℹ️ No new location-qualified companies on this round.")
            if report["source_errors"]:
                progress_cb("⚠️ Failed sources are incomplete, not empty. Their result pages were not advanced.")
        dedupe.log_search(field, location, sources, num_per_source, api_key)
        dedupe.sync_to_google_sheets()
        return [], []

    if progress_cb: progress_cb(f"✨ Deeply enriching {len(filtered_candidates)} candidates upfront...")
    
    fully_enriched_candidates = []
    for lead in filtered_candidates:
        enriched_emails = set(lead.get("emails", []) if lead.get("emails") else [])
        enriched_phones = set(lead.get("phones", []) if lead.get("phones") else [])

        if lead.get("website"):
            try:
                extracted = extractor.enrich_from_website(lead["website"])
                if extracted.get("emails"): enriched_emails.update(extracted["emails"])
                if extracted.get("phones"): enriched_phones.update(extracted["phones"])
                if not lead.get("linkedin") and extracted.get("linkedin"):
                    lead["linkedin"] = extracted["linkedin"]
            except Exception:
                pass

        lead["emails"] = list(enriched_emails)
        lead["phones"] = list(enriched_phones)
        fully_enriched_candidates.append(lead)

    if progress_cb: progress_cb(f"🚀 Running Webform API Speed Check on {len(fully_enriched_candidates)} leads...")
    
    definitely_new = []
    suspects_for_later = []
    
    for lead in fully_enriched_candidates:
        podio_result = podio_api_precheck(lead["name"])
        if podio_result is None:
            lead["podio_check_status"] = "unavailable"
            lead["podio_check_reason"] = "Podio check unavailable or response unreadable; duplicate status unknown."
            report["podio_unavailable"] += 1
            suspects_for_later.append(lead)
        elif podio_result:
            lead["podio_check_status"] = "exact_match"
            lead["podio_check_reason"] = "Exact company-name match found in Podio."
            report["podio_matches"] += 1
            suspects_for_later.append(lead)
        else:
            lead["podio_check_status"] = "no_match"
            definitely_new.append(lead)

    if progress_cb:
        progress_cb(f"✅ No Podio match: {len(definitely_new)} | Exact matches: {report['podio_matches']} | Check unavailable: {report['podio_unavailable']}")

    for lead in definitely_new:
        dedupe.add_company(lead)
        
    if suspects_for_later:
        dedupe.add_suspects_to_sheet(suspects_for_later)

    dedupe.log_search(field, location, sources, num_per_source, api_key)
    dedupe.sync_to_google_sheets()

    return definitely_new, suspects_for_later
