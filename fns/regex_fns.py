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
        print(f"🔥🔥🔥 (`get_first_heading`) No Heading Found in:\n```md\n{md[:100]}..\n```")
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