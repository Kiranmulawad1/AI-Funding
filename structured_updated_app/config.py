# config.py

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

# Load .env file variables if available
load_dotenv()

# -------- App paths --------
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
DEFAULT_DATA_CSV = PROJECT_ROOT / "data" / "merged_funding_data.csv"

# -------- Environment Variables --------
POSTGRES_URL = os.getenv("POSTGRES_URL")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV     = os.getenv("PINECONE_ENV")
INDEX_NAME       = os.getenv("PINECONE_INDEX_NAME", "funding-search")
NAMESPACE        = os.getenv("PINECONE_NAMESPACE", "openai-v3")
FUNDING_CSV_PATH = Path(os.getenv("FUNDING_CSV_PATH", str(DEFAULT_DATA_CSV))).resolve()

# -------- OpenAI client --------
def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return OpenAI(api_key=OPENAI_API_KEY)

# -------- Pinecone client --------
def get_pinecone_client() -> Pinecone:
    if not PINECONE_API_KEY:
        raise RuntimeError("Missing PINECONE_API_KEY")
    return Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
