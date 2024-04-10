import asyncio
import sys
import os
import json
import zipfile
import re
import datetime
import time
import urllib
import pickle

from datetime import datetime
from dotenv import load_dotenv, dotenv_values
from glom import glom

from gremlin_python.driver import client, serializer
from .artifactory_fns import (
    ArtifactoryPath,
    get_artifactory_metadata,
    get_publication_metadata,
    extract_xml_from_zip
)

from .regex_fns import (
    get_md_links,
    strip_md_links,
    generate_links,
    related_rx,
    no_special_chars
)
from .soup_fns import (
    html2md_clean,
    html2md
)
from .keyvault import get_secret
from .azure_fns import (
    write_file,
    read_file,
    spawn_plan,
    exec_gremlin
)
from .markdown_fns import chunk_markdown
from .utils import RELATIVE_PATH

load_dotenv(dotenv_path=f"{RELATIVE_PATH}.env")

cwd = os.getcwd()

config_path = os.path.join(cwd, f"{RELATIVE_PATH}constants.json")

with open(config_path) as f:
    config = json.load(f)
    publication_whitelist = config["artifactory_publication_whitelist"]

# """
# Pseudo
# NOTE: Make sure you are logged into the VPN in order to access Artifactory
# 1. Get the Artifactory paths from the vtxdev Artifactory URL

AF_BASE_URL = "https://binrepo.vtxdev.net/artifactory/"
AF_TARGET = "knowmgmt-gen-publish/publish-prod"
AF_URL = AF_BASE_URL + AF_TARGET + "/"

# artifactory_url: https://binrepo.vtxdev.net/artifactory/knowmgmt-gen-publish/publish-prod/
# artifactory_path: https://binrepo.vtxdev.net/artifactory/knowmgmt-gen-publish/publish-prod


def file_size(file):
    """
    Get the size of the file
    """
    return os.stat(file).st_size

# 2. For each path: digest the publication name, metadata (json file), xml file, and zip files
#     - the entire process is modulated per publication (i.e., iterate over files with the same function)


def xf_metadata(metadata: dict):
    """
    Transform the metadata
    """
    # regex that removes any strings wrapped in <>s
    bracket_rx = re.compile(r"<[^>]*?>")

    def split_concatenated(tags: list[str]):
        """
        some tags are incorrectly concatenated and need to be split by commas. this
        function takes all the tags, splits each of them by commas adds them to a
        set, and flattens into a list 

        example:
        ["Release Notes", "Featured, Product Documentation", "Featured"]
        ->
        ["Release Notes", "Featured", "Product Documentation"]
        """
        results = set()
        if isinstance(tags, list):
            for tag in tags:
                results.update([re.sub(bracket_rx, "", t.strip())
                               for t in tag.split(",")])
            return list([result for result in results if result != ""])
        elif isinstance(tags, str):
            results.update([re.sub(bracket_rx, "", t.strip())
                           for t in tags.split(",")])
            return list([result for result in results if result != ""])
        else:
            return tags

    def pascal_2_snake(name: str):
        """
        Convert PascalCase to snake_case
        """
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

    return {
        pascal_2_snake(k): split_concatenated(v) for k, v in metadata.items()
    }


def partition_related(md):
    """
    Uses regular expressions to see if the markdown contains (case-insensitive):
    - ## Related Articles
    - ## Related Topics
    and pulls out that section (until the end of the md or until the next heading)
    """
    related = related_rx.search(md)
    snipped = re.sub(related_rx, "", md)

    return {
        "related": related.group(1) if related else None,
        "snipped": snipped
    }


def digest_article(md, publication, lang="enus"):
    """
    Takes the full markdown content of an article (containing links) and:
    - separates the related articles section (if it exists)
    - chunks the markdown content into smaller pieces
    - for each chunk, extracts the links
    - cleans out the links for downstream processes
    """
    # separate the related articles section
    parts = partition_related(md)
    snipped = parts["snipped"]
    related = parts["related"]

    # chunk the markdown content
    chunks = chunk_markdown(
        markdown_payload=snipped,
        # max_tokens=default_token_sequence_length,
        # min_tokens=50,
        # omit_headings=None,
        # table=None,
        # seps=None,
        # step=0,
        debug=False,
    )

    parsed_chunks = []

    for chunk in chunks:
        links = get_md_links(chunk["md"])
        clean_chunk = strip_md_links(chunk["md"])
        chunk["md"] = clean_chunk
        parsed_chunks.append({
            **chunk,
            "links": generate_links(links=links, publication=publication, lang=lang) or []
        })

    article_links = get_md_links(related) if related else []

    return {
        "links": generate_links(
            links=article_links,
            publication=publication,
            lang=lang
        ) if related else [],
        "chunks": parsed_chunks,
    }


lang_dict = {
    "en": "enus",
}


def infuse_metadata(chunks, metadata):
    """
    Infuse metadata into the chunks
    """
    for chunk in chunks:
        chunk.update(metadata)
    return chunks


def extract_zip(
    path,
    directory,
    kv_state,
    lang="en",
):
    """
    Download the zip file from the Artifactory path, extract relevant files and
    metadata, and construct the graph

    TODO:

    - [ ] Generalize the link builder to enable links to arbitrary web pages
      instead of just the community
    """
    pub_name = path.stem
    filename = os.path.join(directory, pub_name)
    zip_filename = filename + ".zip"
    artf_meta = get_artifactory_metadata(path)

    if artf_meta["size"] < 10000:
        print(
            f"Skipping {pub_name} due to small size: {artf_meta['size']} bytes")
        return

    with path.open() as infile, open(zip_filename, "wb") as outfile:
        outfile.write(infile.read())

    zip_file = zipfile.ZipFile(zip_filename)
    xml = extract_xml_from_zip(zip_file)
    pub_meta = get_publication_metadata(xml)
    pub_meta["publication_name"] = pub_name
    pub_meta.update(artf_meta)
    pub_meta = xf_metadata(pub_meta)

    zip_file_contents = zip_file.namelist()

    # check if the publication size has changed
    if pub_name in kv_state:
        if kv_state[pub_name]["size"] == pub_meta["size"]:
            print(f"✅✅ Skipping publication {pub_name} due to unchanged size")
            return
        else:
            # update the size store and continue
            kv_state[pub_name] = pub_meta
    else:
        # add the publication to the size store
        kv_state[pub_name] = pub_meta

    publication = pub_name.split("/")[0]

    gremlin_vertices = set()
    gremlin_edges = set()

    content_path = "Vertex/content/" + lang + "/"
    # handle zip files with content in the /content/en/ directory
    for file in zip_file_contents:
        if content_path in file and (file.endswith(".json") or file.endswith(".html")):
            zip_file.extract(file, directory)
            print(f"Extracted {file} to {directory}")
            # print(f"🍖 Metadata: {json.dumps(pub_meta, indent=2)} 🍖")
            # only one per publication
            if file.endswith("metadata.json"):
                json_file = os.path.join(directory, file)
                with open(json_file) as pojo:
                    data = json.load(pojo)["values"]
                    size = file_size(json_file)
                    meta = xf_metadata(data)
                    kv_state[pub_name].update(meta)
            elif file.endswith(".html"):
                html_file = os.path.join(directory, file)
                with open(html_file) as html:
                    size = file_size(html_file)
                    print(f"Size of html {file}: {size} bytes")
                    topic_path = file.split(".")[-2]
                    # -> Vertex/content/<lang>/<topic>
                    topic = ":".join(topic_path.split("/")[-2:])
                    # -> <lang>:<topic>
                    key = f"{pub_name}:{topic}"
                    print(f"Key: {key}")
                    if key in kv_state:
                        if kv_state[key]["size"] == size:
                            print(
                                f"✅ Skipping topic {key} due to unchanged size")
                            continue
                        else:
                            kv_state[key] = {"size": size}
                    else:
                        kv_state[key] = {"size": size}
                    # pretty print the html data
                    data = html.read()
                    md = html2md(data)
                    # TODO: Chunking
                    digest = digest_article(
                        md, publication, lang=lang_dict[lang])
                    # print(f"\n📄 Markdown digest for {publication} 📄")
                    # print(f"📄 {json.dumps(digest, indent=2)} 📄")
                    plan = spawn_plan(
                        from_id=key,
                        digest=digest,
                        metadata=pub_meta,
                        lang='en'
                    )
                    # print(f"Plan for {key}:\n")
                    gremlin_vertices = gremlin_vertices.union(
                        plan["gremlin"]["vertices"])
                    gremlin_edges = gremlin_edges.union(
                        plan["gremlin"]["edges"])
                    # print("\n" + json.dumps(digest, indent=2))
                    # TODO: Graph Construction + other storage
            # delete the extracted file
            os.remove(os.path.join(directory, file))

        # print the gremlins
    print("GREMLINS:\n")
    # number
    # print(f"Vertices: {len(gremlin_vertices)}")
    # print(f"Edges: {len(gremlin_edges)}")
    # execute the gremlins
    return {
        "gremlin": {"vertices": gremlin_vertices, "edges": gremlin_edges},
    }


kv_store = json.loads(read_file("benchmarks/kv.json"))


def download_af_files(
    index_name: str,
    download_dir: str = "downloads",
    lang: str = "en",
    targeted_products: bool | list[str] = False,
    kv: dict = kv_store
):
    """
    Download files from the Artifactory URL
    """
    directory = os.path.join(download_dir, index_name)
    if not os.path.exists(directory):
        os.makedirs(directory)
    payload = []
    gremlin_vertices = set()
    gremlin_edges = set()
    execution_count = 0
    af_path = ArtifactoryPath(AF_URL)
    for path in af_path:
        # path: https://binrepo.vtxdev.net/artifactory/knowmgmt-gen-publish/publish-prod/IrisProductGuide.zip
        if path.stem.lower() not in [x.lower() for x in publication_whitelist]:
            print(f"⬛ Skipping non-whitelisted publication: {path.stem}")
            # Skipping non-whitelisted publication: IrisProductGuide
            continue
        if targeted_products and len(targeted_products) and path.stem.lower() in [x.lower() for x in targeted_products]:
            print(
                f"Downloading targeted (shortlist) {path.stem} to {directory}")
            print(f"full path: {path}")
            payload.append(extract_zip(
                path, directory, kv_state=kv, lang=lang))
        elif not targeted_products:
            print(f"Downloading {path.stem} to {directory}")
            payload.append(extract_zip(
                path, directory, kv_state=kv, lang=lang))

    for plan in payload:
        try:
            gremlin_vertices = gremlin_vertices.union(
                plan["gremlin"]["vertices"] or set())
            gremlin_edges = gremlin_edges.union(
                plan["gremlin"]["edges"] or set())
        except TypeError:
            # print(f"🔥 PROBLEM PARSING PLAN:\n {plan}")
            # Plan can end up being [] instead (FIXME)
            continue

    # create nodes first
    for gremlin in gremlin_vertices:
        execution_count += 1
        print(f"\n🔴 Creating Vertex:\n{gremlin}")
        exec_gremlin(gremlin)

    # create edges
    for gremlin in gremlin_edges:
        execution_count += 1
        print(f"\n🔗 Creating Edge:\n{gremlin}")
        exec_gremlin(gremlin)

    total_queries = len(gremlin_vertices.union(gremlin_edges))
    print(f"🧧 DONE: {execution_count} of {total_queries} queries 🧧")

    new_kvs = json.dumps(kv, indent=2)
    write_file("benchmarks/kv.json", new_kvs)
    new_kvs_size = sys.getsizeof(new_kvs)
    print(f"📄📄📄 Updated size store ({new_kvs_size} bytes) 📄📄📄")


"""
TODO:
- improve graph topology
  - product
  - publication
  - topic (article)
  - author
  - chunk (section)
  - chunk type (categories)
    - 
"""
