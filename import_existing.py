"""
Imports companies from an existing leads Excel file (in the same format
excel_writer.py produces) into the dedupe database, so the app treats
them as already-found and won't re-add or re-research them.

Usage:
    python import_existing.py path/to/leads_master.xlsx
    python import_existing.py                              (defaults to output/leads_master.xlsx)
"""
import sys

import openpyxl

import dedupe

DEFAULT_PATH = "output/leads_master.xlsx"


def import_excel(path):
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    dedupe.init_db()
    imported, skipped = 0, 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        name, field, location, website, linkedin, emails, phones, source, _found_at = (
            list(row) + [None] * (9 - len(row))
        )[:9]

        if dedupe.company_exists(name):
            skipped += 1
            continue

        dedupe.add_company({
            "name": name,
            "field": field or "",
            "location": location or "",
            "website": website or "",
            "linkedin": linkedin or "",
            "emails": [e.strip() for e in (emails or "").split(",") if e.strip()],
            "phones": [p.strip() for p in (phones or "").split(",") if p.strip()],
            "source": source or "",
        })
        imported += 1

    print(f"Imported {imported} companies, {skipped} were already in the database.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    import_excel(path)
