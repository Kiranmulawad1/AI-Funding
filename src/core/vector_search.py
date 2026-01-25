# search_engine.py
import pandas as pd
from pinecone import Pinecone
from src.core.config import PINECONE_API_KEY, INDEX_NAME, NAMESPACE, get_openai_client
from src.core.utils import safe_parse_deadline

client = get_openai_client()
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

def get_embedding(text: str):
    return client.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding

def compute_relevance(item, query):
    score = 0
    if query.lower() in str(item.get("description", "")).lower():
        score += 0.1
    if "deadline" in item:
        try:
            deadline = pd.to_datetime(safe_parse_deadline(item["deadline"]), utc=True)
            if deadline >= pd.Timestamp.now(tz="UTC"):
                item["days_left"] = (deadline - pd.Timestamp.now(tz="UTC")).days
                item["deadline_date"] = deadline
                score += 0.2
        except:
            pass
    return round(score * 100)

def query_funding_data(query: str, top_k: int = 8):
    emb = get_embedding(query)
    res = index.query(vector=emb, top_k=top_k, include_metadata=True, namespace=NAMESPACE)
    matches = [m["metadata"] for m in res.get("matches", [])]
    for m in matches:
        m["relevance_score"] = compute_relevance(m, query)
    return sorted(matches, key=lambda x: x.get("relevance_score", 0), reverse=True)