# config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

# Project root is the folder that contains `ai-funding-app/`
# This file lives in ai-funding-app/, so its parent is the project root.
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent

# Default CSV path: ../data/merged_funding_data.csv (sibling to ai-funding-app)
DEFAULT_DATA_CSV = PROJECT_ROOT / "data" / "merged_funding_data.csv"

# ---- Required/optional ENV ----
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV     = os.getenv("PINECONE_ENV")  # keep for your current SDK usage
INDEX_NAME       = os.getenv("PINECONE_INDEX_NAME", "funding-search")
NAMESPACE        = os.getenv("PINECONE_NAMESPACE", "openai-v3")

# Allow override via env, else use sibling ../data path
FUNDING_CSV_PATH = Path(os.getenv("FUNDING_CSV_PATH", str(DEFAULT_DATA_CSV))).resolve()

def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return OpenAI(api_key=OPENAI_API_KEY)

def get_pinecone_client() -> Pinecone:
    if not PINECONE_API_KEY:
        raise RuntimeError("Missing PINECONE_API_KEY")
    return Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
