from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
load_dotenv()

model = AzureChatOpenAI(
    azure_deployment=os.getenv('AZURE_DEPLOYMENT_NAME', ''),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION', ''),
    temperature=0.5,
    max_tokens=4096,
    # other params...
)
