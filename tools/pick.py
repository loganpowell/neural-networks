import fns

# takes a list and picks one based on intent

prompt_pick = """
You are a tool that picks the best url for a given query and a list of search
results containing urls with supporting information.

given a user's query and a list of search results, you should pick the best url
for the user's query.

Return only the full url of the best search result. 
Your response should only contain a single url. No other language or formatting 
is allowed.
"""


def pick(query, results):
    """
    Uses an LLM to pick a response from a list of responses
    """
    print(f"`pick`: Query: {query}")

    response = fns.messages_prompt([
        {"role": "system", "content": prompt_pick},
        {"role": "user", "content": query},
        {"role": "assistant", "content": results}
    ])

    return response
