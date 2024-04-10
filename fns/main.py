"""os module"""
import json
import os
import zipfile
import shutil

from datetime import datetime

from langchain.docstore.document import Document
from langchain.vectorstores.azuresearch import AzureSearch

from .artifactory_fns import (
    ArtifactoryPath,
    artifactory_base_url,
    content_prefix,
    downloads_dir,
    extract_xml_from_zip,
    get_artifactory_metadata,
    get_publication_metadata,
    publication_whitelist,
)

from .azure_fns import (
    VECTOR_STORE_API_KEY,
    VECTOR_STORE_URL,
    # VECTOR_IDX_NAME,
    # SEARCH_API_VERSION,
    create_index,
    delete_index,
    fields,
    vector_search,
)
from .markdown_fns import chunk_markdown, clean_w_md_tables
from .openai_fns import default_token_sequence_length, embedding_function
from .soup_fns import html2md_clean
from .utils import RELATIVE_PATH

# load constants.json from the root directory as a dictionary
with open(f"{RELATIVE_PATH}constants.json") as f:
    config = json.load(f)
    search_api_version = config["search_api_version"]
    search_index_name = config["search_index_name"]

headings_to_omit = ["related articles", "What's new in Tax Rules..."]


def vectorize_metadata_field(chunk, field, omit="", sep=","):
    """
    Split a metadata field into a list of values
    """
    target = chunk[field]
    targets = (
        [x.strip() for x in target.split(sep) if omit not in x] if target else None
    )
    chunk[field] = targets if target else ["NA"]


def xf_metadata(chunk):
    """
    Transform the metadata in a chunk
    """
    # print("chunk:", json.dumps(chunk, indent=4))
    time = chunk["modified_time"]
    # Azure date format
    day = datetime.fromisoformat(time).strftime("%Y-%m-%d")
    chunk["modified_time"] = day
    vectorize_metadata_field(chunk, "product", omit="<Select a product>")
    vectorize_metadata_field(chunk, "tax_process",
                             omit="<Select a tax process>")
    heading = chunk["heading"]
    md = chunk["md"]
    if heading not in md:
        md = f"{heading}\n\n{md}"
    chunk["md"] = md
    return chunk


def xf_chunk(chunk, topic_metadata):
    """
    Transform a chunk
    """
    chunk = xf_metadata({**chunk, **topic_metadata})
    # 🔥 SUPER HANDY SYNTAX 🔥
    md, rest = (lambda md, **rest: (md, rest))(**chunk)
    return Document(page_content=clean_w_md_tables(md), metadata={**rest})


def process_page(
    publication_metadata,
    topic_id,
    html_content,
    max_tokens=default_token_sequence_length,
    min_tokens=30,
    omit_headings=None,
    debug=True,
):
    """
    Read a topic from the zip file and split it into chunks
    """
    if not omit_headings:
        omit_headings = headings_to_omit

    metadata = publication_metadata.copy()

    topic_product = metadata["topic_products"].get(topic_id)

    if topic_product:
        metadata["product"] = topic_product

    markdown = html2md_clean(html_content)
    partitions = chunk_markdown(
        markdown,
        max_tokens=max_tokens,
        min_tokens=min_tokens,
        omit_headings=omit_headings,
        debug=debug,
    )

    topic_metadata = {
        "topic_id": topic_id,
        "community_url": f"https://community.vertexinc.com/s/document-item?bundleId={metadata['publication_name']}&topicId={topic_id}.html&_LANG=enus",
        **metadata,
    }

    return list(map(lambda x: xf_chunk(x, topic_metadata), partitions))


def process_publication(
    zip_file,
    publication_metadata,
    prefix=content_prefix,
    max_tokens=default_token_sequence_length,
    min_tokens=30,
    omit_headings=None,
    debug=True,
):
    """
    Read all the topics in a publication and split them into chunks
    """
    if not omit_headings:
        omit_headings = headings_to_omit
    chunks = []
    topics = 0
    for file_info in zip_file.infolist():
        # We only care about files in the content directory that are HTML
        if file_info.filename.startswith(prefix) and file_info.filename.endswith(
            ".html"
        ):
            # The topic id is the part between the last / and the .html
            topic_id = file_info.filename.split("/")[-1].split(".")[0]
            html_content = zip_file.read(file_info).decode("utf-8")
            split_sections = process_page(
                publication_metadata,
                topic_id,
                html_content,
                max_tokens=max_tokens,
                min_tokens=min_tokens,
                omit_headings=omit_headings,
                debug=debug,
            )
            # Add the chunks to the list of all sections
            chunks.extend(split_sections)
            topics += 1

    print(f"...Found {topics} topics:")

    return chunks, topics


def check_exists(file_path, art_path, art_meta):
    """
    Check if we already have this version of the publication
    """
    if os.path.exists(file_path):
        with open(file_path) as infile:
            previous_metadata = json.load(infile)
        if previous_metadata["sha256"] == art_meta["sha256"]:
            print(f"Hashes match, skipping {art_path.name}")
            return


#   d8                      d8
# _d88__  e88~~8e   d88~\ _d88__
#  888   d888  88b C888    888
#  888   8888__888  Y88b   888
#  888   Y888    ,   888D  888
#  "88_/  "88___/  \_88P   "88_/


def test_product_payload(path="2023-12-29/COSMyEnterprise"):
    """
    Test the process_publication function
    """
    cwd = os.getcwd()
    path = os.path.join(cwd, "downloads", path)
    print("path:", path)
    # get current time yyyy-mm-dd
    cur_time = datetime.now().strftime("%Y-%m-%d")

    pub_name = path.split("/")[-1]

    # If we already have this version, skip it
    # check_exists(json_filename, path, art_meta)

    zip_file = zipfile.ZipFile(path + ".zip")
    xml = extract_xml_from_zip(zip_file)

    pub_meta = get_publication_metadata(xml)
    pub_meta["publication_name"] = pub_name
    pub_meta.update(
        {
            "created_time": cur_time,
            "modified_time": cur_time,
            "created_by": "logan",
            "modified_by": "logan",
            "mime_type": "application/zip",
            "size": 10000,
            "sha1": "sha1",
            "sha256": "sha256",
            "md5": "md5",
            "is_dir": False,
            "children": False,
            "repo": False,
        }
    )
    chunks, topics = process_publication(
        zip_file=zip_file,
        publication_metadata=pub_meta,
        debug=False,
    )
    print(f"Found {len(chunks)} chunks ({topics} topics)")
    print("all chunks:", chunks)


# test_product_payload()


def download_publication(
    download_subdir,
    vector_store,
    path,
    max_tokens=default_token_sequence_length,
    min_tokens=30,
    omit_headings=None,
    debug=True,
    skip=False,
):
    """
    Download a publication and read its metadata
    """
    if not omit_headings:
        omit_headings = headings_to_omit

    art_meta = get_artifactory_metadata(path)
    pub_name = path.stem
    zip_filename = os.path.join(download_subdir, f"{pub_name}.zip")
    json_filename = os.path.join(download_subdir, f"{pub_name}.json")
    xml_filename = os.path.join(download_subdir, f"{pub_name}.xml")

    # If we already have this version, skip it
    # check_exists(json_filename, path, art_meta)

    if art_meta["size"] < 10000:
        print(f"File too small, was {art_meta['size']}, skipping {path.name}")
        return

    print(f"Downloading {path.name} to {zip_filename}")
    with path.open() as infile, open(zip_filename, "wb") as outfile:
        outfile.write(infile.read())

    zip_file = zipfile.ZipFile(zip_filename)
    xml = extract_xml_from_zip(zip_file)

    with open(xml_filename, "w") as xmlfile:
        xmlfile.write(xml)

    pub_meta = get_publication_metadata(xml)
    pub_meta["publication_name"] = pub_name
    pub_meta.update(art_meta)

    print("product:", pub_meta["product"])
    if pub_meta["product"] is None:
        print(f"⚠ Warning: {pub_name} has no product ⚠")
    # if pub_meta["product"] and "O Series Cloud" not in pub_meta["product"]:
    #    print(f"skipping non O Series Cloud product: {pub_meta['product']}")
    #    return []

    chunks, topics = process_publication(
        zip_file,
        pub_meta,
        max_tokens=max_tokens,
        min_tokens=min_tokens,
        omit_headings=omit_headings,
        debug=debug,
    )

    chunk_count = len(chunks)
    pub_meta["topic_count"] = topics
    pub_meta["document_count"] = chunk_count

    if not skip:
        print(f"...🌩 Adding {chunk_count} chunks ({topics} topics) to index 🌩")
        ids = vector_store.add_documents(chunks)
        print(f"   🌩 Added {len(ids)} chunks to vector store 🌩")

    with open(json_filename, "w") as outfile:
        json.dump(pub_meta, outfile, indent=4)

    return chunks


def process_environment(
    index_name=search_index_name,
    api_version=search_api_version,
    ef_construction=400,
    ef_search=500,
    m=4,
    max_tokens=default_token_sequence_length,
    min_tokens=30,
    omit_headings=None,
    debug=True,
):
    """
    Process all the publications in an Artifactory environment
    """
    if not omit_headings:
        omit_headings = headings_to_omit

    print(f"Processing {index_name}...")
    download_subdir = os.path.join(downloads_dir, index_name)

    # empty the download directory between executions to ensure we only have the desired files
    if os.path.exists(download_subdir):
        shutil.rmtree(download_subdir)

    artifactory_url = f"{artifactory_base_url}/knowmgmt-gen-publish/publish-prod/"
    print("artifactory_url:", artifactory_url)
    # wsl_dummy = pathlib.Path(artifactory_url)
    artifactory_path = ArtifactoryPath(artifactory_url)
    print("artifactory_path:", artifactory_path)

    try:
        print(f"Deleting index {index_name}")
        response = delete_index(index_name=index_name, api_version=api_version)
        print("Deletion response:", response)
    except Exception as e:
        print("Deletion failed:", e)

    # while response.status_code == 403:
    #    print(f"Waiting for index {index_name} to be deleted...")
    #    time.sleep(5)
    #    response = delete_index(index_name=index_name)

    print(
        f"Recreating and populating index {index_name}, api_version: {api_version}")

    create_index(
        index_name=index_name,
        api_version=api_version,
        efConstruction=ef_construction,
        efSearch=ef_search,
        m=m,
    )
    # time.sleep(5)
    vector_store = AzureSearch(
        azure_search_endpoint=VECTOR_STORE_URL,
        azure_search_key=VECTOR_STORE_API_KEY,
        index_name=index_name,
        embedding_function=embedding_function,
        # fields are required upon upsertion of documents
        fields=fields,
        vector_search=vector_search(
            api_version=api_version,
            efConstruction=ef_construction,
            efSearch=ef_search,
            m=m,
        ),
        # scoring_profiles=[sc_profile],
        # default_scoring_profile=sc_name,
    )

    if not os.path.exists(download_subdir):
        os.makedirs(download_subdir)

    for path in artifactory_path:
        if path.stem.lower() not in [x.lower() for x in publication_whitelist]:
            print(f"Skipping publication: {path.stem}")
            continue
        print("path:", path)
        download_publication(
            download_subdir,
            vector_store,
            path,
            max_tokens=max_tokens,
            min_tokens=min_tokens,
            omit_headings=omit_headings,
            debug=debug,
        )

    print(f"\n\n\n=============== FINISHED {index_name} ===============")

    # return success for lambda handler
    return {"statusCode": 200, "body": "success"}
