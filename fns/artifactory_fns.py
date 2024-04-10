import xml.etree.ElementTree as etree
import json
import xmltodict
import os
from artifactory import ArtifactoryPath
from .utils import RELATIVE_PATH

artifactory_base_url = "https://binrepo.vtxdev.net/artifactory"
# Repository where the publication zips are stored
repository = "knowmgmt-gen-publish"
# Inside the zips, all the content is in this directory
content_prefix = "Vertex/content/en/"
# Path to keep local copy of documents
downloads_dir = "downloads"

# present / current working dir python

cwd = os.getcwd()
config_path = os.path.join(cwd, f"{RELATIVE_PATH}constants.json")

with open(config_path) as f:
    config = json.load(f)
    publication_whitelist = config["artifactory_publication_whitelist"]


def get_artifactory_metadata(path):
    """
    Get the metadata for a path from artifactory
    """
    stat = path.stat()
    artifactory_metadata = {
        "created_time": stat.ctime.isoformat(),
        "modified_time": stat.mtime.isoformat(),
        "created_by": stat.created_by,
        "modified_by": stat.modified_by,
        "mime_type": stat.mime_type,
        "size": stat.size,
        "sha1": stat.sha1,
        "sha256": stat.sha256,
        "md5": stat.md5,
        "is_dir": stat.is_dir,
        "children": stat.children,
        "repo": stat.repo,
    }
    return artifactory_metadata


def find_variable(root, variable_name):
    """
    Look up the value of a variable in the publication XML
    conditional product mapping algo:
        - if topic has variable with name products - use topic products
        - else use book products
    """
    xml_path = (
        ".//{http://www.authorit.com/xml/authorit}Book/{http://www.authorit.com/xml/authorit}VariableAssignments/{http://www.authorit.com/xml/authorit}VariableAssignment[{http://www.authorit.com/xml/authorit}Name='"
        + variable_name
        + "']/{http://www.authorit.com/xml/authorit}Value"
    )

    # print("xml_path:", xml_path)
    results = root.findall(xml_path)

    if results:
        return results[0].text
    else:
        return None


def find_topic_products(root):
    """
    Return all the topic products
    """
    xml_path = ".//{http://www.authorit.com/xml/authorit}Topic"

    results = root.findall(xml_path)
    # convert restults to list of dicts
    # results = [xmltodict.parse(etree.tostring(result)) for result in results]
    # print(json.dumps(results, indent=4))
    if results:
        topic_product = {}
        for result in results:
            tree = xmltodict.parse(etree.tostring(result))
            # print(json.dumps(tree, indent=4))

            has_variable_assignments = tree["ns0:Topic"]["ns0:VariableAssignments"]
            if has_variable_assignments:
                topic_id = tree["ns0:Topic"]["ns0:Object"]["ns0:ID"]
                candidates = has_variable_assignments["ns0:VariableAssignment"]
                if isinstance(candidates, dict):
                    for key, value in candidates.items():
                        # print("candidate:", key, value)
                        if key == "ns0:Name" and value == "Product":
                            valid_products = candidates["ns0:Value"]
                            topic_product[topic_id] = valid_products
                            # print("topic:", topic_id, "products:", valid_products)
                            # print("")
                            # print("")

        return topic_product
    else:
        return None


def get_publication_metadata(xml):
    """
    Get the metadata for a document from its XML
    """
    root = etree.fromstring(xml)
    publication_metadata = {
        "content_type": find_variable(root, "ContentType"),
        "internal_content": find_variable(root, "InternalContent"),
        "product": find_variable(root, "Product"),
        "product_subcategory": find_variable(root, "ProductSubcategory"),
        "publication_name": None,
        "tax_process": find_variable(root, "TaxProcess"),
        "topic_products": find_topic_products(root),
    }
    return publication_metadata


def extract_xml_from_zip(zip_file):
    """
    Extract the main XML file from a zip file
    """
    for file_info in zip_file.infolist():
        if file_info.filename.endswith(".xml"):
            with zip_file.open(file_info) as xml_file:
                xml = xml_file.read().decode("utf-8")
                return xml
    raise ValueError(f"No XML file found in {zip_file.filename}")


# publication_path = os.path.join(cwd, "downloads/2023-12-29/COSMyEnterprise.xml")
# print(publication_path)
# with open(publication_path) as f:
#    products = find_topic_products(etree.fromstring(f.read()))
#    print(products)
