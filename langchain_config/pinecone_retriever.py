import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_config.embeddings import get_embedding_model
# Change this import
from langchain_config.llm_provider import get_llm

# Load env variables
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX", "funding-search") # Use your index name
NAMESPACE = "openai-v3" # Update namespace to match your OpenAI uploads

def get_retriever():
    embedding = get_embedding_model()
    pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
    index = pc.Index(PINECONE_INDEX_NAME)
    vectorstore = PineconeVectorStore(index=index, embedding=embedding, namespace=NAMESPACE)
    return vectorstore.as_retriever()