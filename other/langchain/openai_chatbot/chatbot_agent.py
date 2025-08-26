from langchain_community.vectorstores import Pinecone as LangPinecone
from langchain_openai import OpenAIEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT")  # e.g. "us-west1-gcp"
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "funding-search")
NAMESPACE = os.getenv("PINECONE_NAMESPACE", "openai-v3")

embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=OPENAI_API_KEY,
)

vectorstore = LangPinecone.from_existing_index(
    index_name=INDEX_NAME,
    embedding=embedding_model,
    namespace=NAMESPACE
)

llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0.2)

qa_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
    return_source_documents=True,
)

def get_chatbot_chain():
    return qa_chain
