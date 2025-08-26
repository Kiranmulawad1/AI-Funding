import os
from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_llm(model_name: str = "openai"):
    """
    Returns the specified LLM or a default one.
    """
    if model_name == "openai":
        return ChatOpenAI(
            model="gpt-4-turbo",  # You can choose the specific OpenAI model here
            openai_api_key=OPENAI_API_KEY,
            temperature=0
        )
    elif model_name == "llama3":
        return Ollama(model="llama3.2")
    else:
        raise ValueError(f"Unsupported model name: {model_name}")