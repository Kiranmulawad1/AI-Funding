import os
from openai import OpenAI
from dotenv import load_dotenv
from langchain_community.embeddings import OpenAIEmbeddings

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_embedding_model():
    # Use OpenAI's embedding model
    return OpenAIEmbeddings(
        model="text-embedding-3-small",  # This is the model you used in your notebook
        openai_api_key=OPENAI_API_KEY
    )