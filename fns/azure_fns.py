import os
import sys
import json
import asyncio
import requests

from gremlin_python.driver.protocol import GremlinServerError, GremlinServerWSProtocol
from gremlin_python.driver.aiohttp.transport import AiohttpTransport
from enum import Enum
from urllib.parse import quote_plus, quote
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
from azure.core.exceptions import AzureError
from azure.core.credentials import AzureKeyCredential
from azure.cosmos import exceptions, CosmosClient, PartitionKey

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
from azure.storage.blob import BlobServiceClient, BlobClient, BlobSasPermissions, generate_blob_sas
from azure.core.exceptions import ResourceNotFoundError
from pathlib import Path

# graph db
from gremlin_python.driver import client as gremlin, serializer, driver_remote_connection as DriverRemoteConnection

# mongo db
# from pymongo import MongoClient

from dotenv import load_dotenv, dotenv_values
from glom import glom, flatten

from .openai_fns import get_embeddings
from .keyvault import get_secret
from .regex_fns import no_special_chars
from .utils import RELATIVE_PATH


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

env = dotenv_values(f"{RELATIVE_PATH}.env")

with open(f"{RELATIVE_PATH}constants.json") as f:
    config = json.load(f)
    search_api_version = config["search_api_version"]
    search_index_name = config["search_index_name"]


#       /                                888 ,e,
# e88~88e 888-~\  e88~~8e  888-~88e-~88e 888  "  888-~88e
# 888 888 888    d888  88b 888  888  888 888 888 888  888
# "88_88" 888    8888__888 888  888  888 888 888 888  888
#  /      888    Y888    , 888  888  888 888 888 888  888
# Cb      888     "88___/  888  888  888 888 888 888  888
#  Y8""8D

# https://github.com/Azure-Samples/cosmos-notebooks/blob/c8ce5f5319459f2a6a7f8fe55b6c62dd9ee78753/All_API_quickstarts/GremlinIntroduction.ipynb

GREMLIN_ENDPOINT = env["GREMLIN_ENDPOINT"]
GREMLIN_KEY = env["GREMLIN_KEY"]
GREMLIN_DB = env["GREMLIN_DB"]
GREMLIN_GRAPH = env["GREMLIN_GRAPH"]
ENGLISH_PARTITION = "en"
PARTITION_KEY = "lang"


def gremlin_client(
    db=GREMLIN_DB,
    graph=GREMLIN_GRAPH,
):
    "Spins up a gremlin client for the graph db"
    return gremlin.Client(
        url=f"wss://{GREMLIN_ENDPOINT}.gremlin.cosmos.azure.com:443/{db}",
        traversal_source="g",
        username=f"/dbs/{db}/colls/{graph}",
        password=GREMLIN_KEY,
        message_serializer=serializer.GraphSONSerializersV2d0(),
        # headers={'MaxContentLength': "1000000"}
    )


client_gremlin = gremlin_client()

gremlin_error_codes = {
    400: 'Gremlin Query Compilation Error',
    409: 'Conflict exception. You\'re probably inserting the same ID again.',
    429: 'Not enough RUs for this query. Try again.',
    1002: "Gremlin Query Execution Error"
}

query_options = {
    # 'EnableCrossPartitionQuery': True,  # Enable cross-partition query
    'maxItemCount': -1,                   # Maximum number of items to return per query
    # 'PageSize': 100                     # Page size for result pagination
}


def exec_gremlin(
    query_string,
    client=client_gremlin
):
    "Executes a gremlin query (async) on the graph db and returns the result"
    try:
        callback = client.submitAsync(
            query_string,
            # request_options=query_options
        )
        if callback.result() is not None:
            return callback.result().one()
    except GremlinServerError as ex:
        status = ex.status_attributes['x-ms-status-code']
        print(f'There was an exception: {status}')
        print(f'🔥 Problem with this query: 🔥 \n\n{query_string}\n\n')
        print(gremlin_error_codes.get(status, 'Unknown error'))
        print(ex)

#    Yb  dP 8888
#     YbdP  8www
#     dPYb  8
#    dP  Yb 8


def graph_xf_compress(target, omit=None):
    "compress verbose default gremlin output to a more readable format"
    if omit is None:
        omit = []
    return [
        {
            "id": node["id"],
            "label": node["label"],
            "type": node["type"],
            **{k: v[0]["value"] for k, v in node["properties"].items() if k not in omit}
        }
        for node in target
    ]


def graph_xf_props(
    payload,
    glom_spec="0.*.value.*.key",
    omit=None
):
    """
    Takes a payload that looks like this:

    ```json
    [
      {
        "PUB:en:TOP": {
          "key": { ... },
          "value": {
            "PUB:en:TOP:4": {
              "key": {
                "id": "PUB:en:TOP:4",
                "label": "chunk",
                "type": "vertex",
                "properties": {
                  "lang": [{ "id": "PUB:en:TOP:4|lang", "value": "en"}],
                  "product": [{"id": "123","value": "..., ..."}],
                  "tax_process": [{"id": "234","value": "..., ..."}],
                  "title": [{"id": "345","value": "..."}],
                  "heading": [{"id": "456","value": "..."}],
                  "md": [{"id": "567","value": "...long markdown string..."}],
                  "order": [{"id": "678","value": 4}]
                }
              },
              "value": {}
            },
            ...
          }
        }
      }
    ]
    ```
    and simplifies it to this:
    ```json
    [
        {
            "id": "PUB:en:TOP:4",
            "label": "chunk",
            "type": "vertex",
            "order": 4,
        },
    ]
    ```
    """
    if omit is None:
        omit = ["lang", "product", "tax_process"]

    target = flatten(glom(payload, spec=glom_spec)) if glom_spec else payload
    return graph_xf_compress(target, omit)


def sort_by_key(payload: list[dict], key: str):
    """
    Sorts a list of dictionaries by a key
    """
    return sorted(payload, key=lambda x: x[key])

#                           w
#    .d88  8   8 .d88b 8d8b w .d88b d88b
#    8  8  8b d8 8.dP' 8P   8 8.dP' `Yb.
#    `Y88  `Y8P8 `Y88P 8    8 `Y88P Y88P
#       8P


# === GET ===

jargon = {
    "both": "both",
    "in": "inE",
    "out": "outE",
    "mean": ".mean()",
    "max": ".max()",
    "min": ".min()",
    "sum": ".sum()",
    "count": ".count()",
}

graph_queries = {
    "get_vertex_count_by_label": {
        "query": "g.V().group().by('label').by(count())",
        "output": [
            {
                "topic": 2645,
                "chunk": 5727,
                "publication": 125
            }
        ]
    }
}


def graph_get_mean(
    sample=500,
    direction="in"
):
    """
    Gets the mean links of a sample number of nodes in the graph db
    """
    _dir = jargon[direction]
    query = (
        f"g.V().sample({sample})",
        ".project('vertex', 'links')",
        f".by({_dir}().count())",
        ".map(select('links'))",
        ".mean()"
    )
    query = "".join(query)
    return exec_gremlin(query)


def graph_get_most_connected(
    node_ids: list[str],
    direction="both",
    pop=True,
):
    """
    From a list of node ids, returns the node with the most connections
    """
    _dir = jargon[direction]

    ids = ", ".join([f'"{id}"' for id in node_ids])
    query = (
        f"g.V().hasId({ids})",
        ".project('vertex', 'degree')",
        ".by()",
        f".by({_dir}().count())",
        ".order().by(select('degree'), decr)",
    ) + ((
        ".limit(1)",
        ".select('vertex')"
    ) if pop else ())

    query = "".join(query)
    print(f"graph_get_most_connected Query: {query}")

    results = exec_gremlin(query)
    if pop:
        return results
    else:
        return {result["vertex"]["id"]: result["degree"] for result in results}


def graph_get_connections(
    node_ids: list[str],
    direction="both",
    stat=None
):
    """
    From a list of node ids, returns the node with the most connections
    """
    _dir = jargon[direction]
    _stat = jargon[stat] if stat else ""

    ids = ", ".join([f'"{id}"' for id in node_ids])
    query = (
        f"g.V().hasId({ids})",
        ".project('vertex', 'degree')",
        f".by({_dir}().count())",
        ".select('degree')",
        _stat
    )
    query = "".join(query)
    print(f"graph_get_connections Query: {query}")
    return exec_gremlin(query)


def graph_get_in_common(
        nodes_ids: list[str],):
    """
    Gets the nodes that are in common between a list of nodes (exclusive of provided nodes)
    """
    provided = ", ".join([f'"{id}"' for id in nodes_ids])
    query = (
        f"g.V({provided})",
        ".aggregate('provided')",
        ".both()",
        ".where(without('provided'))",  # only nodes not in provided
        ".groupCount()",
        # ".order(local)",
        # ".by(values, decr)",
        # ".limit(1)",
        # ".select(keys)"
    )
    query = "".join(query)
    print(f"graph_get_in_common Query: {query}")
    return exec_gremlin(query)


def graph_get_connected(
    node_id,
    relation,
    prop_tuple=None,
    direction="out"
):
    """
    Gathers all connections of a node in the graph db by their relation

    example:
    ```python
    graph_get_connected("COSMyEnterprise:en:Taxpayers:0", "child")
    ```
    """
    query = f"g.V('{node_id}').{direction}('{relation}')"

    if prop_tuple:
        query += f".has('{prop_tuple[0]}', '{prop_tuple[1]}')"

    query += ".tree()"

    print(f"graph_get_connected Query: {query}")
    results = exec_gremlin(query)
    return results


def graph_get_chunk_by_parent(
        node_id,
        heading
):
    """
    Gets the actual chunk id for a chunk returned from the search_kb function
    """
    return graph_get_connected(node_id, "parent", ("heading", heading))

# === UPSERT ===

# CollapseOSConfigurationParameters:en:189165&pubname=OSConfigurationParameters


def upsert_edges(
    from_id,
    to_id,
    rel_to=None,  # e.g., "parent"
    rel_from=None,  # e.g., "child"
    execute=True
):
    """
    creates an edge between two nodes in the graph db

    example - outgoing direction from Luis to Andrew:
    g.V('Luis').addE('knows').to(g.V('Andrew')).property('weight', 0.5).next()

    example - incoming direction to Rimma from Andrew:
    "g.V('Rimma').addE('knows').from(g.V('Andrew'))"

    only upsert if non-existant (idempotent)
    """
    results = []
    if rel_to:
        query = (
            f"g.V('{from_id}').coalesce(",
            f"outE('{rel_to}').where(inV().hasId('{to_id}')),",
            f"addE('{rel_to}').from(__.V('{from_id}')).to(__.V('{to_id}'))",
            ")"
        )
        q1 = "".join(query)
        # q1 = f"g.V('{from_id}').addE('{rel_to}').to(g.V('{to_id}'))"
        if execute:
            r1 = exec_gremlin(q1)
            results.append(r1)
        else:
            results.append(q1)
    if rel_from:
        query = (
            f"g.V('{to_id}').coalesce(",
            f"outE('{rel_from}').where(inV().hasId('{from_id}')),",
            f"addE('{rel_from}').to(__.V('{from_id}')).from(__.V('{to_id}'))",
            ")"
        )
        q2 = "".join(query)
        # q2 = f"g.V('{to_id}').addE('{rel_from}').from(g.V('{from_id}'))"
        if execute:
            r2 = exec_gremlin(q2)
            results.append(r2)
        else:
            results.append(q2)
    return results

# create enum for node type: publication, topic, chunk


class NodeType(Enum):
    "Enum for valid node types in the graph db"
    PUBLICATION = "publication"
    TOPIC = "topic"
    CHUNK = "chunk"


def upsert_node(
    node_id,
    node_type: NodeType,
    properties: dict = None,
    execute=True,
    partition=ENGLISH_PARTITION,
    partition_key=PARTITION_KEY
):
    """
    creates a node in the graph db
    properties is a dict whos values can only be:
    - string
    - number
    - boolean

    only upsert if non-existent (idempotent):
    https://stackoverflow.com/a/50354351
    """
    if properties is None:
        properties = {}

    def handle_primitive(value):
        if isinstance(value, str):
            return f"'{value}'"
        return value

    message = (
        f"g.V().hasId('{node_id}').fold()",
        ".coalesce(unfold(),",
        f"addV('{node_type}')",
        f".property('id', '{node_id}')",
        f".property('{partition_key}', '{partition}')",
        ")",
        * (f".property('{k}', {handle_primitive(v)})" for k,
           v in properties.items()),
    )

    message = "".join(message)

    if execute:
        result = exec_gremlin(message)
        return result
    else:
        return [message]

# === DELETE ===


def gather_connections(node_id, relation="knows"):
    """
    Gathers all connections of a node in the graph db by their relation
    """
    query = f"g.V('{node_id}').out('{relation}')"
    results = exec_gremlin(query)
    return results


def machiavelli(
    node_id,
    relation="parent",
    results=None
):
    """
    Gathers all decendants of a node in the graph db by their relation
    (recursive)
    """
    if results is None:
        results = []

    children = gather_connections(node_id, relation)
    results.extend(children)
    if len(children) > 0:
        for child in children:
            machiavelli(child["id"], relation, results)
    return results


def prune(node_id, relation="parent", inclusive=True):
    """
    🔥 use with caution 🔥

    Deletes a subgraph of decendant nodes by targeting a progenitor node 

    (will include the progenitor node itself if inclusive=True)

    Gathers all decendants and deletes them

    Source: https://stackoverflow.com/a/45243153
    """
    decendants = machiavelli(node_id, relation)

    targets = [node["id"] for node in decendants]
    if inclusive:
        targets.append(node_id)

    quoted = [f"'{target}'" for target in targets]

    query = f"g.V().hasId({', '.join(quoted)}).drop()"

    return exec_gremlin(query)

#      8
# 88b. 8 .d88 8d8b. 8d8b. .d88b 8d8b
# 8  8 8 8  8 8P Y8 8P Y8 8.dP' 8P
# 88P' 8 `Y88 8   8 8   8 `Y88P 8
# 8


def combine(x):
    "Combines a list of strings into a single string separated by commas"
    return ", ".join(x) if isinstance(x, list) else x if x else ""


def pluck_xf(payload: dict, xfs: dict = None):
    """
    Plucks and transforms a dictionary using a dictionary of transformation functions
    """
    if xfs is None:
        xfs = {
            "product": combine,
            "tax_process": combine,
        }

    return {k: xfs[k](payload[k]) for k in xfs.keys()}


def spawn_plan(
    from_id,  # initially topic_id (article)
    digest,
    metadata,
    plan=None,
    lang="en"
):
    """
    Spawns plans to generate 
    - nodes and edges in the graph db
    - vectors in the vector store
    - documents/content in a key value store

    Takes a id (to be a source/'from') - example:
    "OSOverview/en/OSeriesHome"

    and a list of links (to be targets/'to') - example:
    ```json
    {
      "links": [
        {
          "raw": "/csh?topicname=OSeriesHome.html&pubname=OSOverview",
          "text": "Overview of O Series",
          "topic": "OSeriesHome",
          "publication": "OSOverview",
          "href": "https://community.vertexinc.com/s/document-item?bundleId=OSOverview&topicId=OSeriesHome.html&_LANG=enus"
        },
      ],
      "chunks": [
        {
          "title": "Taxability precedence hierarchy in O Series",
          "heading": "Taxability precedence hierarchy in O Series",
          "md": "...string with markdown content...",
          "links": [
            {
              "raw": "#showid/186454",
              "text": "financial events",
              "topic": "186454",
              "publication": "COSOverview",
              "href": "https://community.vertexinc.com/s/document-item?bundleId=COSOverview&topicId=186454.html&_LANG=enus"
            }
          ]
        },
    }
    ```

    and generates a plan of queries to execute, e.g.:

    ```json
    {
        "gremlin": { "vertices": [], "edges": [] }
        "vector": [{ ...vector store args ...}], list[dict]
        "kv": [{ ...kv store args ...}], list[dict]
    }

    ```
    """
    if plan is None:
        plan = {
            "gremlin": {"vertices": [], "edges": []},
            "vector": [],
            "kv": []
        }
    meta = pluck_xf(metadata)

    path = from_id.split(":")

    vertices = []
    edges = []
    pub_id = None
    if len(path) > 2:
        # full article path
        pub_id = path[0]
        topic_id = path[2]
        # create a link between the publication and the topic
        edge = upsert_edges(
            from_id=pub_id,
            to_id=from_id,
            rel_to="parent",
            rel_from="child",
            execute=False
        )
        edges.extend(edge)
    else:
        # just a publication id
        pub_id = from_id

    pub_node = upsert_node(
        node_id=pub_id,
        node_type="publication",
        properties=meta,  # no properties for now
        execute=False
    )
    vertices.extend(pub_node)
    # handle node generation first
    topic = digest["chunks"]
    # create a node for the article
    topic_node = upsert_node(
        node_id=from_id,
        node_type="topic",
        properties=meta,
        execute=False
    )
    vertices.extend(topic_node)
    for i, chunk in enumerate(topic):
        chunk_id = f"{from_id}:{i}"
        chunk_properties = {
            **meta,
            "title": no_special_chars(chunk["title"]),
            "heading": no_special_chars(chunk["heading"]),
            # TODO: store this in a KV store instead
            "md": no_special_chars(chunk["md"]),
            "order": i
        }
        chunk_node = upsert_node(
            node_id=chunk_id,
            node_type="chunk",
            properties=chunk_properties,
            execute=False
        )
        vertices.extend(chunk_node)
        chunk_links = chunk["links"]
        # create parent:child relationships between chunks and topic
        topic_chunk_edges = upsert_edges(
            from_id=from_id,
            to_id=chunk_id,
            rel_to="parent",
            rel_from="child",
            execute=False
        )
        edges.extend(topic_chunk_edges)
        for link in chunk_links:
            # append to links list
            topic_id = f"{link['publication']}:{lang}:{link['topic']}"
            chunk_topic_edges = upsert_edges(
                from_id=chunk_id,
                to_id=topic_id,
                rel_to="related",
                execute=False
            )
            edges.extend(chunk_topic_edges)
            chunk_topic_node = upsert_node(
                node_id=topic_id,
                node_type="topic",
                execute=False
            )
            vertices.extend(chunk_topic_node)

    article_links = digest["links"]
    for link in article_links:
        if link['topic']:
            topic_id = f"{link['publication']}:{lang}:{link['topic']}"
            article_article_links = upsert_edges(
                from_id=from_id,
                to_id=topic_id,
                rel_to="related",
                execute=False
            )
            edges.extend(article_article_links)
            # create node stubs for related articles
            topic_node = upsert_node(
                node_id=topic_id,
                node_type="topic",
                execute=False
            )
            vertices.extend(topic_node)
    plan["gremlin"]["vertices"].extend(vertices)
    plan["gremlin"]["edges"].extend(edges)
    # TODO: handle vector generation third
    # TODO: handle kv generation last
    return plan

# 888       888          888
# 888-~88e  888  e88~-_  888-~88e
# 888  888b 888 d888   i 888  888b
# 888  8888 888 8888   | 888  8888
# 888  888P 888 Y888   ' 888  888P
# 888-_88"  888  "88_-~  888-_88"


def blobs_uri(account):
    return f"https://{account}.blob.core.windows.net/"


def write_file(path, data, encoding='utf-8'):
    """
    Writes a file to either local storage or Azure Blob Storage.
    param path: the path to the file (e.g. 'benchmarks/file.txt')
        - if the path is local, the file will be written to the local filesystem
        - if the path is remote, the blob will be stored as 
            - container: the first part of the path (e.g. 'benchmarks')
            - file_path: the rest of the path (e.g. 'file.txt')
    param data: the data to write to the file

    """
    if config.get('isLocal'):
        _dir = os.path.dirname(path)
        Path(_dir).mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding=encoding) as f:
            f.write(data)
    else:
        container_name, file_path = path.split('/', 1)
        blob_account_name = get_secret('share-storage-account-name')
        blob_account_key = get_secret(
            'share-storage-account-secondary-access-key'
        )
        blob_uri = blobs_uri(blob_account_name)
        blob_service_client = BlobServiceClient(
            account_url=blob_uri,
            credential=blob_account_key
        )
        blob_client = blob_service_client.get_blob_client(
            container_name,
            file_path
        )
        blob_client.upload_blob(
            data,
            overwrite=True)


def read_file(path):
    """
    Reads a file from either local storage or Azure Blob Storage.
    param path: the path to the file (e.g. 'benchmarks/file.txt')
        - if the path is local, the file will be read from the local filesystem
        - if the path is remote, the blob will be downloaded from 
            - container: the first part of the path (e.g. 'benchmarks')
            - file_path: the rest of the path (e.g. 'file.txt')
    """
    if config.get('isLocal'):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        container_name, file_path = path.split('/', 1)
        blob_account_name = get_secret('share-storage-account-name')
        blob_account_key = get_secret(
            'share-storage-account-secondary-access-key')
        blob_uri = blobs_uri(blob_account_name)
        blob_service_client = BlobServiceClient(
            account_url=blob_uri, credential=blob_account_key)
        blob_client = blob_service_client.get_blob_client(
            container_name, file_path)
        try:
            return blob_client.download_blob().readall().decode('utf-8')
        except ResourceNotFoundError:
            print(f"Error downloading blob: {path}")
            raise


#                        /          ,e,   d8   ,e,
#  e88~~\  e88~-_  e88~88e 888-~88e  "  _d88__  "  Y88b    /  e88~~8e
# d888    d888   i 888 888 888  888 888  888   888  Y88b  /  d888  88b
# 8888    8888   | "88_88" 888  888 888  888   888   Y88b/   8888__888
# Y888    Y888   '  /      888  888 888  888   888    Y8/    Y888    ,
#  "88__/  "88_-~  Cb      888  888 888  "88_/ 888     Y      "88___/
#                   Y8""8D


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

#                           8
# d88b .d88b .d88 8d8b .d8b 8d8b.
# `Yb. 8.dP' 8  8 8P   8    8P Y8
# Y88P `Y88P `Y88 8    `Y8P 8   8


def search_kb(
    query,
    embeddings=None,
    index_name=search_index_name,
    api_version=search_api_version,
    product=None,
    tax_process=None,
    algorithm='HNSW-NVM',
    k=3
):
    """
    Uses the Azure Cognitive Search API to search for similar documents within
    the Vertex Knowledge Base based on a given query or embeddings.
    """
    if not embeddings and query:
        embeddings = get_embeddings(query)

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
    except Exception as exc:
        print("Error during fetch to Azure:\n")
        print(exc)
        raise Exception(
            'Error in `search` function calling Azure Cognitive Search API') from exc


# .d88b 888b. 8    8 888b.
# 8P    8  .8 8    8 8   8
# 8b    8wwK' 8b..d8 8   8
# `Y88P 8  Yb `Y88P' 888P'


def vector_search(
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
                "dimensions": len(get_embeddings("Test")),
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
        "vectorSearch": vector_search(
            efConstruction=efConstruction,
            efSearch=efSearch,
            m=m,
        ),
    }
    try:
        print(
            f"""Creating index {index_name} at url: {base_url} and body: \n {json.dumps(body, indent=2)}"""
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
        vector_search_dimensions=len(get_embeddings("Test")),
        # vector_search_configuration=ALGO_CONFIG_NAME,
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
        filterable=True,
        normalizer="lowercase",
    ),
    SimpleField(
        name="tax_process",
        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
        filterable=True,
        normalizer="lowercase",
    ),
    SimpleField(
        name="modified_time",
        type=SearchFieldDataType.DateTimeOffset,
        filterable=True,
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


#  e88~~\  e88~-_   d88~\ 888-~88e-~88e  e88~-_   d88~\
# d888    d888   i C888   888  888  888 d888   i C888
# 8888    8888   |  Y88b  888  888  888 8888   |  Y88b
# Y888    Y888   '   888D 888  888  888 Y888   '   888D
#  "88__/  "88_-~  \_88P  888  888  888  "88_-~  \_88P

# REST DOCS: https://learn.microsoft.com/en-us/rest/api/cosmos-db/
# OTHER DOCS: https://learn.microsoft.com/en-us/azure/cosmos-db/

# COSMOS_DB = os.getenv("COSMOS_DB_BASE")
# COSMOS_URI = f"https://{COSMOS_DB}.documents.azure.com"
# ACCOUNT_KEY = os.environ["COSMOS_DB_KEY"]

# cosmos_client = CosmosClient(COSMOS_URI, credential=ACCOUNT_KEY)

# create a new database in cosmos db


# def cdb_create(database_id):
#    """
#    creates a new database in cosmos db
#    https://azuresdkdocs.blob.core.windows.net/$web/python/azure-cosmos/4.0.0/azure.cosmos.html#azure.cosmos.CosmosClient
#    """
#    database = cosmos_client.create_database_if_not_exists(id=database_id)
#    return [*database]


# def cdb_create_container(database_id, container_id, partition_key):
#    """
#    creates a new container in cosmos db
#    """
#    database = cosmos_client.get_database_client(database_id)
#    container = database.create_container_if_not_exists(
#        id=container_id, partition_key=PartitionKey(path=partition_key)
#    )
#    return container


# def cdb_create_kv_item(database_id, container_id, item):
#    """
#    creates a new key-value item in cosmos db
#    """
#    database = cosmos_client.get_database_client(database_id)
#    container = database.get_container_client(container_id)
#    container.create_item(body=item)
#    return item


# def cdb_list_dbs():
#    """
#    lists all databases in cosmos db
#    """
#    databases = cosmos_client.list_databases()
#    # convert the iterator to a list
#    return [*databases]

# create a mongodb-compliant database in cosmos db
# def cdb_create_mongo_database(database_id):

# create a mongodb client


# def cdb_create_mongo_db():
#    """
#    creates a new mongo db client
#    """
#    usr = quote(env["MONGO_USER"])
#    pwd = quote(env["MONGO_PASS"])
#    host = env["MONGO_HOST"]
#    db = env["MONGO_DB"]
#    qualifier = "tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
#    mongo_conn = f"mongodb+srv://{usr}:{pwd}@{host}/{db}?{qualifier}"
#    client = MongoClient(mongo_conn)


# def cdb_upsert_item(database_id, container_id, item):
#    """
#    upserts an item into a container in cosmos db
#    """
#    database = cosmos_client.get_database_client(database_id)
#    container = database.get_container_client(container_id)
#    container.upsert_item(item)
#    return item
