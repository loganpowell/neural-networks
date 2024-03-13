import json
import requests

from fns.keyvault import get_secret
from fns.openai_fns import get_embeddings

ALL_O_SERIES = "product/any(p: p eq 'O Series Cloud' or p eq 'O Series On-Premise' or p eq 'O Series On Demand')"

COLLECTIONS = {
    # should include returns, but no returns in KB
    "Cloud Indirect Tax": "product/any(p: p eq 'O Series Cloud')",
    "Indirect Tax O Series®": "product/any(p: p eq 'O Series Cloud')",
    "Indirect Tax Intelligence®": "product/any(p: p eq 'Indirect Tax Intelligence')",
    "O Series Edge": "product/any(p: p eq 'O Series Edge')",
    # in menu, not in KB
    "Tax Categorization": "product/any(p: p eq 'Tax Categorization')",
    # should we do only cloud?
    "Payroll Tax": "product/any(p: p eq 'Cloud Payroll Tax' or p eq 'Payroll Tax')",
    "Certificate Center": "product/any(p: p eq 'Certificate Center')",
    "Vertex Cloud": "product/any(p: p eq 'Vertex Cloud')",
    # "Address Cleansing": all_o_series,
    # "Data Integrity": "product/any(p: p eq ' ')", # no KB articles
    # "Rate File": "product/any(p: p eq ' ')", # no KB articles
    # "Retail Tax Extract": "product/any(p: p eq ' ')", # should be o series lite/retail, but not in KB
    # "Rate Locator Online": "product/any(p: p eq ' ')", # no KB articles
    # "Returns & Reporting": "product/any(p: p eq ' ')", # no KB articles
}

with open("../constants.json") as f:
    config = json.load(f)
    search_api_version = config["search_api_version"]
    search_index_name = config["search_index_name"]


def search(
    embeddings=get_embeddings("Test"),
    index_name=search_index_name,
    api_version=search_api_version,
    product=None,
    tax_process=None,
    algorithm='HNSW-NVM',
    k=3
):
    # if index name is not provided, use shared config (NEW)
    azure_index = index_name
    azure_api_version = api_version

    _year, _month, _day = api_version.split('-') if api_version else []
    year = int(_year)
    month = int(_month)

    collection = COLLECTIONS.get(product) if product else None

    filter = None
    if collection and tax_process:
        filter = f"{collection} and tax_process/any(p: p eq '{tax_process}')"
    elif collection:
        filter = collection
    elif tax_process:
        filter = f"tax_process/any(p: p eq '{tax_process}')"

    select = "id, content, metadata, title, tax_process, product, modified_time, heading"

    if year >= 2023 and month >= 10:
        query = {
            "count": True,
            "vectorQueries": [{
                "k": k,
                "vector": embeddings,
                "fields": "content_vector",
                "kind": "vector",
                "exhaustive": "exhaustive" in algorithm,
            }],
            "select": select,
        }

        if filter:
            query["vectorFilterMode"] = "postFilter"
            query["filter"] = filter
    else:
        query = {
            "top": k,
            "vector": {
                "k": k,
                "value": embeddings,
                "fields": 'content_vector',
                "filter": filter,
            },
            "select": select,
        }

    try:
        search_base_url = get_secret("primary-search-service-base-url")
        search_key = get_secret("primary-search-service-secondary-key")
        url = f"{search_base_url}/indexes/{azure_index}/docs/search?api-version={azure_api_version}"
        response = requests.post(
            url,
            json=query,
            headers={
                "api-key": search_key,
                'Content-Type': 'application/json'
            },
            timeout=20
        )
        result = response.json()
        if not result['value']:
            print("Problem with 'search' API call")

        return result
    except:
        print("Error during fetch to Azure")
        raise Exception(
            "Error in `search` function calling Azure Cognitive Search API"
        )
