import json
import os
from typing import List

import requests
from dotenv import load_dotenv
from markdownify import markdownify as md

load_dotenv()

API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")


def web_search(
    query: str,
    search_kwargs: dict = {},
    api_key: str = API_KEY
):
    """Wrapper around the Brave search engine."""
    base_url: str = "https://api.search.brave.com/res/v1/web/search"
    """The base URL for the Brave search engine."""

    print(f"web_search: Searching for: {query}")

    def search_request(query: str) -> list[dict]:
        headers = {
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        }
        req = requests.PreparedRequest()
        params = {**search_kwargs, **{"q": query}}
        req.prepare_url(base_url, params)
        if req.url is None:
            raise ValueError("prepared url is None, this should not happen")

        response = requests.get(req.url, headers=headers, timeout=20)
        if not response.ok:
            raise requests.exceptions.HTTPError(
                f"HTTP error {response.status_code}")

        return response.json().get("web", {}).get("results", [])

    web_search_results = search_request(query)

    final_results = [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": md(item.get("description")),
        }
        for item in web_search_results
    ]

    print(f"Found {len(final_results)} results for: {query}")
    return final_results
