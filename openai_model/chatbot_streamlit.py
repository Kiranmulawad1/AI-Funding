import streamlit as st
import os
import re
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil import parser
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# --- Load environment ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV")
NAMESPACE = "openai-v3"

# --- Clients ---
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
index = pc.Index("funding-search")

# --- Load full dataset (optional) ---
df_full = pd.read_csv("/Users/kiranmulawad/AI-Funding/2_preprocessing/data/merged_funding_data.csv")

# --- Streamlit setup ---
st.set_page_config(page_title="Smart Funding Chatbot", layout="centered")
st.title("🤖 Smart Funding Finder Chatbot")

# --- Initialize session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_matches" not in st.session_state:
    st.session_state.last_matches = []

# --- Functions ---
def get_embedding(text):
    return client.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding

def safe_parse_deadline(deadline_str):
    try:
        if pd.isna(deadline_str) or deadline_str.strip() == "":
            return None
        return parser.parse(deadline_str, dayfirst=True, fuzzy=True)
    except Exception:
        return None

def compute_relevance_score(row, query, funding_need=200000, target_domain="AI", user_location="Rhineland-Palatinate"):
    score = 0.0
    if target_domain.lower() in str(row.get("domain", "")).lower():
        score += 0.4
    try:
        amount_val = int(re.sub(r'[^\d]', '', str(row.get("amount", "0"))))
        if amount_val >= funding_need:
            score += 0.3
    except:
        pass
    if "month" in str(row.get("deadline", "")).lower() or "2025" in str(row.get("deadline", "")):
        score += 0.2
    if any(word.lower() in str(row.get("description", "")).lower() for word in query.split()):
        score += 0.1
    if user_location.lower() in str(row.get("location", "")).lower():
        score += 0.1
    return round(score * 100)

def format_funding_blocks(matches):
    blocks = []
    for idx, meta in enumerate(matches, 1):
        name = meta.get("name", "Unnamed")
        deadline_val = meta.get("deadline", "")
        deadline_date = safe_parse_deadline(deadline_val)
        days_left = (deadline_date - datetime.now()).days if deadline_date else None
        deadline_display = f"{deadline_val} (🕒 {days_left} days left)" if days_left is not None else "Not specified"

        block = f"""**{idx}. {name}**
- **Amount**: {meta.get("amount", "Not specified")}
- **Deadline**: {deadline_display}
- **Eligibility**: {meta.get("eligibility", "Not specified")}
- **Procedure**: {meta.get("procedure", "Not specified")}
- **Contact**: {meta.get("contact", "Not specified")}
- **Location**: {meta.get("location", "Not specified")}
- **Source**: {meta.get("source", "N/A")}
"""
        if meta.get("url"):
            block += f"- [More Info]({meta['url']})\n"
        blocks.append(block)
    return "\n".join(blocks)

def query_funding_data(query, location="Rhineland-Palatinate", top_k=5):
    embedding = get_embedding(query)
    search_result = index.query(vector=embedding, top_k=top_k, include_metadata=True, namespace=NAMESPACE)
    matches = [m["metadata"] for m in search_result["matches"]]

    df = pd.DataFrame(matches)
    df["deadline"] = df["deadline"].replace(["", "deadline information not found"], np.nan)
    df["deadline_date"] = df["deadline"].apply(safe_parse_deadline)
    df["deadline_date"] = pd.to_datetime(df["deadline_date"], errors="coerce")
    df["days_left"] = (df["deadline_date"] - pd.Timestamp.now()).dt.days
    df = df[(df["days_left"].isna()) | (df["days_left"] >= 0)]
    df["relevance_score"] = df.apply(lambda r: compute_relevance_score(r, query, user_location=location), axis=1)
    df = df.sort_values("relevance_score", ascending=False)
    return df.to_dict(orient="records")

def get_gpt_response_stream(query, funding_blocks, history):
    """Returns GPT streaming response based on chat history + funding context."""
    messages = [{"role": "system", "content": "You are an expert in German business funding."}]
    
    # Full conversation so far
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add latest funding context again before follow-up
    messages.append({
        "role": "user",
        "content": f"""Here are the most relevant public funding programs in Germany:

{funding_blocks}

Now respond to the user's latest message using these programs. This may be a follow-up.
"""
    })

    return client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages,
        stream=True
    )

# --- Step 1: Show previous chat history ---
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Step 2: Handle new input ---
query = st.chat_input("Describe your company or ask a follow-up...")

if query:
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.chat_history.append({"role": "user", "content": query})

    with st.spinner("Analyzing..."):

        is_followup = len(st.session_state.last_matches) > 0 and len(st.session_state.chat_history) > 1

        if is_followup:
            matches = st.session_state.last_matches
        else:
            matches = query_funding_data(query)
            st.session_state.last_matches = matches

        formatted_blocks = format_funding_blocks(matches)

        with st.chat_message("assistant"):
            full_response = ""
            placeholder = st.empty()
            response_stream = get_gpt_response_stream(query, formatted_blocks, st.session_state.chat_history)
            for chunk in response_stream:
                content = chunk.choices[0].delta.content or ""
                full_response += content
                placeholder.markdown(full_response)

        st.session_state.chat_history.append({"role": "assistant", "content": full_response})
