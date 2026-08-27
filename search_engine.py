"""
Orchestrates the scraping pipeline across multiple sources, removes duplicates, 
and runs Playwright to cross-check leads against Podio.
"""
from sources.linkedin import search_linkedin_companies
from sources.yellowpages_eg import search_yellowpages
from sources.wuzzuf import search_wuzzuf
from sources.indeed import search_indeed
from sources.google_maps import search_google_maps
from podio_live_checker import analyze_leads_live
import dedupe
import extractor
from urllib.parse import urlparse
import concurrent.futures

# Mappings for dynamic scraper calling
SOURCE_FUNCS = {
    "Google Maps": lambda field, location, num, offset, api_key: search_google_maps(field, location, num, start=offset, api_key=api_key),
    "LinkedIn": lambda field, location, num, offset, api_key: search_linkedin_companies(field, location, num, start=offset, api_key=api_key),
    "Yellow Pages": lambda field, location, num, offset, api_key: search_yellowpages(
        field, location, num, start_page=1 + offset, max_pages=max(3, num // 15 + 2)
    ),
    "Wuzzuf": lambda field, location, num, offset, api_key: search_wuzzuf(field, location, num, start=offset, api_key=api_key),
    "Indeed": lambda field, location, num, offset, api_key: search_indeed(field, location, num, start=offset, api_key=api_key),
}

OFFSET_STEP = {
    "Google Maps": 20, 
    "LinkedIn": 10, 
    "Yellow Pages": 1, 
    "Wuzzuf": 10, 
    "Indeed": 10
}

def clean_domain(url: str) -> str:
    """Extracts the base domain name (e.g., 'example.com') for deduplication."""
    if not url: return ""
    if not url.startswith("http"): url = "http://" + url
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except:
        return url
import requests
from urllib.parse import quote

def podio_api_precheck(company_name: str) -> bool:
    """
    Pings the public Podio Webform search API. 
    Returns True if Podio has data on this name (needs Playwright check).
    Returns False if it is completely empty (brand new lead, skip Playwright).
    """
    if not company_name: return False
    
    # URL encode the company name for the API query
    query = quote(company_name.strip())
    url = f"https://podio.com/webforms/25879454/1936053/items_search?field_id=238040132&query={query}&limit=50"
    
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            # If the response is totally empty, it's a new lead
            if not data:
                return False
            
            # If the response has the 'app' structure and contains items
            if isinstance(data, list) and len(data) > 0:
                first_item = data[0]
                if first_item.get("name") == "app" and len(first_item.get("contents", [])) > 0:
                    return True # Data found! Send to Playwright.
                    
        return False # Default to assuming it's new if the data structure is empty
    except Exception as e:
        print(f"Podio API Pre-check failed for {company_name}: {e}")
        # If the API fails for some reason, return True to fall back to the safe Playwright check
        return True
def process(field, location, sources, num_per_source, progress_cb=None, api_key=None, podio_email=None, podio_password=None):
    """
    1) Scrapes the selected sources for companies.
    2) Removes absolute duplicates (already in local database or duplicate domain).
    3) Enriches missing contact info.
    4) Uses Playwright to cross-check Podio Deals and Companies.
    """
    dedupe.init_db()
    
    if progress_cb: progress_cb(f"🚀 Starting Search Pipeline: {field} in {location}")
    if api_key and progress_cb: dedupe.log_search(field, location, sources, num_per_source, api_key=api_key)

    raw_candidates = []

# 1) Collect from Sources (Simultaneously)
    if progress_cb: progress_cb("📥 Launching scrapers simultaneously...")
    
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
                if progress_cb: progress_cb(f"❌ Error in {source_name}: {error}")
            else:
                for r in results:
                    r["field"] = field
                    r["location"] = location
                    raw_candidates.append(r)
                if progress_cb: progress_cb(f"✅ {source_name} returned {len(results)} records.")

    # 2) Initial Deduplication (Local DB + Session domains)
    if progress_cb: progress_cb(f"🧹 Found {len(raw_candidates)} total raw records. Deduplicating...")
    
    filtered_candidates = []
    skipped_local_count = 0
    seen_domains = set()

    for item in raw_candidates:
        c_name = item.get("name", "")
        if not c_name: continue

        if dedupe.company_exists(c_name):
            skipped_local_count += 1
            continue

        domain = clean_domain(item.get("website", ""))
        if domain:
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

        filtered_candidates.append(item)

    if progress_cb: 
        progress_cb(f"🔍 {len(filtered_candidates)} unique companies passed local checks.")
        if skipped_local_count > 0: progress_cb(f"🗑️ Skipped {skipped_local_count} already in local database.")

    # 3) Check Podio Live (via Playwright)
    if not filtered_candidates:
        return [], skipped_local_count, [], [], None, None, None

    if progress_cb: progress_cb("🌐 Checking Podio Deals and Companies...")
    
    deal_accounts, comp_take, new_leads_to_enrich, msg1, msg2 = analyze_leads_live(
        filtered_candidates, podio_email, podio_password, progress_cb
    )

    # 4) Save Podio Matches to DB so we don't scrape them again
    for d in deal_accounts: dedupe.save_podio_duplicate(d["Company Name"], d["Company Name"], d.get("Deal Link", ""))
    for c in comp_take: dedupe.save_podio_duplicate(c["Company Name"], c["Company Name"], c.get("Company Link", ""))

# 5) Enrich the Brand New Leads
    if progress_cb: progress_cb(f"✨ Found {len(new_leads_to_enrich)} brand new leads! Scanning their websites for Egyptian contacts...")
    
    final_new_leads = []
    for lead in new_leads_to_enrich:
        # Get whatever contact info the source (like Google Maps) already provided
        enriched_emails = set(lead.get("emails", []) if lead.get("emails") else [])
        enriched_phones = set(lead.get("phones", []) if lead.get("phones") else [])

        # If they have a website, scan it using extractor.py!
        if lead.get("website"):
            try:
                extracted_data = extractor.enrich_from_website(lead["website"])
                
                # Add the found emails and phones
                if extracted_data.get("emails"): 
                    enriched_emails.update(extracted_data["emails"])
                if extracted_data.get("phones"): 
                    enriched_phones.update(extracted_data["phones"])
                
                # Add LinkedIn if it was missing
                if not lead.get("linkedin") and extracted_data.get("linkedin"):
                    lead["linkedin"] = extracted_data["linkedin"]
            except Exception as e:
                pass

        # Save the combined, deduplicated contact info back to the lead
        lead["emails"] = list(enriched_emails)
        lead["phones"] = list(enriched_phones)
        final_new_leads.append(lead)

    # 6) Save Brand New Leads to DB
    for lead in final_new_leads:
        dedupe.add_company(lead)

    return final_new_leads, skipped_local_count, deal_accounts, comp_take, None, None, None