import json

import requests

from azure.search.documents.indexes.models import (
    FreshnessScoringFunction,
    FreshnessScoringParameters,
    ScoringProfile,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    TextWeights,
)
from .keyvault import get_secret
from .openai_fns import get_embeddings


with open("../constants.json") as f:
    config = json.load(f)
    search_api_version = config["search_api_version"]
    search_index_name = config["search_index_name"]

VECTOR_STORE_URL = get_secret("primary-search-service-base-url")
VECTOR_STORE_API_KEY = get_secret("primary-search-service-secondary-key")

ALGO_CONFIG_NAME = "HNSW-NVM"

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


def search_params(
    api_version=search_api_version,
    efConstruction=400,
    efSearch=500,
    m=4,
) -> dict:
    """
    HNSW algo config for vector search
    """
    print("api_version:", api_version)
    [*values] = api_version.split("-")
    [year, month, day, *rest] = values
    year = int(year)
    month = int(month)
    day = int(day)

    if year >= 2023 and month >= 10:
        return {
            "profiles": [
                {
                    "name": ALGO_CONFIG_NAME,
                    "algorithm": "hnsw-1",
                    # "vectorizer": "vertex-vector",
                },
                {
                    "name": "exhausive",
                    "algorithm": "knn-1",
                },
            ],
            "algorithms": [
                {
                    "name": "hnsw-1",
                    "kind": "hnsw",
                    "hnswParameters": {
                        "m": m,
                        "metric": "cosine",
                        "efConstruction": efConstruction,
                        "efSearch": efSearch,
                    },
                },
                # Subtype value exhaustiveKnn has no mapping, use base class VectorSearchAlgorithmConfiguration.
                {
                    "name": "knn-1",
                    "kind": "exhaustiveKnn",
                    "exhaustiveKnnParameters": {
                        "metric": "cosine",
                    },
                },
            ],
            # not available in 2023-11-01
            # "vectorizers": [
            #    {
            #        "name": "vertex-vector",
            #        "kind": "azureOpenAI",
            #        "azureOpenAIParameters": {
            #            "resourceUri": OPENAI_BASE_URL,
            #            "deploymentId": OPENAI_EMBEDDING_DEPLOYMENT,
            #            "apiKey": OPENAI_API_KEY,
            #        },
            #    }
            # ],
        }
    else:
        return {
            "algorithmConfigurations": [
                {
                    "name": ALGO_CONFIG_NAME,
                    "kind": "hnsw",
                    "hnswParameters": {
                        "m": m,
                        "efConstruction": efConstruction,
                        "efSearch": efSearch,
                        "metric": "cosine",
                    },
                }
            ]
        }


def create_index(
    index_name=search_index_name,
    api_version=search_api_version,
    efConstruction=400,
    efSearch=500,
    m=4,
):
    """
    uses the requests library to make a call to the azure search api to create
    an index

    inputs:
        - index: name of the index to create
        - efConstruction: number of neighbors inserted during construction
        - efSearch: number of neighbors considered during search
        - m: bi-directional links per vertex
        - env: environment to create the index in

    outputs:
        - response: response from the azure search api upon creating the index

    """

    # ?{index_name}"  # ?api-version={api_version}&allowIndexDowntime=true"
    base_url = f"{VECTOR_STORE_URL}/indexes"
    params = {"api-version": api_version, "allowIndexDowntime": "true"}

    [*values] = api_version.split("-")
    [year, month, day, *rest] = values
    year = int(year)
    month = int(month)
    day = int(day)
    preview = len(rest) > 0

    headers = {
        "Content-Type": "application/json",
        "api-key": VECTOR_STORE_API_KEY,
    }

    print("vector store url:", base_url)

    body = {
        "name": index_name,
        # these must be set upon creation of the index
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {
                "name": "metadata",
                "type": "Edm.String",
                "searchable": True,
            },
            {
                "name": "content",
                "type": "Edm.String",
                "searchable": True,
            },
            {
                "name": "content_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "dimensions": len(get_embeddings("Test")["data"][0]["embedding"]),
                **(
                    {"vectorSearchProfile": ALGO_CONFIG_NAME}
                    if year >= 2023 and month >= 10
                    else {"vectorSearchConfiguration": ALGO_CONFIG_NAME}
                ),
            },
            {
                "name": "title",
                "type": "Edm.String",
                "searchable": True,
            },
            {
                "name": "heading",
                "type": "Edm.String",
                "searchable": True,
            },
            {
                "name": "product",
                "type": "Collection(Edm.String)",
                "filterable": True,
                # [3] normalizer not available in 2023-11-01
                **({"normalizer": "lowercase"} if month != 11 and not preview else {}),
            },
            {
                "name": "tax_process",
                "type": "Collection(Edm.String)",
                "filterable": True,
                **({"normalizer": "lowercase"} if month != 11 and not preview else {}),
            },
            {"name": "modified_time", "type": "Edm.DateTimeOffset", "filterable": True},
        ],
        "corsOptions": {"allowedOrigins": ["*"], "maxAgeInSeconds": 60},
        "vectorSearch": search_params(
            efConstruction=efConstruction,
            efSearch=efSearch,
            m=m,
        ),
    }
    try:
        print(
            f"Creating index {index_name} at url: {
                base_url} and body: \n {json.dumps(body, indent=2)}"
        )
        response = requests.post(
            url=base_url,
            params=params,
            headers=headers,
            json=body,
            timeout=60,
        )
        print(json.dumps(response.text, indent=2))

    except Exception as error:
        print("ERROR:", error)
        raise error

    print(f"🌊 created index {index_name} 🌊\n", response)

    return response


"""
References:

[1]: https://learn.microsoft.com/en-us/azure/search/vector-search-overview#approximate-nearest-neighbors
[2]: https://learn.microsoft.com/en-us/azure/search/index-add-scoring-profiles
[3]: https://learn.microsoft.com/en-us/azure/search/search-normalizers
[4]: https://www.pinecone.io/learn/series/faiss/hnsw/
[5]: https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-create-index?tabs=portal-add-field%2Cpush%2Cportal-check-index#add-a-vector-field-to-the-fields-collection
[6]: https://learn.microsoft.com/en-us/azure/search/search-normalizers

"""

# Create a new index with a Scoring Profile:
# https://python.langchain.com/docs/integrations/vectorstores/azuresearch
# https://learn.microsoft.com/en-us/azure/search/search-query-odata-filter
# https://learn.microsoft.com/en-us/azure/search/search-normalizers
# fields are required upon upsertion of documents in the vector store
fields = [
    SimpleField(
        name="id",
        type=SearchFieldDataType.String,
        key=True,
        fiterable=True,
    ),
    SearchableField(
        name="metadata",
        type=SearchFieldDataType.String,
        searchable=True,
    ),
    SearchableField(
        name="content",
        type=SearchFieldDataType.String,
        searchable=True,
    ),
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=len(get_embeddings("Test")[
                                     "data"][0]["embedding"]),
        # search_params_configuration=ALGO_CONFIG_NAME,
    ),
    SearchableField(
        name="title",
        type=SearchFieldDataType.String,
        searchable=True,
    ),
    SearchableField(
        name="heading",
        type=SearchFieldDataType.String,
        searchable=True,
    ),
    SimpleField(
        name="product",
        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
        _filterable=True,
        normalizer="lowercase",
    ),
    SimpleField(
        name="tax_process",
        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
        _filterable=True,
        normalizer="lowercase",
    ),
    SimpleField(
        name="modified_time",
        type=SearchFieldDataType.DateTimeOffset,
        _filterable=True,
    ),
]


def delete_index(index_name=search_index_name, api_version=search_api_version):
    """
    uses the requests library to make a call to the azure search api to delete an index
    """
    base_url = f"{VECTOR_STORE_URL}/indexes/{index_name}"
    params = {"api-version": api_version, "allowIndexDowntime": "true"}
    headers = {
        "Content-Type": "application/json",
        "api-key": VECTOR_STORE_API_KEY,
    }
    response = requests.delete(
        base_url, headers=headers, params=params, timeout=60)
    print(f"INDEX {index_name} DELETED:", response)
    return response


sc_name = "baseline_scoring_profile"
# weights can be updated without recreating the index
# via API:
# https://learn.microsoft.com/en-us/rest/api/searchservice/update-index
# https://learn.microsoft.com/en-us/azure/search/index-add-scoring-profiles

# I didn't find this to actually do anything...
sc_profile = ScoringProfile(
    name=sc_name,
    text_weights=TextWeights(weights={"content": 1.0, "title": 1.5}),
    # sum (default), average, minimum, maximum, firstMatching
    function_aggregation="sum",
    functions=[
        FreshnessScoringFunction(
            field_name="modified_time",
            boost=5.0,
            parameters=FreshnessScoringParameters(
                boosting_duration="P30D",  # period = 30 days
            ),
            interpolation="linear",
        ),
        # TagScoringFunction(
        #    field_name="product",
        #    boost=2.0,
        #    parameters=TagScoringParameters(
        #        tags_parameter="product",
        #    ),
        #    interpolation="linear",
        # ),
        # TagScoringFunction(
        #    field_name="tax_process",
        #    boost=2.0,
        #    parameters=TagScoringParameters(
        #        tags_parameter="process",
        #    ),
        #    interpolation="linear",
        # ),
    ],
)


def vector_search(
    embeddings,
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

    _filter = None
    if collection and tax_process:
        _filter = f"{collection} and tax_process/any(p: p eq '{tax_process}')"
    elif collection:
        _filter = collection
    elif tax_process:
        _filter = f"tax_process/any(p: p eq '{tax_process}')"

    select = "id, content, metadata, title, tax_process, product, modified_time, heading, content_vector"

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

        if _filter:
            query["vectorFilterMode"] = "postFilter"
            query["filter"] = _filter
    else:
        query = {
            "top": k,
            "vector": {
                "k": k,
                "value": embeddings,
                "fields": 'content_vector',
                "filter": _filter,
            },
            "select": select,
        }

    try:
        search_base_url = get_secret("primary-search-service-base-url")
        search_key = get_secret("primary-search-service-secondary-key")
        url = f"{
            search_base_url}/indexes/{azure_index}/docs/search?api-version={azure_api_version}"
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
        # print("result:", result)
        if not result['value']:
            print("Problem with 'search' API call")

        return result
    except:
        print("Error during fetch to Azure")
        raise Exception(
            "Error in `search` function calling Azure Cognitive Search API"
        )
