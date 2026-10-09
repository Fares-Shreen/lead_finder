from sources.company_profiles import search_company_profiles


def search_clutch(field, location, num=10, start=0, api_key=None):
    return search_company_profiles("Clutch", field, location, num, start, api_key)
