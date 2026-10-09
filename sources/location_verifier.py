"""Cross-check a directory company's identity and Alexandria address on Maps."""
import re
import unicodedata

from company_location import TARGET_LOCATION, alexandria_address
from sources.google_maps import search_google_maps


def identity_key(name):
    text = unicodedata.normalize("NFKC", str(name or "")).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    words = text.split()
    while words and words[-1] in {"llc", "ltd", "limited", "inc", "incorporated"}:
        words.pop()
    return " ".join(words)


def verify_on_maps(name, api_key):
    key = identity_key(name)
    if not key:
        return None
    places = search_google_maps(f'"{name}"', TARGET_LOCATION, 5, api_key=api_key)
    for place in places:
        if identity_key(place.get("name")) == key and alexandria_address(place.get("address")):
            return place
    return None
