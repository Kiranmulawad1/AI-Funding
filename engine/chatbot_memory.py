from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_config.pinecone_retriever import get_retriever
from langchain_config.llm_provider import get_llm

def get_chatbot_chain(provider="openai"): # Add the provider parameter with a default
    retriever = get_retriever()
    llm = get_llm(model_name=provider) # Pass the provider to get_llm
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=False,
    )
    return qa_chain