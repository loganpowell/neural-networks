import json
import functools

from numpy import dot
from numpy.linalg import norm
from tools import api_mocker, web_search, page_scraper, pick, search
from .openai_fns import get_embeddings, messages_prompt, summarize


action_vtx_api = {
    "name": "action_vtx_api",
    "function": api_mocker,
    "description": "Takes actions against one of Vertex's APIs.",
    "follow_up": None,
}

ask_user = {
    "name": "ask_user",
    "function": None,
    "description": "When the assistant needs more information from the user to proceed. Not for commands.",
    "follow_up": None,
}

elaborate_vtx_url = {
    "name": "elaborate_vtx_url",
    "function": page_scraper,
    "description": "Takes a single URL and returns the full text of the page.",
    "follow_up": "Text is verbose, I will summarize it for you.",
}

llm_eloquent = {
    "name": "llm_eloquent",
    "function": summarize,
    "description": "Summarizes text to make it more concise and tailored to the user's request.",
    "follow_up": None
}

llm_payloader = {
    "name": "llm_payloader",
    "description": "Converts plain language into a structured payload for a given spec",
    "follow_up": None
}

llm_pick = {
    "name": "llm_pick",
    "function": pick,
    "description": "When a list is provided, this action picks the item that is most relevant to the user's request.",
    "follow_up": "The selected URL needs additional context. I will elaborate on it."
}

search_vtx_com = {
    "name": "search_vtx_com",
    "function": lambda x: web_search(x + " site:vertexinc.com"),
    "description": "For general inquiries about Vertex's products or services. Returns a list of search results.",
    "follow_up": "The results are a list of pages. I will pick the most relevant one for you.",
}

search_vtx_kb = {
    "name": "search_vtx_kb",
    "function": lambda x: web_search(x + " site:vertexinc.com"),
    "description": "Search for specific/esoteric information about a Vertex product/service.",
    "follow_up": "The results are a list of pages. I will pick the most relevant one for you.",
}


def isolate_action_data(action):
    """
    isolates the data from the action
    """
    return {
        "name": action["name"],
        "description": action["description"],
    }


catalog = {
    "search_vtx_com": isolate_action_data(search_vtx_com),
    "search_vtx_kb": isolate_action_data(search_vtx_kb),
    "elaborate_vtx_url": isolate_action_data(elaborate_vtx_url),
    "action_vtx_api": isolate_action_data(action_vtx_api),
    "llm_pick": isolate_action_data(llm_pick),
    "llm_eloquent": isolate_action_data(llm_eloquent),
    "ask_user": isolate_action_data(ask_user)
}


actions = [
    action_vtx_api,
    {
        **action_vtx_api,
        "description": "Executes a command on a user's behalf."
    },
    {
        **action_vtx_api,
        "description": "Not for answering questions. Only for executing commands."
    },
    {
        **action_vtx_api,
        "description": "Executes a command on a user's behalf with specific information. I do not answer questions."
    },
    ask_user,
    {
        **ask_user,
        "description": "Ends a conversation. No actions to follow."
    },
    elaborate_vtx_url,
    {
        **elaborate_vtx_url,
        "description": "Can elaborate on a webpage (for a URL). Not for summarization."
    },
    {
        **elaborate_vtx_url,
        "description": "Returns the full content of an entire web page."
    },
    {
        **elaborate_vtx_url,
        "description": "Get's all the context surrounding a particular topic.",
    },
    llm_eloquent,
    {
        **llm_eloquent,
        "description": "Summarizes a page."
    },
    {
        **llm_eloquent,
        "description": "Rephrases a procured chunk of text to address their question as a helpful response."
    },
    {
        **llm_eloquent,
        "description": "When text needs to be summarized, I can pull out only the relevant information."
    },
    llm_pick,
    {
        **llm_pick,
        "description": "When a list of URLs is available, picks one that is most relevant."
    },
    {
        **llm_pick,
        "description": "Picks an item from a list that best suits a user's query."
    },
    {
        **llm_pick,
        "description": "Does not provide the full text of the result, just an identifier."
    },
    search_vtx_com,
    {
        **search_vtx_com,
        "description": "Questions about sales and marketing materials."
    },
    {
        **search_vtx_com,
        "description": "Not for information on a specific Vertex product."
    },
    {
        **search_vtx_com,
        "description": "Returns a list of search results of pages with only the following attributes per result: title, URL, and snippet."
    },
    search_vtx_kb,
    {
        **search_vtx_kb,
        "description": "Returns a list of search results, each containing completed chunks of knowledge."
    },
    {
        **search_vtx_kb,
        "description": "Returns a list containing results that each have more detailed information about Vertex's products and services. Typically don't require elaboration."
    },
]


@functools.cache
def action_embeddings():
    """
    embeds the descriptions of an action and returns it with an 'embed' key
    """
    embedded_actions = []
    for action in actions:
        embed = get_embeddings(action["description"])
        embedded_actions.append({**action, "embed": embed})
    return embedded_actions


def get_intent(message):
    """
    Uses the embeddings of the actions to find the closest match to the message
    """
    # print(f"Inferring intent for: {message}")

    msg_emb = get_embeddings(message)

    nn = None
    nn_score = 0
    for a in action_embeddings():
        embed = a["embed"]
        # print(f"Embed length: {len(embed)}\n embed: {embed}")
        score = dot(embed, msg_emb) / (norm(embed) * norm(msg_emb))
        if score > nn_score:
            nn_score = score
            nn = {**a, "embed": [f"... {len(a['embed'])} dimensions ..."]}
    return nn
