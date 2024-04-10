import os

import openai
import requests
import tiktoken

from .keyvault import get_secret

OPENAI_BASE_URL = (
    f"https://{get_secret('azure-openai-instance-name')}.openai.azure.com/"
)
EMBEDDINGS_API_VERSION = get_secret("azure-openai-embedding-api-version")

OPENAI_EMBEDDING_DEPLOYMENT = get_secret(
    "azure-openai-embedding-api-deployment-name")
OPENAI_API_KEY = get_secret("azure-openai-api-key")
OPENAI_INSTANCE = get_secret("azure-openai-instance-name")
OPENAI_DEPLOYMENT = get_secret("azure-openai-deployment-name")

# replaces OPENAI_DEPLOYMENT (GPT-4) for now
GPT35 = "VERX-GTP35-TURBO-ET"

OPENAI_API_VERSION = get_secret("azure-openai-client-api-version")

openai.api_type = "azure"
openai.api_base = OPENAI_BASE_URL
openai.api_version = OPENAI_API_VERSION
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
    URL = f"https://{OPENAI_INSTANCE}.openai.azure.com/openai/deployments/{OPENAI_EMBEDDING_DEPLOYMENT}/embeddings?api-version={EMBEDDINGS_API_VERSION}"

    headers = {"Content-Type": "application/json", "api-key": OPENAI_API_KEY}

    body = {
        "input": query
    }

    response = requests.post(URL, headers=headers, json=body, timeout=20)

    results = response.json()

    return results["data"][0]["embedding"]


def gen_summary(text, title, heading, max_tokens=default_token_sequence_length):
    """generates a summary of the text using the GPT-4 model"""

    URL = f"https://{OPENAI_INSTANCE}.openai.azure.com/openai/deployments/{OPENAI_DEPLOYMENT}/chat/completions?api-version={openai.api_version}"

    headers = {"Content-Type": "application/json", "api-key": OPENAI_API_KEY}

    body = {
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Summarize the following 'CONTENT'as instructions in a manner that retains and emphasizes keywords. The result should be amenable to semantic searchability.",
            },
            {
                "role": "user",
                "content": f"CONTENT:\n\n{title}:\n\n{heading}.\n\n{text}",
            },
        ],
        "temperature": 0,
        "frequency_penalty": 1,
        "presence_penalty": 0,
        "max_tokens": max_tokens,
        "stop": None,
    }

    response = requests.post(URL, headers=headers, json=body, timeout=20)

    content = response.json()["choices"][0]["message"]["content"]

    print(f"🌊 (`gen_summary`) Summary for '{heading}':\n", content)

    content = f"{heading}.  {content}"

    return content


def summarize(text, max_tokens=default_token_sequence_length):
    """generates a summary of the text using the GPT-4 model"""
    URL = f"https://{OPENAI_INSTANCE}.openai.azure.com/openai/deployments/{OPENAI_DEPLOYMENT}/chat/completions?api-version={openai.api_version}"

    headers = {"Content-Type": "application/json", "api-key": OPENAI_API_KEY}

    body = {
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Summarize the following text in a manner that retains and emphasizes keywords. The result should be amenable to semantic searchability. Please format as markdown.",
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


def messages_prompt(
    messages: list[dict[str, str]],
    max_tokens=default_token_sequence_length,
    deployment=OPENAI_DEPLOYMENT,
    api_version=OPENAI_API_VERSION,
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

    URL = f"https://{OPENAI_INSTANCE}.openai.azure.com/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

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


def text_generation(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    temperature: float = 0.0,
    frequency_penalty: int = 1,
    presence_penalty: int = 0,
    max_tokens=default_token_sequence_length
):
    """generates a summary of the text using the GPT-4 model"""
    URL = f"https://{OPENAI_INSTANCE}.openai.azure.com/openai/deployments/{OPENAI_DEPLOYMENT}/chat/completions?api-version={openai.api_version}"

    headers = {"Content-Type": "application/json", "api-key": OPENAI_API_KEY}

    body = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": temperature,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "max_tokens": max_tokens,
        "stop": None,
    }

    response = requests.post(URL, headers=headers, json=body, timeout=20)

    return response.json()["choices"][0]["message"]["content"]
