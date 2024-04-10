import json
from glom import glom
from .openai_fns import (
    get_embeddings,
    messages_prompt
)
from .regex_fns import (
    generate_links,
    no_special_chars
)
from .azure_fns import (
    search_kb,
    graph_get_connected,
    graph_get_in_common,
    graph_get_chunk_by_parent,
    graph_get_most_connected,
    graph_xf_props,
    graph_xf_compress,
    sort_by_key
)

# function that takes a query, grabs the top 3 results from search_kb, maps over those results and uses the community_url from the metadata of each result to get the connected nodes from the graph and uses these as context for the messages_prompt


def omit(d, keys):
    return {k: v for k, v in d.items() if k not in keys}


def pluck(d, keys):
    return {k: v for k, v in d.items() if k in keys}


def xf_related(payload: list[dict], spec: str = "0.*.value.*.key"):
    """
    Transforms the output of get_community into a format that can be used by messages_prompt
    """
    xfd = graph_xf_props(payload, spec)
    try:
        return sort_by_key(xfd, "order")
    except KeyError:
        # print(f"KeyError: {e}")
        return xfd


def get_community(query, lang="en"):
    results = search_kb(query)
    kb_payload = results["value"]
    buffer = []
    related = []
    cleaned = []
    for item in kb_payload:
        payload = pluck(item, ["metadata", "title",
                        "content", "product", "heading", "@search.score"])
        metadata = json.loads(payload["metadata"])
        url = metadata["community_url"]
        cleaned.append({
            "url": url,
            **omit(payload, ["metadata"]),
        })
        modified_by = metadata["modified_by"]
        created_by = metadata["created_by"]
        title = payload["title"]
        content = payload["content"].strip()
        product = payload["product"]
        search_score = payload["@search.score"]
        heading = no_special_chars(payload["heading"])
        link = {
            heading: url
        }
        deconstructed_link = generate_links(link)[0]

        topic, publication, __ = (lambda topic, publication, **rest: (
            topic, publication, rest))(**deconstructed_link)

        node_id = f'{publication}:{lang}:{topic}'

        chunk_node = xf_related(graph_get_chunk_by_parent(
            node_id,
            heading
        ))

        page_chunks = xf_related(graph_get_connected(
            node_id,
            "parent"
        ))

        chunk_id = glom(chunk_node, "0.id", default=None)
        print(f"node_id: {node_id}")
        print(f"url: {url}")
        print(f"heading: {heading}")
        related_articles = []
        if node_id:
            related_articles = xf_related(graph_get_connected(
                node_id,
                "related"
            ))
        chunk_links = []
        if chunk_id:
            buffer.append(chunk_id)
            chunk_links = xf_related(graph_get_connected(
                chunk_id,
                "related"
            ))
        related.append({
            "url": url,
            "node_id": node_id,
            "heading": heading,
            "title": title,
            "modified_by": modified_by,
            "created_by": created_by,
            "chunk_id": chunk_id,
            "chunk_links": chunk_links,
            "related_articles": related_articles,
            "page_chunks": page_chunks,
        })
    # get the first two node ids from the related payload

    def get_specific_if_possible(x):
        # return glom(x, "*.0.id", default=None)
        return x["node_id"]

    mutual_raw = graph_get_in_common(
        buffer,
    )

    mutuals = mutual_raw  # xf_related(mutual_raw, spec=None)

    def filter_pubs(mutuals: list[dict]):
        """
        takes a payload like this:
        ```json
        [{ "Pub": 4, "Pub:en:123": 1, "Pub:en:456": 1 }]
        ```
        and returns a list where keys contain at least two : characters:
        ```json
        [{ "Pub:en:123": 1, "Pub:en:456": 1 }]
        ```
        """
        return [
            {k: v for k, v in x.items() if k.count(":") > 1}
            for x in mutuals
        ]

    inbound_links = graph_get_most_connected(buffer, "in", pop=False)

    # important = xf_related(important, spec=None)[
    #     0]["id"] if important else None

    # for mutual in mutuals:
    #     node_id = mutual["id"]
    #     siblings = graph_get_connected(node_id, "parent")
    #     mutual["siblings"] = xf_related(siblings)

    kb = [omit(x, ["metadata", "id"]) for x in cleaned]

    return {
        "inbound_links": inbound_links,
        "mutuals": mutuals[0],  # graph_xf_compress(mutuals[0])
        "kb_results": kb,
        "graph_results": related,
    }

# TODO:
# - siblings functionality can be used to grab arbitrarily chunked nodes (flexible)
# - mutuals doesn't always avail results -> consider looking further than direct connections
# OSClientUtilities:en:189591
