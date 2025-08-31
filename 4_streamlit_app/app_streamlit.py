import os
import re
import uuid
import hashlib
import fitz  # PyMuPDF
import streamlit as st
from datetime import datetime

from config import OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENV, get_openai_client
from rag_core import query_funding_data
from utils import present, program_name
from docx_generator import generate_funding_draft
from memory import save_query_to_postgres, get_recent_queries, clear_all_queries
from gpt_recommender import build_gpt_prompt, extract_sources_from_response

# ------------------ Setup ------------------
st.set_page_config(page_title="Smart Funding Finder", layout="centered")
client = get_openai_client()

# ------------------ ENV Check ------------------
missing_keys = [k for k, v in {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "PINECONE_API_KEY": PINECONE_API_KEY,
    "PINECONE_ENV": PINECONE_ENV,
}.items() if not v]
if missing_keys:
    st.error(f"Missing environment variables: {', '.join(missing_keys)}")
    st.stop()

# ------------------ Session Init ------------------
for key in ["chat_history", "last_recommendation", "pdf_summary_query", "pdf_hash", "pending_query"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "chat_history" else []

# ------------------ Sidebar: PDF Upload + Reset ------------------
if "file_uploader_key" not in st.session_state:
    st.session_state["file_uploader_key"] = "default_uploader"

st.sidebar.subheader("📄 Upload Company Profile (Optional)")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF", type=["pdf"], key=st.session_state["file_uploader_key"])

if uploaded_pdf:
    pdf_bytes = uploaded_pdf.getvalue()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    if st.session_state.pdf_hash != pdf_hash:
        st.session_state.pdf_hash = pdf_hash
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = "\n".join(page.get_text() for page in doc).strip()[:6000]
        prompt = f"""Summarize the company profile into 2–3 lines for public funding discovery.\nFocus on domain, goals, and funding need.\n---\n{full_text}\n---"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state.pdf_summary_query = response.choices[0].message.content.strip()
        st.sidebar.success("✅ Summary generated from PDF.")

st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Chat Options")
if st.sidebar.button("🔄 Reset Conversation"):
    for key in [
        "chat_history", "last_recommendation", "pdf_summary_query",
        "pending_query", "pdf_hash", "uploaded_pdf", "suppress_query"
    ]:
        st.session_state.pop(key, None)
    st.session_state["file_uploader_key"] = str(uuid.uuid4())
    st.rerun()

# ------------------ Header ------------------
st.title("🤖 Smart AI Funding Finder")

# ------------------ History Viewer ------------------
with st.expander("🕒 Past Queries History (Last 20)"):
    recent = get_recent_queries(limit=20)
    if not recent:
        st.info("No queries saved yet.")
    else:
        for q in recent:
            try:
                timestamp = datetime.fromisoformat(str(q['timestamp'])).astimezone()
                formatted_time = timestamp.strftime("%d %B %Y — %H:%M")
            except Exception:
                formatted_time = str(q['timestamp'])
            st.markdown(f"---\n📅 **{formatted_time}**")
            st.markdown(f"🔍 **{q['query'][:200]}**")
            st.markdown(f"📦 **Source**: `{q['source']}` | 📈 **Results**: `{q['result_count']}`")
            with st.expander("🗞 GPT Recommendation"):
                st.markdown(q['recommendation'])

    if st.button("🧈 Clear History"):
        clear_all_queries()
        st.success("History cleared.")
        st.rerun()

# ------------------ Chat Input + Display ------------------
user_text_input = st.chat_input("Describe your company or project...")

# ✅ Clear suppress flag if user enters a new message
if user_text_input:
    st.session_state.pop("suppress_query", None)

query = user_text_input or st.session_state.pdf_summary_query
st.session_state.pending_query = query

# ✅ Block GPT rerun if draft/download is triggered
if any(k.startswith("draft_") and st.session_state.get(k) for k in st.session_state.keys()) or st.session_state.get("suppress_query"):
    query = None

# ✅ Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ✅ Run GPT if valid new query
if query:
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.chat_history.append({"role": "user", "content": query})

    if st.session_state.last_recommendation:
        prompt = f"""You are a funding assistant chatbot.

Below is a prior recommendation you gave based on public funding data:
---
{st.session_state.last_recommendation}
---

The user now asks a follow-up:
\"{query}\"

Rules:
- Only use information from the recommendation text above.
- If a field like contact or URL was not included, reply that it was not available in the data.
- Do not make up or guess email addresses or contact info.
- You can suggest visiting the official URL only if it was explicitly listed in the previous answer.

Respond clearly and concisely, using markdown if helpful."""
        with st.chat_message("assistant"):
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content.strip()
            st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
    else:
        with st.spinner("🔍 Finding matching programs..."):
            results = query_funding_data(query)

        if not results:
            st.error("No matching funding programs found.")
        else:
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                prompt = build_gpt_prompt(query, results)
                response = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    stream=True
                )
                for chunk in response:
                    if chunk.choices and getattr(chunk.choices[0].delta, "content", None):
                        token = chunk.choices[0].delta.content
                        full_response += token
                        message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)

            st.session_state.last_recommendation = full_response
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})

            sources = extract_sources_from_response(full_response)
            source = ", ".join(sorted(sources)) or "Unknown"
            rec_count = len(re.findall(r"^\s*\d+\.\s", full_response, flags=re.MULTILINE)) or len(results)
            save_query_to_postgres(query, source, rec_count, full_response)

# ✅ Always show Generate Draft Buttons if a GPT recommendation exists
if st.session_state.last_recommendation:
    funding_blocks = re.split(r"\n(?=\d+\.\s)", st.session_state.last_recommendation.strip())
    for idx, block in enumerate(funding_blocks):
        if st.button(f"📝 Generate Draft for Funding {idx + 1}", key=f"draft_{idx}"):
            st.info("Generating draft document...")

            def extract_field(pattern):
                match = re.search(pattern, block, re.DOTALL)
                return match.group(1).strip() if match else None

            metadata = {}
            for field, pattern in {
                "name": r"\d+\.\s+(.+?)\s*\(",
                "domain": r"\*\*Domain\*\*: (.+)",
                "eligibility": r"\*\*Eligibility\*\*: (.+)",
                "amount": r"\*\*Amount\*\*: (.+)",
                "deadline": r"\*\*Deadline\*\*: (.+)",
                "location": r"\*\*Location\*\*: (.+)",
                "contact": r"\*\*Contact\*\*: (.+)",
                "procedure": r"\*\*Next Steps\*\*:(.+)"
            }.items():
                value = extract_field(pattern)
                if value and value.lower() != "not specified" and "information not found" not in value.lower():
                    metadata[field] = value

            profile = {
                "company_name": "RoboAI Solutions",
                "location": "Rhineland-Palatinate, Germany",
                "industry": "AI-based Robotics",
                "goals": "Develop intelligent control systems for industrial robots",
                "project_idea": "Advanced AI-based Robotic Systems for Automation",
                "funding_need": "€200,000 for research and prototyping"
            }

            docx_data = generate_funding_draft(metadata, profile, client)

            st.session_state["suppress_query"] = True  # ✅ Prevent re-querying

            st.download_button(
                label="📄 Download Draft (.docx)",
                data=docx_data,
                file_name=f"draft_funding_{idx + 1}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
