# import os
# import re
# import uuid
# import hashlib
# import fitz  # PyMuPDF
# import streamlit as st
# from datetime import datetime

# from config import OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENV, get_openai_client
# from rag_core import query_funding_data
# from utils import present, program_name
# from docx_generator import generate_funding_draft
# from memory import save_query_to_postgres, get_recent_queries, clear_all_queries
# from gpt_recommender import build_gpt_prompt, extract_sources_from_response

# # ------------------ Setup ------------------
# st.set_page_config(page_title="Smart Funding Finder", layout="centered")
# client = get_openai_client()

# # ------------------ ENV Check ------------------
# missing_keys = [k for k, v in {
#     "OPENAI_API_KEY": OPENAI_API_KEY,
#     "PINECONE_API_KEY": PINECONE_API_KEY,
#     "PINECONE_ENV": PINECONE_ENV,
# }.items() if not v]
# if missing_keys:
#     st.error(f"Missing environment variables: {', '.join(missing_keys)}")
#     st.stop()

# # ------------------ Session Init ------------------
# for key in ["chat_history", "last_recommendation", "pdf_summary_query", "pdf_hash", "pending_query"]:
#     if key not in st.session_state:
#         st.session_state[key] = None if key != "chat_history" else []

# # ------------------ Sidebar: PDF Upload + Reset ------------------
# if "file_uploader_key" not in st.session_state:
#     st.session_state["file_uploader_key"] = "default_uploader"

# st.sidebar.subheader("📄 Upload Company Profile (Optional)")
# uploaded_pdf = st.sidebar.file_uploader("Upload PDF", type=["pdf"], key=st.session_state["file_uploader_key"])

# if uploaded_pdf:
#     pdf_bytes = uploaded_pdf.getvalue()
#     pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
#     if st.session_state.pdf_hash != pdf_hash:
#         st.session_state.pdf_hash = pdf_hash
#         doc = fitz.open(stream=pdf_bytes, filetype="pdf")
#         full_text = "\n".join(page.get_text() for page in doc).strip()[:6000]
#         prompt = f"""Summarize the company profile into 2–3 lines for public funding discovery.\nFocus on domain, goals, and funding need.\n---\n{full_text}\n---"""
#         response = client.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[{"role": "user", "content": prompt}]
#         )
#         st.session_state.pdf_summary_query = response.choices[0].message.content.strip()
#         st.sidebar.success("✅ Summary generated from PDF.")

# st.sidebar.markdown("---")
# st.sidebar.subheader("🧠 Chat Options")
# if st.sidebar.button("🔄 Reset Conversation"):
#     for key in [
#         "chat_history", "last_recommendation", "pdf_summary_query",
#         "pending_query", "pdf_hash", "uploaded_pdf", "suppress_query"
#     ]:
#         st.session_state.pop(key, None)
#     st.session_state["file_uploader_key"] = str(uuid.uuid4())
#     st.rerun()

# # ------------------ Header ------------------
# st.title("🎯 AI Grant Finder")

# # ------------------ History Viewer ------------------
# with st.expander("🕒 Past Queries History (Last 20)"):

#     if st.button("🧈 Clear History"):
#         clear_all_queries()
#         st.session_state["suppress_query"] = True  # ✅ Prevent re-querying
#         st.success("History cleared.")
#         st.rerun()

#     # ✅ Divider below the button (not inside the loop)
#     st.markdown("---")

#     recent = get_recent_queries(limit=20)
#     if not recent:
#         st.info("No queries saved yet.")
#     else:
#         for q in recent:
#             try:
#                 timestamp = datetime.fromisoformat(str(q['timestamp'])).astimezone()
#                 formatted_time = timestamp.strftime("%d %B %Y — %H:%M")
#             except Exception:
#                 formatted_time = str(q['timestamp'])
#             st.markdown(f"📅 **{formatted_time}**")
#             st.markdown(f"🔍 **{q['query'][:200]}**")
#             st.markdown(f"📦 **Source**: `{q['source']}` | 📈 **Results**: `{q['result_count']}`")
#             with st.expander("🗞 GPT Recommendation"):
#                 st.markdown(q['recommendation'])
#                 st.markdown("---")

# # ------------------ Chat Input + Display ------------------
# user_text_input = st.chat_input("Describe your company or ask follow up questions...")

# # ✅ Clear suppress flag if user enters a new message
# if user_text_input:
#     st.session_state.pop("suppress_query", None)

# query = user_text_input or st.session_state.pdf_summary_query
# st.session_state.pending_query = query

# # ✅ Block GPT rerun if draft/download is triggered
# if any(k.startswith("draft_") and st.session_state.get(k) for k in st.session_state.keys()) or st.session_state.get("suppress_query"):
#     query = None

# # ✅ Display chat history
# for msg in st.session_state.chat_history:
#     with st.chat_message(msg["role"]):
#         st.markdown(msg["content"])

# # ✅ Run GPT if valid new query
# if query:
#     with st.chat_message("user"):
#         st.markdown(query)
#     st.session_state.chat_history.append({"role": "user", "content": query})

#     if st.session_state.last_recommendation:
#         prompt = f"""You are a funding assistant chatbot.

# Below is a prior recommendation you gave based on public funding data:
# ---
# {st.session_state.last_recommendation}
# ---

# The user now asks a follow-up:
# \"{query}\"

# Rules:
# - Only use information from the recommendation text above.
# - If a field like contact or URL was not included, reply that it was not available in the data.
# - Do not make up or guess email addresses or contact info.
# - You can suggest visiting the official URL only if it was explicitly listed in the previous answer.

# Respond clearly and concisely, using markdown if helpful."""
#         with st.chat_message("assistant"):
#             response = client.chat.completions.create(
#                 model="gpt-4-turbo",
#                 messages=[{"role": "user", "content": prompt}]
#             )
#             answer = response.choices[0].message.content.strip()
#             st.markdown(answer)
#             st.session_state.chat_history.append({"role": "assistant", "content": answer})
#     else:
#         with st.spinner("🔍 Finding matching programs..."):
#             results = query_funding_data(query)

#         if not results:
#             st.error("No matching funding programs found.")
#         else:
#             with st.chat_message("assistant"):
#                 message_placeholder = st.empty()
#                 full_response = ""
#                 prompt = build_gpt_prompt(query, results)
#                 response = client.chat.completions.create(
#                     model="gpt-4-turbo",
#                     messages=[{"role": "user", "content": prompt}],
#                     stream=True
#                 )
#                 for chunk in response:
#                     if chunk.choices and getattr(chunk.choices[0].delta, "content", None):
#                         token = chunk.choices[0].delta.content
#                         full_response += token
#                         message_placeholder.markdown(full_response + "▌")
#                 message_placeholder.markdown(full_response)

#             st.session_state.last_recommendation = full_response
#             st.session_state["rendered_draft_buttons"] = False
#             st.session_state.chat_history.append({"role": "assistant", "content": full_response})

#             sources = extract_sources_from_response(full_response)
#             source = ", ".join(sorted(sources)) or "Unknown"
#             rec_count = len(re.findall(r"^#+\s*\d+\.\s", full_response, flags=re.MULTILINE)) or len(results)
#             save_query_to_postgres(query, source, rec_count, full_response)

# # ✅ Always show Generate Draft Buttons if a GPT recommendation exists
# if st.session_state.last_recommendation:
#     funding_blocks = re.split(r"\n(?=#+\s*\d+\.\s)", st.session_state.last_recommendation.strip())
#     st.markdown("### 📝 Draft Your Application")
#     for idx, block in enumerate(funding_blocks):
#         if st.button(f"📝 Generate Draft for Funding {idx + 1}", key=f"draft_{idx}"):
#             st.info("Generating draft document...") 

#             def extract_field(pattern):
#                 match = re.search(pattern, block, re.DOTALL)
#                 return match.group(1).strip() if match else None

#             metadata = {}
#             for field, pattern in {
#                 "name": r"#*\s*\d+\.\s+(.+?)\s*\(",
#                 "domain": r"\*\*Domain\*\*: (.+)",
#                 "eligibility": r"\*\*Eligibility\*\*: (.+)",
#                 "amount": r"\*\*Amount\*\*: (.+)",
#                 "deadline": r"\*\*Deadline\*\*: (.+)",
#                 "location": r"\*\*Location\*\*: (.+)",
#                 "contact": r"\*\*Contact\*\*: (.+)",
#                 "procedure": r"\*\*Next Steps\*\*:(.+)"
#             }.items():
#                 value = extract_field(pattern)
#                 if value and value.lower() != "not specified" and "information not found" not in value.lower():
#                     metadata[field] = value

#             profile = {
#                 "company_name": "RoboAI Solutions",
#                 "location": "Rhineland-Palatinate, Germany",
#                 "industry": "AI-based Robotics",
#                 "goals": "Develop intelligent control systems for industrial robots",
#                 "project_idea": "Advanced AI-based Robotic Systems for Automation",
#                 "funding_need": "€200,000 for research and prototyping"
#             }

#             docx_data = generate_funding_draft(metadata, profile, client)

#             st.session_state["suppress_query"] = True  # ✅ Prevent re-querying

#             st.download_button(
#                 label="📄 Download Draft (.docx)",
#                 data=docx_data,
#                 file_name=f"draft_funding_{idx + 1}.docx",
#                 mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
#             )

import os
import re
import uuid
import hashlib
import asyncio
import fitz  # PyMuPDF
import streamlit as st
from datetime import datetime
from config import OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENV, get_openai_client
from rag_core import query_funding_data
from utils import present, program_name
from docx_generator import generate_funding_draft
from memory import save_query_to_postgres, get_recent_queries, clear_all_queries
from gpt_recommender import build_gpt_prompt, extract_sources_from_response

# Import new comprehensive search module
from expanded_dynamic_search import get_comprehensive_funding_results, ExpandedFundingSearcher
from modern_styles import apply_modern_styling, create_modern_header, create_feature_box, create_funding_card
from clarifying_questions import ClarifyingQuestionsManager, display_funding_questions_ui, display_draft_questions_ui

# ------------------ Setup ------------------
st.set_page_config(
    page_title="🎯 AI Grant Finder", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply modern styling
apply_modern_styling()

client = get_openai_client()
questions_manager = ClarifyingQuestionsManager()

# ------------------ ENV Check ------------------
missing_keys = [k for k, v in {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "PINECONE_API_KEY": PINECONE_API_KEY,
    "PINECONE_ENV": PINECONE_ENV,
}.items() if not v]

if missing_keys:
    st.error(f"Missing environment variables: {', '.join(missing_keys)}")
    st.stop()

# ------------------ Session State Init ------------------
for key in [
    "chat_history", "last_recommendation", "pdf_summary_query", 
    "pdf_hash", "pending_query", "search_method", "ask_clarifying_questions",
    "current_funding_questions", "current_draft_questions", "enhanced_query",
    "waiting_for_clarification"
]:
    if key not in st.session_state:
        if key == "chat_history":
            st.session_state[key] = []
        elif key == "search_method":
            st.session_state[key] = "🚀 Comprehensive Search (20+ sources)"
        elif key == "ask_clarifying_questions":
            st.session_state[key] = True
        else:
            st.session_state[key] = None

# ------------------ Sidebar Configuration ------------------
st.sidebar.title("⚙️ Settings")

if "file_uploader_key" not in st.session_state:
    st.session_state["file_uploader_key"] = "default_uploader"

# Search method selection
st.sidebar.markdown("### 🔍 Search Options")
search_option = st.sidebar.radio(
    "Choose search method:",
    [
        "🚀 Comprehensive Search (20+ sources)",
        "💾 Database Search (fastest)",
    ],
    index=0,
    help="Comprehensive search covers EU, federal, regional, and private funding"
)

# Store search preference
st.session_state.search_method = search_option

st.sidebar.markdown("---")

# PDF Upload Section
st.sidebar.markdown("### 📄 Company Profile Upload")
uploaded_pdf = st.sidebar.file_uploader(
    "Upload PDF Profile (Optional)", 
    type=["pdf"], 
    key=st.session_state["file_uploader_key"]
)

if uploaded_pdf:
    pdf_bytes = uploaded_pdf.getvalue()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    
    if st.session_state.pdf_hash != pdf_hash:
        st.session_state.pdf_hash = pdf_hash
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = "\n".join(page.get_text() for page in doc).strip()[:6000]
        
        with st.spinner("Processing PDF..."):
            prompt = f"""Summarize this company profile into 2–3 lines for funding search.\nFocus on domain, goals, and funding needs.\n---\n{full_text}\n---"""
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            st.session_state.pdf_summary_query = response.choices[0].message.content.strip()
        
        st.sidebar.success("✅ PDF processed!")
        st.sidebar.text_area("Extracted Summary:", st.session_state.pdf_summary_query, height=100)

st.sidebar.markdown("---")

# Reset and Clear Options
st.sidebar.markdown("### 🔄 Actions")

# col1, col2 = st.sidebar.columns(2)
# with col1:
if st.button("🆕 Reset Chat", type="secondary"):
    for key in [
        "chat_history", "last_recommendation", "pdf_summary_query",
        "pending_query", "pdf_hash", "enhanced_query", "waiting_for_clarification"
    ]:
        st.session_state.pop(key, None)
    st.session_state.chat_history = []
    st.session_state["file_uploader_key"] = str(uuid.uuid4())
    st.rerun()

# with col2:
#     if st.button("🗑️ Clear History", type="secondary"):
#         clear_all_queries()
#         st.sidebar.success("History cleared!")

# ------------------ Main Header ------------------
create_modern_header(
    "🎯 AI Grant Finder", 
    "Discover the perfect funding opportunities for your AI and robotics projects"
)

# ------------------ Feature Highlights ------------------
col1, col2, col3 = st.columns(3)

with col1:
    create_feature_box(
        "🔍", 
        "Comprehensive Search", 
        "Search across 20+ funding sources: EU, federal, regional, and private funding"
    )

with col2:
    create_feature_box(
        "🤖", 
        "AI-Powered Matching", 
        "Intelligent ranking and filtering based on your specific needs and location"
    )

with col3:
    create_feature_box(
        "📝", 
        "Draft Generation", 
        "Automated application drafts tailored to specific funding programs"
    )

# ------------------ Chat History Display ------------------
with st.expander("🕒 Recent Queries History", expanded=False):
    if st.button("🧹 Clear All History", key="clear_history_expanded"):
        clear_all_queries()
        st.success("All history cleared!")
        st.rerun()
    
    st.markdown("---")
    recent_queries = get_recent_queries(limit=10)
    
    if not recent_queries:
        st.info("No previous queries found.")
    else:
        for i, q in enumerate(recent_queries):
            with st.container():
                try:
                    timestamp = datetime.fromisoformat(str(q['timestamp']))
                    formatted_time = timestamp.strftime("%B %d, %Y at %H:%M")
                except:
                    formatted_time = str(q['timestamp'])
                
                st.markdown(f"**📅 {formatted_time}**")
                st.markdown(f"**Query:** {q['query'][:150]}{'...' if len(q['query']) > 150 else ''}")
                st.markdown(f"**Source:** `{q['source']}` | **Results:** `{q['result_count']}`")
                
                with st.expander(f"View Recommendation #{i+1}"):
                    st.markdown(q['recommendation'])
                
                st.markdown("---")

# ------------------ Main Chat Interface ------------------
st.markdown("### 💬 Chat with AI Grant Finder")

# Handle clarifying questions workflow
if st.session_state.get("waiting_for_clarification") == "funding":
    st.markdown("### 🤔 Let me ask a few questions to find better matches:")
    
    questions = st.session_state.get("current_funding_questions", [])
    if questions:
        answers = {}
        
        for i, q_data in enumerate(questions):
            question = q_data['question']
            category = q_data['category']
            options = q_data.get('options', [])
            
            if options:
                answer = st.selectbox(
                    question,
                    ["Select an option..."] + options,
                    key=f"clarify_funding_{i}_{category}"
                )
                if answer != "Select an option...":
                    answers[category] = answer
            else:
                answer = st.text_input(question, key=f"clarify_funding_{i}_{category}")
                if answer.strip():
                    answers[category] = answer.strip()

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Main chat input
user_input = st.chat_input("Describe your company or ask follow-up questions...")

# Handle new user input or enhanced query
query_to_process = None
if user_input:
    st.session_state.pop("suppress_query", None)
    query_to_process = user_input
elif st.session_state.enhanced_query and not st.session_state.get("enhanced_processed"):
    query_to_process = st.session_state.enhanced_query
    st.session_state.enhanced_processed = True
elif st.session_state.pdf_summary_query and not st.session_state.get("pdf_processed"):
    query_to_process = st.session_state.pdf_summary_query
    st.session_state.pdf_processed = True

# Block processing if waiting for clarification or if suppress flag is set
if st.session_state.get("waiting_for_clarification") or st.session_state.get("suppress_query"):
    query_to_process = None

# Process the query
if query_to_process and not st.session_state.get("waiting_for_clarification"):
    # Add user message to chat
    with st.chat_message("user"):
        st.markdown(query_to_process)
    st.session_state.chat_history.append({"role": "user", "content": query_to_process})
    
    # Handle follow-up questions to existing recommendation
    if st.session_state.last_recommendation and user_input:  # Only for new user input, not enhanced queries
        follow_up_prompt = f"""You are a funding assistant chatbot.
        
Previous recommendation you gave:
---
{st.session_state.last_recommendation}
---

User follow-up question: "{user_input}"

Rules:
- Only use information from the previous recommendation
- If information wasn't provided, say it wasn't available
- Don't make up contact info or details
- Suggest visiting official URLs only if they were listed

Respond clearly and helpfully:"""
        
        with st.chat_message("assistant"):
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": follow_up_prompt}]
            )
            answer = response.choices[0].message.content.strip()
            st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
    
    else:
        # Check if we should ask clarifying questions
        if st.session_state.ask_clarifying_questions and questions_manager.should_ask_funding_questions(query_to_process):
            st.session_state.original_query = query_to_process
            st.session_state.current_funding_questions = questions_manager.generate_funding_questions(query_to_process)
            st.session_state.waiting_for_clarification = "funding"
            st.rerun()
        
        # Perform funding search based on selected method
        with st.spinner("🔍 Searching for funding opportunities..."):
            search_method = st.session_state.get("search_method", "💾 Database Search (fastest)")
            
            if "Comprehensive Search" in search_method:
                # Use new comprehensive search (20+ sources)
                try:
                    results = asyncio.run(get_comprehensive_funding_results(query_to_process, max_results=12))
                    search_method_display = "Comprehensive Search (20+ sources)"
                except Exception as e:
                    st.warning(f"Comprehensive search failed: {e}. Using database search.")
                    results = query_funding_data(query_to_process)
                    search_method_display = "Database Search (fallback)"
            
            elif "Dynamic Search" in search_method:
                # Use original dynamic search (3 sources) - fallback to database if not available
                try:
                    from dynamic_search import get_dynamic_funding_results
                    results = asyncio.run(get_dynamic_funding_results(query_to_process, max_results=8))
                    search_method_display = "Dynamic Search (3 original sources)"
                except Exception as e:
                    st.warning(f"Dynamic search not available: {e}. Using database search.")
                    results = query_funding_data(query_to_process)
                    search_method_display = "Database Search (fallback)"
            
            else:
                # Use existing database search (fastest)
                results = query_funding_data(query_to_process)
                search_method_display = "Database Search"
        
        if not results:
            with st.chat_message("assistant"):
                st.error("No matching funding programs found. Try a different query or enable comprehensive search.")
        else:
            # Generate GPT recommendation
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                prompt = build_gpt_prompt(query_to_process, results)
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
                
                # Add search method info
                st.info(f"🔍 Results found using: **{search_method_display}**")
            
            # Save recommendation and results
            st.session_state.last_recommendation = full_response
            st.session_state.last_results = results
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            
            # Save to database
            sources = extract_sources_from_response(full_response)
            source = ", ".join(sorted(sources)) or "Unknown"
            rec_count = len(results)
            save_query_to_postgres(query_to_process, f"{source} ({search_method_display})", rec_count, full_response)

# ------------------ Draft Generation Section ------------------
if st.session_state.last_recommendation:
    st.markdown("---")
    st.markdown("### 📝 Generate Application Drafts")
    
    # Parse funding programs from recommendation
    funding_blocks = re.split(r"\n(?=#+\s*\d+\.)", st.session_state.last_recommendation.strip())
    
    # Create columns for draft buttons
    cols = st.columns(min(len(funding_blocks), 3))
    
    for idx, block in enumerate(funding_blocks):
        if block.strip():
            col_idx = idx % 3
            with cols[col_idx]:
                program_name_match = re.search(r"#+\s*\d+\.\s+(.+?)\s*\(", block)
                program_name = program_name_match.group(1) if program_name_match else f"Program {idx + 1}"
                
                if st.button(f"📝 Draft for {program_name[:20]}...", key=f"draft_{idx}"):
                    # Extract program metadata
                    def extract_field(pattern):
                        match = re.search(pattern, block, re.DOTALL)
                        return match.group(1).strip() if match else None
                    
                    metadata = {}
                    for field, pattern in {
                        "name": r"#+\s*\d+\.\s+(.+?)\s*\(",
                        "domain": r"\*\*Domain\*\*:?\s*(.+)",
                        "eligibility": r"\*\*Eligibility\*\*:?\s*(.+)",
                        "amount": r"\*\*Amount\*\*:?\s*(.+)",
                        "deadline": r"\*\*Deadline\*\*:?\s*(.+)",
                        "location": r"\*\*Location\*\*:?\s*(.+)",
                        "contact": r"\*\*Contact\*\*:?\s*(.+)",
                    }.items():
                        value = extract_field(pattern)
                        if value and value.lower() not in ["not specified", "information not found"]:
                            metadata[field] = value
                    
                    # Generate draft directly if no questions needed
                    with st.spinner("🎯 Generating application draft..."):
                        profile = {
                            "company_name": "Your Company",
                            "location": "Germany",
                            "industry": "AI/Robotics",
                            "goals": "Innovation and research in AI technology",
                            "project_idea": query_to_process or "AI-based project",
                            "funding_need": "Research and development funding"
                        }
                        
                        # Use enhanced profile if available
                        if st.session_state.get("enhanced_profile"):
                            profile.update(st.session_state.enhanced_profile)
                        
                        try:
                            docx_data = generate_funding_draft(metadata, profile, client)
                            
                            st.success("✅ Draft generated successfully!")
                            st.download_button(
                                label=f"📄 Download {program_name[:15]}... Draft",
                                data=docx_data,
                                file_name=f"funding_draft_{idx + 1}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"download_{idx}"
                            )
                        except Exception as e:
                            st.error(f"Error generating draft: {e}")

# ------------------ Footer ------------------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <p>💡 <em>Now covering 20+ funding sources across EU, Federal, Regional & Private sectors</em></p>
    </div>
    """, 
    unsafe_allow_html=True
)