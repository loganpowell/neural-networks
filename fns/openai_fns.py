import os

import openai
import requests
import tiktoken
import json

from .keyvault import get_secret

with open("../constants.json", encoding="utf8") as f:
    config = json.load(f)
    LLM_API_VERSION = config["openai_api_version"]
    LLM_DEPLOYMENT = config["openai_api_deployment"]

OPENAI_BASE_URL = (
    f"https://{get_secret('azure-openai-instance-name')}.openai.azure.com/"
)

EMBEDDINGS_API_VERSION = get_secret("azure-openai-embedding-api-version")
OPENAI_EMBEDDING_DEPLOYMENT = get_secret(
    "azure-openai-embedding-api-deployment-name")
OPENAI_API_KEY = get_secret("azure-openai-api-key")
OPENAI_INSTANCE = get_secret("azure-openai-instance-name")

openai.api_type = "azure"
openai.api_base = OPENAI_BASE_URL
openai.api_version = LLM_API_VERSION
openai.api_key = OPENAI_API_KEY


# embeddings leaderboard https://huggingface.co/spaces/mteb/leaderboard
embedding_model = "text-embedding-ada-002"
default_token_sequence_length = 512

tokenizer = tiktoken.encoding_for_model(embedding_model)


def count_tokens(
    string: str,
    # encoding_name: str = embedding_model
) -> int:
    """
    Returns the number of tokens in a text string.
    """
    num_tokens = len(tokenizer.encode(string))
    return num_tokens


def get_embeddings(query):
    """uses openai api to generate embeddings for a query"""
    URL = f"https://{OPENAI_INSTANCE}.openai.azure.com/openai/deployments/{
        OPENAI_EMBEDDING_DEPLOYMENT}/embeddings?api-version={EMBEDDINGS_API_VERSION}"

    headers = {"Content-Type": "application/json", "api-key": OPENAI_API_KEY}

    body = {
        "input": query
    }

    response = requests.post(URL, headers=headers, json=body, timeout=20)

    results = response.json()

    return results


def messages_prompt(
    messages: list[dict[str, str]],
    max_tokens=default_token_sequence_length,
    deployment=LLM_DEPLOYMENT,
    api_version=LLM_API_VERSION,
):
    """
    Basic wrapper for the openai's chat completion api. Input some messages with the following structure:
    Example:
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Summarize the following text into a list of bullets that capture the key themes of the text. "
        },
        {
            "role": "user",
            "content": "This is the text that you want to summarize"
        }
    ]
    response = messages_prompt(messages)
    """

    URL = f"https://{OPENAI_INSTANCE}.openai.azure.com/openai/deployments/{
        deployment}/chat/completions?api-version={api_version}"

    headers = {
        "Content-Type": "application/json",
        "api-key": OPENAI_API_KEY
    }

    # pretty print messages
    # print("messages_prompt messages:", json.dumps(messages, indent=2))
    body = {
        "messages": messages,
        "temperature": 0,
        "frequency_penalty": 1,
        "presence_penalty": 0,
        "max_tokens": round(max_tokens),
        "stop": None,
    }
    response = requests.post(URL, headers=headers, json=body, timeout=60)
    # print("messages_prompt response:", response.json())

    content = response.json()["choices"][0]["message"]["content"]

    return content


def summarize(text, max_tokens=default_token_sequence_length):
    """
    Generates a summary of the key theme of the text.
    """
    URL = f"https://{OPENAI_INSTANCE}.openai.azure.com/openai/deployments/{
        LLM_DEPLOYMENT}/chat/completions?api-version={LLM_API_VERSION}"

    headers = {"Content-Type": "application/json", "api-key": OPENAI_API_KEY}

    body = {
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Summarize the following text into a well-formatted list of bullets that capture the key information as per the user's query."
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "frequency_penalty": 1,
        "presence_penalty": 0,
        "max_tokens": round(max_tokens),
        "stop": None,
    }

    response = requests.post(URL, headers=headers, json=body, timeout=60)
    # print(response.json())

    content = response.json()["choices"][0]["message"]["content"]

    return content
