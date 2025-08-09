import os
import re
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil import parser
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
import fitz  # PyMuPDF

# -----------------------
# 0) Setup & Environment
# -----------------------
load_dotenv()

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV     = os.getenv("PINECONE_ENV")
INDEX_NAME       = os.getenv("PINECONE_INDEX_NAME", "funding-search")
NAMESPACE        = os.getenv("PINECONE_NAMESPACE", "openai-v3")
FUNDING_CSV_PATH = os.getenv("FUNDING_CSV_PATH", "./data/merged_funding_data.csv")

required = {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "PINECONE_API_KEY": PINECONE_API_KEY,
    "PINECONE_ENV": PINECONE_ENV,
}
missing = [k for k, v in required.items() if not v]
if missing:
    st.set_page_config(page_title="Smart Funding Chatbot", layout="centered")
    st.error(f"Missing environment variables: {', '.join(missing)}")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)

# Cache heavy resources
@st.cache_resource(show_spinner=False)
def get_index(_pc, name: str):
    return _pc.Index(name)

@st.cache_data(show_spinner=False)
def load_full_df(path: str):
    return pd.read_csv(path)

index = get_index(pc, INDEX_NAME)
df_full = load_full_df(FUNDING_CSV_PATH)

# -----------------------
# 1) Streamlit UI Setup
# -----------------------
st.set_page_config(page_title="Smart Funding Chatbot", layout="centered")
st.title("🤖 Smart Funding Finder Chatbot")

# session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_matches" not in st.session_state:
    st.session_state.last_matches = []
if "generated_query" not in st.session_state:
    st.session_state.generated_query = ""

# Sidebar controls
st.sidebar.header("⚙️ Options")
need = st.sidebar.number_input("Target amount (€)", min_value=0, value=200_000, step=10_000)
loc  = st.sidebar.text_input("Preferred location/region", value="Rhineland-Palatinate")
domain_pref = st.sidebar.text_input("Preferred domain keyword (optional)", value="AI")

if st.sidebar.button("🔄 Reset chat"):
    st.session_state.chat_history = []
    st.session_state.last_matches = []
    st.session_state.generated_query = ""
    st.rerun()

# -----------------------
# 2) Utilities
# -----------------------
def extract_text_from_pdf(uploaded_file):
    """Extract all text from uploaded PDF using PyMuPDF."""
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text.strip()

def summarize_text_with_gpt(raw_text: str) -> str:
    """
    Summarize long PDF text into a 2–3 line query suitable for funding discovery.
    Always uses gpt-3.5-turbo for cost efficiency.
    """
    prompt = f"""
You are an assistant that summarizes company profiles for funding discovery.

Extract the core business description, goals, and funding need from this text:
---
{raw_text[:6000]}
---
Summarize into 2–3 lines suitable for finding matching public grants in Germany.
"""
    res = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

def get_embedding(text: str):
    # text-embedding-3-small has 1536 dims; ensure Pinecone index dimension matches
    return client.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding

def safe_parse_deadline(deadline_str):
    """Parse many date formats; return a naive datetime if possible (we'll convert to UTC later)."""
    try:
        if pd.isna(deadline_str) or str(deadline_str).strip() == "":
            return None
        return parser.parse(str(deadline_str), dayfirst=True, fuzzy=True)
    except Exception:
        return None

def compute_relevance_score(row, query, funding_need=0, target_domain="", user_location=""):
    """Dynamic, transparent scoring. Prefer parsed deadlines and user prefs."""
    score = 0.0

    # domain preference
    if target_domain and target_domain.lower() in str(row.get("domain", "")).lower():
        score += 0.4

    # amount threshold
    try:
        amount_val = int(re.sub(r"[^\d]", "", str(row.get("amount", "0"))))
        if funding_need and amount_val >= funding_need:
            score += 0.3
    except Exception:
        pass

    # deadline in future (uses parsed date, made UTC-aware elsewhere)
    dd = row.get("deadline_date")
    if isinstance(dd, pd.Timestamp) and pd.notnull(dd) and dd >= pd.Timestamp.now(tz="UTC"):
        score += 0.2

    # keyword overlap with description
    query_tokens = re.findall(r"\w+", query.lower())
    if any(tok in str(row.get("description", "")).lower() for tok in query_tokens):
        score += 0.1

    # location preference
    if user_location and user_location.lower() in str(row.get("location", "")).lower():
        score += 0.1

    return round(score * 100)

def days_left_utc(deadline_str):
    """Return integer days left using UTC-aware arithmetic, or None."""
    d = safe_parse_deadline(deadline_str)
    if d is None:
        return None
    d_utc = pd.to_datetime(d, errors="coerce", utc=True)
    if pd.isna(d_utc):
        return None
    return (d_utc - pd.Timestamp.now(tz="UTC")).days

def format_funding_blocks(matches):
    """Markdown card list for GPT + UI. Shows relevance scores for transparency."""
    blocks = []
    for idx, meta in enumerate(matches, 1):
        name = meta.get("name", "Unnamed")

        # UTC-aware days left
        deadline_val = meta.get("deadline", "")
        days_left = days_left_utc(deadline_val)
        deadline_display = (
            f"{deadline_val} (🕒 {days_left} days left)" if days_left is not None else "Not specified"
        )

        score = meta.get("relevance_score", None)
        title_line = f"**{idx}. {name}**" + (f" — *Relevance: {score}*" if score is not None else "")

        block = f"""{title_line}
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

def query_funding_data(query, location="Rhineland-Palatinate", top_k=5, need_eur=0, dom_pref=""):
    """Semantic search -> parse deadlines -> UTC-aware -> score -> sort -> return dict list."""
    embedding = get_embedding(query)
    search_result = index.query(vector=embedding, top_k=top_k, include_metadata=True, namespace=NAMESPACE)
    matches = [m["metadata"] for m in search_result.get("matches", [])]
    if not matches:
        return []

    df = pd.DataFrame(matches)

    # normalize deadlines
    placeholders = ["", "deadline information not found"]
    df["deadline"] = df["deadline"].replace(placeholders, np.nan)

    # parse -> convert to UTC-aware datetimes
    df["deadline_date"] = df["deadline"].apply(safe_parse_deadline)
    df["deadline_date"] = pd.to_datetime(df["deadline_date"], errors="coerce", utc=True)

    # compute days_left with tz-aware "now"
    now_ts = pd.Timestamp.now(tz="UTC")
    df["days_left"] = (df["deadline_date"] - now_ts).dt.days

    # filter: keep missing or future deadlines
    df = df[(df["days_left"].isna()) | (df["days_left"] >= 0)]
    if df.empty:
        return []

    # dynamic relevance
    df["relevance_score"] = df.apply(
        lambda r: compute_relevance_score(
            r,
            query,
            funding_need=need_eur,
            target_domain=dom_pref,
            user_location=location,
        ),
        axis=1,
    )

    df = df.sort_values("relevance_score", ascending=False)
    return df.to_dict(orient="records")

def get_gpt_response_stream(user_message: str, funding_blocks: str, history):
    """
    Stream GPT response using full chat history + fresh funding context.
    Strong hint to keep answers grounded in current list.
    """
    active_hint = (
        "Answer ONLY with respect to the programs listed below. "
        "If the user says 'the second one', use the numbering from this list. "
        "Do not invent new programs. If info is missing, say 'Not specified'."
    )

    messages = [{"role": "system", "content": "You are an expert in German business funding."}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({
        "role": "user",
        "content": f"{active_hint}\n\n{funding_blocks}\n\nUser message: {user_message}"
    })

    return client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages,
        stream=True
    )

# -----------------------
# 3) PDF Upload (optional)
# -----------------------
st.sidebar.subheader("📄 Upload Company Profile (Optional)")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF", type=["pdf"])

if uploaded_pdf:
    raw_text = extract_text_from_pdf(uploaded_pdf)
    summary_query = summarize_text_with_gpt(raw_text)  # gpt-3.5-turbo
    st.session_state.generated_query = summary_query
    st.sidebar.success("✅ Extracted and summarized!")
    with st.sidebar.expander("📝 Auto-Generated Query"):
        st.write(summary_query)

# -----------------------
# 4) Chat Loop
# -----------------------
# Show previous history first (for correct order)
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Hybrid input: typed query or generated from PDF
query = st.chat_input("Describe your company or ask a follow-up...") or st.session_state.get("generated_query", "")

if query:
    # show and store user message
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.chat_history.append({"role": "user", "content": query})

    with st.spinner("Analyzing funding options..."):
        # follow-up: reuse last matches; new query: search again
        is_followup = len(st.session_state.last_matches) > 0 and len(st.session_state.chat_history) > 1

        if is_followup:
            matches = st.session_state.last_matches
        else:
            matches = query_funding_data(
                query,
                location=loc,
                top_k=5,
                need_eur=need,
                dom_pref=domain_pref,
            )
            st.session_state.last_matches = matches

        if not matches:
            with st.chat_message("assistant"):
                msg = "No matching programs found. Try adjusting your description, amount target, or region."
                st.markdown(msg)
            st.session_state.chat_history.append({"role": "assistant", "content": msg})
        else:
            formatted_blocks = format_funding_blocks(matches)

            # stream assistant response
            with st.chat_message("assistant"):
                full_response = ""
                placeholder = st.empty()
                response_stream = get_gpt_response_stream(query, formatted_blocks, st.session_state.chat_history)
                for chunk in response_stream:
                    content = chunk.choices[0].delta.content or ""
                    full_response += content
                    placeholder.markdown(full_response)

            st.session_state.chat_history.append({"role": "assistant", "content": full_response})
