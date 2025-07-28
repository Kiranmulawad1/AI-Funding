from langchain_community.embeddings import HuggingFaceEmbeddings

def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="BAAI/bge-small-en")
