from openai import OpenAI
from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("funding-search-bge")

query_text = "We are an AI company focused on AI for robotics. We are focusing on research right now."

# Embed
print("🔄 Embedding query...")
query_vec = client.embeddings.create(
    input=[query_text],
    model="text-embedding-3-small"
).data[0].embedding

print("🔍 Querying Pinecone...")
results = index.query(
    vector=query_vec,
    top_k=10,
    namespace="openai-v3",
    include_metadata=True
)

# Show results
if results['matches']:
    for i, m in enumerate(results['matches'], 1):
        print(f"{i}. {m['score']:.4f} — {m['metadata'].get('name')}")
else:
    print("❌ No matches returned!")
