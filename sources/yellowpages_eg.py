from sources.company_profiles import search_company_profiles


def search_yellowpages(field, location, num_results, start=0, api_key=None):
    return search_company_profiles("Yellow Pages", field, location, num_results, start, api_key)
