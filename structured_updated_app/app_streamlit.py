# ✅ app_streamlit.py with Follow-Up Support
import os
import re
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

# ------------------ Session ------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_recommendation" not in st.session_state:
    st.session_state.last_recommendation = None

# ------------------ PDF Upload ------------------
st.sidebar.subheader("\U0001F4C4 Upload Company Profile (Optional)")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF", type=["pdf"])


seed_query = ""

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc).strip()

def summarize_with_gpt(text: str) -> str:
    prompt = f"""Summarize the company profile into 2–3 lines for public funding discovery.
Focus on domain, goals, and funding need.

---
{text[:6000]}
---
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

if uploaded_pdf:
    pdf_bytes = uploaded_pdf.getvalue()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    if st.session_state.get("pdf_hash") != pdf_hash:
        st.session_state["pdf_hash"] = pdf_hash
        seed_query = summarize_with_gpt(extract_text_from_pdf(pdf_bytes))
        st.session_state["pdf_summary_query"] = seed_query
        st.sidebar.success("\u2705 Summary generated from PDF.")

# ------------------ Reset Conversation ------------------
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Chat Options")
if st.sidebar.button("🔄 Reset Conversation"):
    st.session_state["chat_history"] = []
    st.success("Conversation reset.")
    st.rerun()

# ------------------ Main UI ------------------
st.title("🤖 Smart AI Funding Finder")

# ------------------ History Viewer ------------------
with st.expander("🕘 Past Queries History (Last 20)"):
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

    if st.button("🪼 Clear History"):
        clear_all_queries()
        st.success("History cleared.")
        st.rerun()

# ------------------ Chat Input ------------------
# Get query from chat input or PDF summary
user_text_input = st.chat_input("Describe your company or project...")
pdf_summary = st.session_state.get("pdf_summary_query")

# Prefer user input, fallback to summary
query = user_text_input or pdf_summary

# Store query for later use
st.session_state["pending_query"] = query

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if query:
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.chat_history.append({"role": "user", "content": query})

    # ------------------ Follow-up mode ------------------
    if st.session_state.last_recommendation:
        prompt = f"""You are a funding assistant chatbot.

The user previously received this recommendation:

---
{st.session_state.last_recommendation}
---

Now they asked:
"{query}"

Please answer helpfully based on the programs shown above.
"""
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

            sources = extract_sources_from_response(full_response)
            source = ", ".join(sorted(sources)) or "Unknown"
            rec_count = len(re.findall(r"^\s*\d+\.\s", full_response, flags=re.MULTILINE)) or len(results)

            save_query_to_postgres(query, source, rec_count, full_response)
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            st.session_state.last_recommendation = full_response

            # --- Draft Generation UI ---
            # Split the GPT response into individual funding blocks
            funding_blocks = re.split(r'\n(?=\d+\.\s)', full_response.strip())  # Splits at 1. , 2. , 3. ...

            for idx, block in enumerate(funding_blocks):
                st.markdown("---")
                st.markdown(block.strip())

                if st.button(f"📝 Generate Draft for Funding {idx + 1}", key=f"draft_btn_{idx}"):
                    st.info("Generating draft document...")
                    
                    # Reconstruct basic metadata for the draft
                    program_metadata = {
                        "name": re.search(r"\d+\.\s+(.+?)\s\(", block).group(1) if re.search(r"\d+\.\s+(.+?)\s\(", block) else "Unknown Program",
                        "domain": re.search(r"\*\*Domain\*\*: (.+)", block).group(1) if re.search(r"\*\*Domain\*\*: (.+)", block) else "",
                        "eligibility": re.search(r"\*\*Eligibility\*\*: (.+)", block).group(1) if re.search(r"\*\*Eligibility\*\*: (.+)", block) else "",
                        "amount": re.search(r"\*\*Amount\*\*: (.+)", block).group(1) if re.search(r"\*\*Amount\*\*: (.+)", block) else "",
                        "deadline": re.search(r"\*\*Deadline\*\*: (.+)", block).group(1) if re.search(r"\*\*Deadline\*\*: (.+)", block) else "",
                        "location": re.search(r"\*\*Location\*\*: (.+)", block).group(1) if re.search(r"\*\*Location\*\*: (.+)", block) else "",
                        "contact": re.search(r"\*\*Contact\*\*: (.+)", block).group(1) if re.search(r"\*\*Contact\*\*: (.+)", block) else "",
                        "procedure": re.search(r"\*\*Next Steps\*\*:(.+)", block, re.DOTALL).group(1).strip() if re.search(r"\*\*Next Steps\*\*:(.+)", block, re.DOTALL) else "",
                    }

                    # Use either uploaded PDF summary or manual input query
                    final_query = st.session_state.get("pdf_summary_query") or query

                    # Generate .docx
                    docx_data = generate_funding_draft(program_metadata, final_query, client)

                    # Offer for download
                    st.download_button(
                        label="📄 Download Draft (.docx)",
                        data=docx_data,
                        file_name=f"draft_funding_{idx+1}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )