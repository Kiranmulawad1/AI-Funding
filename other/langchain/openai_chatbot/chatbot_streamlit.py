# chatbot_streamlit.py

import streamlit as st
from chatbot_agent import get_chatbot_chain


st.set_page_config(page_title="Funding Chatbot", layout="centered")
st.title("💬 Funding Finder Chatbot")


# Initialize chat history in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Utility to convert chat history of messages (role/content dicts)
# to list of (question, answer) tuples as LangChain expects
def convert_chat_history(history):
    qas = []
    # Expect history alternating user-assistant pairs
    for i in range(0, len(history) - 1, 2):
        if history[i]["role"] == "user" and history[i+1]["role"] == "assistant":
            qas.append((history[i]["content"], history[i+1]["content"]))
    return qas

# Load chatbot chain
qa_chain = get_chatbot_chain()

# User input
user_question = st.chat_input("Ask a question about funding...")
if user_question and user_question.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_question.strip()})

    # Call the chatbot chain with chat history converted as pairs
    with st.chat_message("assistant"):
        result = qa_chain.invoke({
            "question": user_question.strip(),
            "chat_history": convert_chat_history(st.session_state.chat_history)
        })
        answer = result.get("answer", "Sorry, no answer generated.")
        st.markdown(answer)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})

        # Optional: show source documents if available
        if "source_documents" in result and result["source_documents"]:
            st.markdown("#### Sources")
            for doc in result["source_documents"]:
                src = doc.metadata.get("source", "Unknown source")
                st.markdown(f"- {src}")
