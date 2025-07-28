import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore  # ✅ New v3-compatible retriever
from langchain_config.embeddings import get_embedding_model

# Load env variables
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT")  # Only needed for Pinecone class
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX", "funding-search-bge")
NAMESPACE = "open-source-v1"  # Namespace for the index

def get_retriever():
    embedding = get_embedding_model()

    # ✅ Init Pinecone v3 client
    pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
    index = pc.Index(PINECONE_INDEX_NAME)

    # ✅ Use langchain-pinecone retriever (v3-compatible)
    vectorstore = PineconeVectorStore(index=index, embedding=embedding, namespace=NAMESPACE)

    return vectorstore.as_retriever()
