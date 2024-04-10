import re
from functools import reduce
from .openai_fns import (
    default_token_sequence_length,
    count_tokens,
    summarize
)
from .regex_fns import (
    get_title,
    get_candidate_heading,
    has_table,
    above_table_rx,
    md_table_rx,
    md_tokens_rx,
    grab_first_table_and_above,
    count_tables,
    nn_h1,
    nn_h2,
    nn_h3,
    nn_continuous_str_nn,
    n_n_n_,
    nn_no_punctuation_nn,
    get_md_links,
    strip_md_links,
)


def in_omissions(heading, omissions, debug=True):
    """
    inputs:
        - heading: a string
        - omissions: a list of strings

    outputs: 
        - match (bool): True if heading is in omissions. 

    Matches are case-insensitive. 

    Match Syntax:
        - "this"      : matches any heading that is exactly "this"
        - "this..."   : matches any heading that starts with "this"
        - "...this"   : matches any heading that ends with "this"
        - "...this...": matches any heading that contains "this"
    """
    omit = False
    for o in omissions:
        o = o.lower().strip()
        h = heading.lower().strip()
        # if string has ... at the end or the beginning, match substring
        # match substring
        parts = o.split("...")
        if len(parts) == 1:
            omit = omit or o == h
        elif len(parts) == 2:
            if parts[0] == "":
                omit = omit or h.endswith(parts[1])
            elif parts[1] == "":
                omit = omit or h.startswith(parts[0])
        elif len(parts) == 3:
            omit = omit or parts[1] in h

    if omit and debug:
        print(f"🦴 Omitting: '{heading}'")

    return omit


def pack_chunks(chunks, max_tokens=default_token_sequence_length):
    """
    Combines chunks that are cumulatively smaller than max_tokens
    """
    ct = count_tokens
    # filter out chunks that are just whitespace
    chunks = [chunk for chunk in chunks if ct(chunk) > 0]
    return reduce(
        lambda acc, cur: acc[:-1] + [f"{acc[-1]}\n\n{cur}"]
        if len(acc) and (ct(acc[-1]) + ct(cur)) < max_tokens
        else [*acc, cur],
        chunks,
        []
    )


def partition_contextualized_table(
    md,
    heading,
    max_tokens=512,
    table={
        "portions": 4,
        "intro": 1,
        "body": 2,
    }
):
    """
    takes a markdown table that has some introductory text and partitions the 
    table into chunks proportional to the config:
        table.body / table.portions
    adds the intro to each partition if it is smaller than: 
        table.intro / table.portions 
    if larger, summarizes the intro using OpenAI's GPT-4 model. Then combines
    the intro with each partition of the table into a single chunk that is 
    cumulatively smaller than max_tokens.
    """
    if count_tokens(md) < max_tokens:
        return [md]

    parts = above_table_rx.split(md)
    table_only = len(parts) == 1
    body = parts[-1].strip()
    intro = " ".join(parts[:-1]).strip()
    ratio = round(max_tokens / table["portions"])
    max_intro = ratio * table["intro"]
    head_count = count_tokens(intro)

    if head_count > max_intro:
        print("🤖... Table intro too long. Summarizing using OpenAI...")
        intro = summarize(intro, max_intro)

    max_body = ratio * table["body"]
    body_count = count_tokens(body)
    divisor = round(body_count / max_body)
    [col_head, col_delim, *rows] = body.split("\n")
    # count the number of pipes in the col_head and
    # filter out any rows that don't have the same number of pipes [1]
    col_head_count = len(col_head.split("|")) - 1
    rows = [row for row in rows if len(row.split("|")) - 1 == col_head_count]
    size = round(len(rows) / divisor)

    return [
        f"{heading} - Part {i + 1}:\n\n" + (intro + '\n\n' if not table_only else "") +
        "\n".join([col_head, col_delim, *rows[(i * size):((i + 1) * size)]])
        for i in range(divisor)
    ]


def TLDR(md, length=30):
    """
    returns first and last length chars with ... in between
    """
    return f"```\n{md[:length]}...{md[-length:]}\n```"


def chunk_markdown(
    markdown_payload,
    max_tokens=default_token_sequence_length,
    min_tokens=50,
    omit_headings=None,
    table=None,
    seps=None,
    step=0,
    debug=True,
):
    """
    Recursively chunk markdown content into chunks smaller than max_tokens

    inputs:
        - markdown_payload: accepts three types:
            - a string of markdown
            - a dictionary with a "md" key containing a string of markdown
            - a list of dictionaries with a "md" key containing a string of markdown
        - max_tokens: the maximum number of tokens allowed in a chunk
        - omit_headings: a list of headings of sections to omit from the results
        - table (optional): configuration for partitioning
            - portions (default = 4): the denominator for the ratio of intro to table
            - intro (default = 1): number of portions to use for the intro
            - body (default = 2): number of portions to use for the table
        - seps (optional): the separators to use for chunking (step'd through in order)
        - min_tokens (optional; default = 50): chunks under this threshold will be skipped
        - step (optional): the current step in the recursion
        - debug (optional; default = True): if True, prints verbose debugging info

    returns:
        - a list of dictionaries with the following keys:
            - title: the title of the markdown
            - heading: the heading of the section of markdown
            - md: the markdown chunk

    TODO: put the title and heading back into the "md" after returning results
    """
    if omit_headings is None:
        omit_headings = [
            # "related articles",
            # "related topics",
            "What's new in Tax Rules..."
        ]
    if table is None:
        table = {
            "portions": 4,
            "intro": 1,
            "body": 2,
        }
    if seps is None:
        seps = [
            nn_h1,
            nn_h2,
            nn_h3,
            nn_continuous_str_nn,
            n_n_n_,
            nn_no_punctuation_nn,
        ]
    my_name = chunk_markdown.__name__
    user_args = {
        "max_tokens": max_tokens,
        "seps": seps,
        "table": table,
        "min_tokens": min_tokens,
        "omit_headings": omit_headings,
        "debug": debug,
    }
    if isinstance(markdown_payload, str):
        markdown_payload = [{"md": markdown_payload}]
    elif isinstance(markdown_payload, dict):
        if "md" not in markdown_payload:
            print(f"🔥 !!! `{my_name}`: No 'md' key in markdown_payload !!! 🔥")
        markdown_payload = [markdown_payload]

    def walker(
        acc=None,
        cur=None
    ):
        if acc is None:
            acc = []
        if cur is None:
            cur = {}
        md = cur["md"]
        if len(md) == 0:
            return acc
        if step == 0:
            title = get_title(md)
            if in_omissions(title, omit_headings, debug):
                return acc
            print(f"\n====== Processing '{title}' ======")
            cur["title"] = cur["heading"] = title
        md_sans_links = strip_md_links(md)
        token_count = count_tokens(md_sans_links)
        if debug:
            print(f"\n{'='*step}= Pass {step + 1}")
            print(f"🪙 Tokens: {token_count}")
        if token_count > max_tokens:
            if debug:
                print(
                    f"{token_count} > {max_tokens}. Chunking: '{cur['heading']}'")
            steps_remaining = len(seps) - (step + 1)
            exhausted = not steps_remaining + 1
            if exhausted:
                if debug:
                    print("🔥 Ran out of separators, but has more work to do 🔥")
                    print(f"Heading: {cur['heading']}:\n\n```🔥\n{md}\n\n🔥```")
                return [*acc, cur]
            else:
                chunks = [m for m in re.split(seps[step], md)]
                chunks = pack_chunks(chunks, max_tokens=max_tokens)
                if debug:
                    print("Chunks:", "🍖" * len(chunks))
                payloads = []
                for idx, chunk in enumerate(chunks):
                    title = cur["title"]
                    heading = get_candidate_heading(chunk) or cur["heading"]
                    if in_omissions(heading, omit_headings, debug):
                        continue
                    if debug:
                        print(
                            f"={'=' * step}\n🪙 Tokens: {count_tokens(strip_md_links(chunk))}")
                        print(f"Pass {step + 1} [🍖 {idx}]...")
                        print(
                            f"Title: '{title}'\nHeading: '{heading}'\nTLDR; {TLDR(chunk)}")
                    payload = {
                        "title": title,
                        "heading": heading,
                        "md": chunk,
                    },
                    tab = grab_first_table_and_above(chunk)
                    if tab:
                        if debug:
                            print(
                                f"(Table within: '{heading}')\n={'=' * step}")
                        if not steps_remaining:
                            # exhaust all separators before resorting to breaking up tables
                            if debug:
                                print(
                                    f"Table w/intro too long. Partitioning: '{heading}'\n={'=' * step}"
                                )
                            parts = partition_contextualized_table(
                                tab, heading, max_tokens, table)
                            payloads.extend([
                                {**payload[0],
                                    'heading': f"{heading} Part {i + 1}", "md": p}
                                for i, p in enumerate(parts)
                            ])
                        else:
                            rest = chunk.replace(tab, "")
                            first = {**payload[0], "md": tab}
                            if len(rest) > 5:
                                partitions = [
                                    first, {**payload[0], "md": rest}]
                            else:
                                partitions = [first]
                            results = chunk_markdown(
                                partitions,
                                step=step + 1,
                                **user_args,
                            )
                            payloads.extend(results)
                    else:
                        if debug:
                            print(
                                f"(No table within: '{heading}')\n={'=' * step}")
                        payloads.extend(chunk_markdown(
                            payload,
                            step=step + 1,
                            **user_args,
                        ))
                acc.extend(payloads)
            return acc
        else:
            if token_count < min_tokens:
                if debug:
                    print(f"Pass {step + 1} 🍖 Heading: '{cur['heading']}'")
                    print(f"Short chunk. Skipping.\n={'=' * step}")
                return acc
            else:
                if debug:
                    print(
                        f"🍖 GTG: '{cur['title']}' > '{cur['heading']}' 🌟\n={'=' * step}"
                    )
                return [*acc, cur]

    return reduce(walker, markdown_payload, [])


def clean_w_md_tables(
    markdown
):
    """
    takes markdown and cleans it, preserving tables.
    """
    # find all tables
    tables = md_table_rx.findall(markdown)
    # add newlines before and after each table
    if len(tables) > 0:
        # 1. replace tables with placeholders
        for idx, table in enumerate(tables):
            # print(table[0])
            markdown = markdown.replace(table[0], f"[[{idx}]]")
        # 2. remove all escaped newlines
        markdown = re.sub(md_tokens_rx, " ", markdown)
        # 3. put the tables back in
        for idx, table in enumerate(tables):
            markdown = markdown.replace(f"[[{idx}]]", f"\n\n{table[0]}\n\n")
    else:
        markdown = re.sub(md_tokens_rx, " ", markdown)
    return markdown
