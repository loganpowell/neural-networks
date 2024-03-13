import asyncio
import json

import instructor
from fns import get_secret
from openai import AzureOpenAI
from pydantic import BaseModel

with open("../constants.json", encoding="utf8") as f:
    config = json.load(f)
    LLM_API_VERSION = config["openai_api_version"]
    LLM_DEPLOYMENT = config["openai_api_deployment"]

OPENAI_API_KEY = get_secret("azure-openai-api-key")
OPENAI_INSTANCE = get_secret("azure-openai-instance-name")
OPENAI_SUBDOMAIN = get_secret('azure-openai-instance-name')
OPENAI_BASE_URL = f"https://{OPENAI_SUBDOMAIN}.openai.azure.com"

structured = instructor.patch(AzureOpenAI(
    api_version=LLM_API_VERSION,
    api_key=OPENAI_API_KEY,
    azure_endpoint=OPENAI_BASE_URL,
))

async def payloader(
    messages: list[dict],
    spec,
    llm_model: str = LLM_DEPLOYMENT,
):
    """
    Converts plain language into a structured payload for a given spec
    """
    response = await structured.chat.completions.create(
        model=llm_model,
        response_model=spec,
        messages=messages,
    )
    
    return response
    