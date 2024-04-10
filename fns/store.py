from langchain.vectorstores.azuresearch import AzureSearch

from .azure_fns import (
    VECTOR_STORE_API_KEY,
    VECTOR_STORE_URL,
    create_index,
    fields,
    vector_search,
)
from .openai_fns import embedding_function


def create(
    index_name: str,
    ef_construction: int,
    ef_search: int,
    m: int,
    embed_fn=embedding_function,
):
    """
    Create an index in the vector store with the given parameters
    """
    create_index(
        index_name=index_name,
        efConstruction=ef_construction,
        efSearch=ef_search,
        m=m,
    )

    index = AzureSearch(
        azure_search_endpoint=VECTOR_STORE_URL,
        azure_search_key=VECTOR_STORE_API_KEY,
        index_name=index_name,
        embedding_function=embed_fn,
        # fields are required upon upsertion of documents
        fields=fields,
        vector_search=vector_search(
            efConstruction=ef_construction,
            efSearch=ef_search,
            m=m,
        ),
        # scoring_profiles=[sc_profile],
        # default_scoring_profile=sc_name,
    )

    return index


def hydrate(store, chunks):
    """
    Hydrate a vector store with the given chunks
    """
    ids = store.add_documents(chunks)
    print(f"Added {len(ids)} documents to {store.index_name}")
