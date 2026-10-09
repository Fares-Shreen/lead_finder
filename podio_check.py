"""
Checks whether a company already exists in your Podio "Companies" app,
via the public webform search endpoint you provided. Used as a final gate
before a newly found company gets added to our own database/Excel — if
it's already tracked in Podio, we skip it instead of duplicating it.

CAVEAT — I could not test this myself: podio.com's robots.txt blocks
automated fetching from my side entirely, so this is built purely from
the response shape you pasted, not verified against a live call. Test it
yourself first:

    python check_podio.py "a real company name already in your Podio"
    python check_podio.py "some made up company xyz123"

...and confirm the first prints FOUND and the second prints NOT FOUND
before relying on this in a real search. If either is wrong, send me
what check_podio.py prints (including the raw JSON it dumps) and I'll
fix the parsing to match.
"""
import requests

PODIO_SEARCH_URL = "https://podio.com/webforms/25879454/1936053/items_search"
FIELD_ID = "238040132"
REQUEST_TIMEOUT = 12
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def raw_podio_response(company_name: str):
    """Returns the parsed JSON response as-is, or None on any failure. Used by
    check_podio.py to show you exactly what Podio sends back."""
    try:
        r = requests.get(
            PODIO_SEARCH_URL,
            params={"field_id": FIELD_ID, "query": company_name.strip(), "limit": 50},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def check_podio(company_name: str):
    """
    Returns exists, matched_title, link, and status (match/no_match/unknown).
    Unknown means the request failed or its response could not be interpreted;
    callers must not treat it as proof of a duplicate or a completed check.

    IMPORTANT: `exists` is only True when one of Podio's returned item
    titles EXACTLY matches company_name (case-insensitive, whitespace-
    normalized). Podio's search returns loosely related items, not just
    exact matches — e.g. searching a gym's name can return other, unrelated
    clubs in the results. Treating any non-empty result as "already exists"
    (the first version of this file did) would incorrectly block real new
    companies just because Podio's search happened to return something
    tangentially similar. Only an exact title match counts as a real
    duplicate; a merely similar result does not block adding the company.
    """
    result = {"exists": False, "matched_title": None, "link": None, "status": "unknown"}
    if not company_name or not company_name.strip():
        return result

    data = raw_podio_response(company_name)
    if not isinstance(data, list):
        return result

    target = " ".join(company_name.casefold().split())
    malformed = False
    for app_entry in data:
        if not isinstance(app_entry, dict) or not isinstance(app_entry.get("contents"), list):
            malformed = True
            continue
        for item in app_entry.get("contents", []):
            if not isinstance(item, dict) or not isinstance(item.get("title"), str) or not item["title"].strip():
                malformed = True
                continue
            title = " ".join(item["title"].casefold().split())
            if title == target:
                result["exists"] = True
                result["status"] = "match"
                result["matched_title"] = item.get("title")
                result["link"] = item.get("link")
                return result
    if not malformed:
        result["status"] = "no_match"
    return result


def exists_in_podio(company_name: str) -> bool:
    """Backwards-compatible boolean wrapper around check_podio()."""
    return check_podio(company_name)["exists"]
