import os
from azure.keyvault.secrets import SecretClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

load_dotenv()

KVUri = f'https://{os.environ["KEY_VAULT_NAME"]}.vault.azure.net'

credential = AzureCliCredential()
client = SecretClient(vault_url=KVUri, credential=credential)


def get_secret(name, default=None):
    return client.get_secret(name).value
