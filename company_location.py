"""Conservative evidence checks for the Alexandria, Egypt search area.

The search query, company name, country subdomain and requested `location`
are not evidence of an office. Require an address or an explicit location
statement returned by the source. Unclear companies are excluded.
"""
import re

TARGET_LOCATION = "Alexandria, Egypt"


def _text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


CITY = r"(?:Alexandria|الإسكندرية|الاسكندرية|إسكندرية|اسكندرية)"
COUNTRY = r"(?:Egypt|مصر|EG)"
CITY_RE = re.compile(rf"(?<!\w){CITY}(?!\w)", re.I)
COUNTRY_RE = re.compile(rf"(?<!\w){COUNTRY}(?!\w)", re.I)
FOREIGN_RE = re.compile(r"\b(?:USA|United States|Virginia|Louisiana|Romania|Australia|Scotland|South Africa)\b", re.I)
FORWARD_PAIR = rf"{CITY}(?:\s+Governorate)?\s*(?:\d{{4,7}}\s*)?[,،·|\-]\s*(?:(?:Alexandria(?: Governorate)?|Al Iskandariyah|الإسكندرية|الاسكندرية|محافظة الإسكندرية|محافظة الاسكندرية)\s*(?:\d{{4,7}}\s*)?[,،]\s*)?{COUNTRY}"
PAIR = rf"(?:{FORWARD_PAIR}|{COUNTRY}\s*[,،·|\-]\s*{CITY})"
LOCATION_STATEMENT = re.compile(
    rf"(?:\b(?:headquarters|headquartered|head office|office address|registered address)\b|المقر الرئيسي|العنوان|الموقع"
    rf"|(?:^|[.;|·]\s*)(?:address|location)\b"
    rf"|\b(?:company|business|agency|studio|production house|we are)\s+(?:is\s+)?(?:based in|located in)\b)"
    rf"\s*[:：.\-]?\s*(?:(?:is\s+)?based\s+)?(?:in\s+)?(?P<address>{PAIR})(?!\w)",
    re.I,
)
PROFILE_LOCATION_LINE = re.compile(rf"(?:^|[·|]\s*)\s*(?P<address>{PAIR})(?!\w)", re.I)


def alexandria_address(value):
    address = _text(value)
    return bool(re.search(PAIR, address, re.I) and not FOREIGN_RE.search(address))


def location_evidence(lead):
    """Return source evidence, never the query location, or an empty string."""
    address = _text(lead.get("address"))
    if address:
        # An explicit conflicting address overrides a search snippet.
        return address if alexandria_address(address) else ""

    snippet = _text(lead.get("snippet"))
    match = LOCATION_STATEMENT.search(snippet) or PROFILE_LOCATION_LINE.search(snippet)
    if match:
        return match.group("address")
    return ""
