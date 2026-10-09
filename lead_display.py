"""Stable display schema for search results, including older lead records."""
import pandas as pd


DISCOVERY_COLUMNS = [
    "name", "location", "location_evidence", "source",
    "website", "linkedin", "source_url", "podio_check_status",
]


def discovery_frame(records):
    # Older records/sources can omit entire columns. Leave missing values blank;
    # the requested search location must never be invented as location evidence.
    return pd.DataFrame(records).reindex(columns=DISCOVERY_COLUMNS, fill_value="").fillna("").astype(str)
