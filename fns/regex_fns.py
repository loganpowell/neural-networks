import re

# more than one whitespace or a newline
whitespace_regex = re.compile(r"\s+?")
numbered_rx = re.compile(r"\s\d{1,3}\.\s")
# matches a numbered list item without any indentation followed by a double newline
numbered_nn_rx = re.compile(r"^\d{1,3}\.\s[^\n]+?\n\n", re.MULTILINE)
# regex that matches the start of a double newline above a table
above_table_rx = re.compile(r"(?=\n\n\|)")
# matches a complete markdown table
md_table_rx = re.compile(r"(([^\n]+?\|\n?)+(|$))")
count_tables = re.compile(r"\n\n\|", re.MULTILINE)
md_tokens_rx = re.compile(r"\\n|\n|#")


def trim_hash(s):
    return re.sub(r"^#{1,6}\s", "", s)


def has_table(md):
    """
    returns True if markdown has a table
    """
    return md_table_rx.search(md) is not None


first_line_rx = re.compile(r"^\s{0,5}(.+?)\n", re.MULTILINE)


def get_candidate_heading(md):
    """
    returns the first line in markdown
    """
    line = first_line_rx.search(md)
    if line:
        return trim_hash(line.group(1)).strip()
    else:
        print("No Candidate Heading Found")
        return None


# matches only the first heading (# or ##) in markdown
first_heading_rx = re.compile(r"^(#+?)\s(.+?)\n", re.MULTILINE)


def get_title(md):
    """
    returns the first heading in markdown
    """
    heading = first_heading_rx.search(md)
    if heading:
        return trim_hash(heading.group(2)).strip()
    else:
        print(f"🔥🔥🔥 heading: {heading}")
        print(
            f"🔥🔥🔥 (`get_first_heading`) No Heading Found in:\n```md\n{md[:100]}..\n```")
        print(f'🔥🔥🔥 using `get_candidate_heading` instead...')
        return get_candidate_heading(md) or "No Heading Found"


def grab_first_table_and_above(md):
    """
    finds the first table in the markdown and returns it along with 
    everything before it
    """
    first_table = md_table_rx.search(md)
    if first_table:
        table = first_table.group(0)
        first_table_and_above = md[:md.find(table) + len(table)]
        return first_table_and_above
    else:
        return None


def get_md_links(md):
    """
    returns a list of markdown links in a string

    example:
    ```json
    {
        "Link One": "/csh?topicname=191623.html&pubname=PubOne",
        "Link Two": "#showid/191623",
        "Link Three": "https://community.vertexinc.com/csh?topicname=191623.html&pubname=PubThree"
    }
    ```
    """
    links = re.findall(r"\[.*?\]\(.*?\)", md)
    # get the text and href from each link as a list of tuples
    return {
        re.search(r"\[(.*?)\]", link).group(1): re.search(r"\((.*?)\)", link).group(1)
        for link in links
    }


def strip_md_links(md):
    """
    replaces markdown links with their text
    """
    links = re.findall(r"\[.*?\]\(.*?\)", md)
    for link in links:
        md = md.replace(link, re.search(r"\[(.*?)\]", link).group(1))

    return md


related_rx = re.compile(
    r"(#\sRelated\s(?:Articles|Topics)(.*?)(?=\Z))", re.I | re.S)


def generate_links(
    links,
    publication=None,
    lang="enus"
):
    """
    takes the output of get_md_links and compiles them into functioning links
    input link formats:
    - inter-publication links
        - /csh?topicname=111111.html&pubname=SomePublication
        - /csh?topicname=SomeTopic.html&pubname=SomePublication
    - intra-publication links
        - #showid/111111
        - #showid/SomeTopic
    - conventional links (vertex)
        - https://www.vertexinc.com/vertex-community
        - https://community.vertexinc.com/s/document-item?bundleId=OSeriesSupportPolicy&topicId=201379.html&_LANG=enus

    example links payload:
    ```json
    {
        "Link One": "/csh?topicname=191623.html&pubname=PubOne",
        "Link Two": "#showid/191623",
        "Link Three": "https://community.vertexinc.com/csh?topicname=191623.html&pubname=PubThree"
    }
    ```
    example output payload:
    ```json
    [
        { 
            "text": "Link One",
            "href": "https://community.vertexinc.com/s/document-item?bundleId=PubOne&topicId=191623.html&_LANG=enus",
            "topic": "191623",
            "publication": "PubOne"
        },
        { 
            "text": "Link Two",
            "href": "https://community.vertexinc.com/s/document-item?bundleId=<publication>&topicId=191623.html&_LANG=enus",
            "topic": "191623",
            "publication": <publication>
        },
        { 
            "text": "Link Three",
            "href": "https://community.vertexinc.com/s/document-item?bundleId=PubThree&topicId=191623.html&_LANG=enus",
            "topic": "191623",
            "publication": "PubThree"
        }
    ]
    ```
    """
    # grab topic id/name from any of the above formats
    # - can be topicname= | showid/ | topicId=
    #   - at the end of a string or followed by a .html
    topic_rx = re.compile(r"(topicname=|showid\/|topicId=)(.*?(?=(\.|$)))")
    pub_rx = re.compile(r"(pubname=|bundleId=)(.*?(?=(\.|$|&)))")

    results = []
    for text, raw in links.items():
        topic = topic_rx.search(raw)
        pub = pub_rx.search(raw)
        if not pub and publication:
            pub = publication
        else:
            pub = pub.group(2)
        if not topic:
            print(f"🔥🔥🔥 topic not found for: {raw}")
            topic = None
        else:
            topic = topic.group(2)
        results.append({
            "raw": raw,
            "text": text,
            "topic": topic if topic else None,  # TODO: use as trigger for link generation
            "publication": pub,
            "href": f"https://community.vertexinc.com/s/document-item?bundleId={pub}&topicId={topic}.html&_LANG={lang}" if topic else raw
        })

    return results


def no_special_chars(md):
    """
    removes all special characters and newlines from a string
    """
    before_escaped = re.sub(r"\W+", " ", md)
    # escape quotes (single and double) and backticks
    after_escaped = re.sub(r"['\"`]", r"\\\g<0>", before_escaped)
    return after_escaped


#   d88~\  e88~~8e  888-~88e   d88~\
#  C888   d888  88b 888  888b C888
#   Y88b  8888__888 888  8888  Y88b
#    888D Y888    , 888  888P   888D
#  \_88P   "88___/  888-_88"  \_88P
#                   888

# matches double newlines above markdown headings:
nn_h1 = re.compile(r"\n\n(?=#)")
nn_h2 = re.compile(r"\n\n(?=##)")
nn_h3 = re.compile(r"\n\n(?=###)")
# matches double newlines above unmarked headings (non-whitespace strings)
nn_continuous_str_nn = re.compile(r"\n\n(?=\S+?\n)")
# match a triple newline with any trailing whitespace on each newline
n_n_n_ = re.compile(r"\n\s*?\n\s*?\n\s*?")
# matches double newlines above a line with no punctuation followed by a double newline
nn_no_punctuation_nn = re.compile(r"\n\n(?=[^.,:;!?*]+?\n\n)")
