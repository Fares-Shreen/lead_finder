import requests
from urllib.parse import urlparse, quote

from sources.linkedin import search_linkedin_companies
from sources.yellowpages_eg import search_yellowpages
from sources.wuzzuf import search_wuzzuf
from sources.indeed import search_indeed
from sources.google_maps import search_google_maps
import dedupe
import extractor

SOURCE_FUNCS = {
    "Google Maps": search_google_maps,
    "LinkedIn": search_linkedin_companies,
    "Yellow Pages": search_yellowpages,
    "Wuzzuf": search_wuzzuf,
    "Indeed": search_indeed
}

OFFSET_STEP = { "Google Maps": 5, "LinkedIn": 10, "Yellow Pages": 10, "Wuzzuf": 10, "Indeed": 10 }

def podio_api_precheck(company_name: str) -> bool:
    """Returns True if the API finds data (Suspect), False if empty (Brand New)."""
    if not company_name: return False
    query = quote(company_name.strip())
    url = f"https://podio.com/webforms/25879454/1936053/items_search?field_id=238040132&query={query}&limit=50"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if not data: return False
            if isinstance(data, list) and len(data) > 0:
                first_item = data[0]
                if first_item.get("name") == "app" and len(first_item.get("contents", [])) > 0:
                    return True 
        return False 
    except Exception:
        return True 

def process(field, location, sources, num_per_source, progress_cb=None, api_key=None, podio_email=None, podio_password=None, function_type="IGT", created_by=""):
    raw_candidates = []
    
    if progress_cb: progress_cb("📥 Launching scrapers (bypassing bot protections)...")
    
    # FIX: Run scrapers sequentially instead of concurrently to prevent Playwright ThreadPool crashes
    for source_name in sources:
        if progress_cb: progress_cb(f"⏳ Scraping {source_name}...")
        
        offset = dedupe.get_search_offset(source_name, field, location)
        try:
            results = SOURCE_FUNCS[source_name](field, location, num_per_source, offset, api_key)
            dedupe.advance_search_offset(source_name, field, location, OFFSET_STEP.get(source_name, 10))
            
            for r in results:
                r["field"] = field
                r["location"] = location
                r["function_type"] = function_type
                r["created_by"] = created_by
                raw_candidates.append(r)
                
            if progress_cb: progress_cb(f"✅ {source_name}: Found {len(results)} leads.")
        except Exception as e:
            if progress_cb: progress_cb(f"❌ Error in {source_name}: {e}")

    filtered_candidates = []
    seen_names = set()
    seen_domains = set()

    for lead in raw_candidates:
        c_name = lead["name"].strip()
        c_lower = c_name.lower()
        if c_lower in seen_names or dedupe.company_exists(c_name) or dedupe.is_suspect(c_name):
            continue
        domain = ""
        if lead.get("website"):
            parsed = urlparse(lead["website"])
            domain = parsed.netloc.replace("www.", "").lower()
            if domain in seen_domains: continue
                
        seen_names.add(c_lower)
        if domain: seen_domains.add(domain)
        filtered_candidates.append(lead)

    # ENRICH EVERYTHING UPFRONT
    if progress_cb: progress_cb(f"✨ Deeply enriching {len(filtered_candidates)} unique candidates...")
    
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

    # API SPEED CHECK
    if progress_cb: progress_cb(f"🚀 Running Webform API Speed Check on {len(fully_enriched_candidates)} leads...")
    
    definitely_new = []
    suspects_for_later = []
    
    for lead in fully_enriched_candidates:
        if podio_api_precheck(lead["name"]):
            suspects_for_later.append(lead)
        else:
            definitely_new.append(lead)

    # SAVE RESULTS
    if progress_cb: progress_cb(f"✅ Safe: {len(definitely_new)} | 🕵️ Suspects: {len(suspects_for_later)}")

    # Brand new go straight to master DB
    for lead in definitely_new:
        dedupe.add_company(lead)
        
    # Suspects go to the new Google Sheet
    if suspects_for_later:
        dedupe.add_suspects_to_sheet(suspects_for_later)

    dedupe.log_search(field, location, sources, num_per_source, api_key)
    dedupe.sync_to_google_sheets()

    return definitely_new, suspects_for_later