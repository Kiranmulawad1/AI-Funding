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
from clarifying_questions import ClarifyingQuestionsManager

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
    "waiting_for_clarification", "last_results", "show_draft_questions", 
    "follow_up_responses", "current_follow_up"  # Added current_follow_up
]:
    if key not in st.session_state:
        if key == "chat_history":
            st.session_state[key] = []
        elif key == "search_method":
            st.session_state[key] = "🚀 Comprehensive Search (20+ sources)"
        elif key == "ask_clarifying_questions":
            st.session_state[key] = True
        elif key == "show_draft_questions":
            st.session_state[key] = False
        elif key == "follow_up_responses":
            st.session_state[key] = []
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
        "📊 Original Sources Only (FDB, ISB, NRW)"
    ],
    index=0,
    help="Comprehensive search covers EU, federal, regional, and private funding"
)

# Store search preference
st.session_state.search_method = search_option

# Clarifying questions toggle with correct text
st.session_state.ask_clarifying_questions = st.sidebar.checkbox(
    "🧠 Enable Clarifying Questions", 
    value=st.session_state.ask_clarifying_questions,
    help="Allow AI to ask follow-up questions for better results"
)

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
# Only Reset Chat button in sidebar
if st.sidebar.button("🆕 Reset Chat", type="secondary", use_container_width=True):
    for key in [
        "chat_history", "last_recommendation", "pdf_summary_query",
        "pending_query", "pdf_hash", "enhanced_query", "waiting_for_clarification",
        "show_draft_questions", "follow_up_responses", "current_follow_up"
    ]:
        st.session_state.pop(key, None)
    st.session_state.chat_history = []
    st.session_state.follow_up_responses = []
    st.session_state["file_uploader_key"] = str(uuid.uuid4())
    st.rerun()

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
    recent_queries = get_recent_queries(limit=10)
    
    if not recent_queries:
        st.info("No previous queries found.")
    else:
        # Clear history button in main area only
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🧹 Clear All History", key="clear_history_main"):
                clear_all_queries()
                st.success("All history cleared!")
                st.rerun()
        
        st.markdown("---")
        
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

# Handle clarifying questions workflow for funding search only
if st.session_state.get("waiting_for_clarification") == "funding":
    # Show the original query that triggered questions
    original_query = st.session_state.get("original_query", "")
    st.info(f"💭 **Original query:** {original_query}")
    
    st.markdown("### 🤔 Let me ask a few questions to find better matches:")
    
    questions = st.session_state.get("current_funding_questions", [])
    if questions:
        answers = {}
        
        # Use columns to make it more compact
        for i, q_data in enumerate(questions):
            question = q_data['question']
            category = q_data['category']
            options = q_data.get('options', [])
            
            if options:
                # Store the current answer if it exists
                current_key = f"clarify_funding_{i}_{category}"
                current_value = st.session_state.get(current_key, "Select an option...")
                
                answer = st.selectbox(
                    question,
                    ["Select an option..."] + options,
                    index=0 if current_value == "Select an option..." else options.index(current_value) + 1 if current_value in options else 0,
                    key=current_key
                )
                if answer != "Select an option...":
                    answers[category] = answer
            else:
                answer = st.text_input(question, key=f"clarify_funding_{i}_{category}")
                if answer.strip():
                    answers[category] = answer.strip()
        
        # Show current answers summary
        if answers:
            st.success(f"✅ **Your answers:** {', '.join([f'{k}: {v}' for k, v in answers.items()])}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Search with Details", type="primary", key="search_with_details"):
                if answers:
                    original_query = st.session_state.get("original_query", "")
                    enhanced_query = questions_manager.process_funding_answers(original_query, answers)
                    
                    # Clear the waiting state and trigger search
                    st.session_state.waiting_for_clarification = None
                    st.session_state.enhanced_query = enhanced_query
                    st.session_state.enhanced_processed = False
                    
                    # Add the enhanced query to chat history immediately
                    with st.chat_message("user"):
                        st.markdown(enhanced_query)
                    st.session_state.chat_history.append({"role": "user", "content": enhanced_query})
                    
                    st.rerun()
                else:
                    st.warning("Please answer at least one question.")
        
        with col2:
            if st.button("⏭️ Skip Questions", type="secondary", key="skip_questions"):
                # Use original query without enhancement
                original_query = st.session_state.get("original_query", "")
                
                st.session_state.waiting_for_clarification = None
                st.session_state.enhanced_query = original_query
                st.session_state.enhanced_processed = False
                
                # Add the original query to chat history
                with st.chat_message("user"):
                    st.markdown(original_query)
                st.session_state.chat_history.append({"role": "user", "content": original_query})
                
                st.rerun()
    
    # Don't show the rest of the interface while waiting for funding clarification
    st.stop()

# Display chat history (excluding follow-up questions that will be shown at bottom)
for msg in st.session_state.chat_history:
    # Skip follow-up questions that are stored in follow_up_responses
    is_follow_up_question = False
    if msg["role"] == "user" and st.session_state.get("follow_up_responses"):
        for follow_up in st.session_state.follow_up_responses:
            if msg["content"] == follow_up["question"]:
                is_follow_up_question = True
                break
    
    # Also skip current follow-up question
    if (msg["role"] == "user" and st.session_state.get("current_follow_up") and 
        msg["content"] == st.session_state.current_follow_up["question"]):
        is_follow_up_question = True
    
    # Only display if it's not a follow-up question
    if not is_follow_up_question:
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
    # Check if this is a follow-up question to existing recommendation
    is_follow_up = (st.session_state.last_recommendation and 
                   user_input and 
                   not st.session_state.enhanced_query and
                   len(query_to_process.split()) < 15)
    
    # Add user message to chat ONLY if it's NOT a follow-up (to prevent duplication)
    if user_input and not st.session_state.enhanced_query and not is_follow_up:
        with st.chat_message("user"):
            st.markdown(query_to_process)
        st.session_state.chat_history.append({"role": "user", "content": query_to_process})
    elif user_input and not st.session_state.enhanced_query and is_follow_up:
        # For follow-ups, add to chat history but prepare for streaming
        # This will be displayed later when we stream the response
        with st.chat_message("user"):
            st.markdown(query_to_process)
        st.session_state.chat_history.append({"role": "user", "content": query_to_process})
    elif not user_input:
        # For enhanced queries or PDF queries, add to chat normally
        with st.chat_message("user"):
            st.markdown(query_to_process)
        st.session_state.chat_history.append({"role": "user", "content": query_to_process})
    
    if is_follow_up:
        # 🎯 NEW: Store follow-up for streaming instead of immediate processing
        follow_up_prompt = f"""You are a funding assistant chatbot.
        
Previous recommendation you gave:
---
{st.session_state.last_recommendation}
---
User follow-up question: "{query_to_process}"
Rules:
- Only use information from the previous recommendation
- If information wasn't provided, say it wasn't available
- Don't make up contact info or details
- Suggest visiting official URLs only if they were listed
Respond clearly and helpfully:"""
        
        # Store the question and mark for streaming display
        st.session_state.current_follow_up = {
            "question": query_to_process,
            "prompt": follow_up_prompt,
            "streaming": True
        }
        
        # Clear any draft questions that might be showing
        st.session_state.show_draft_questions = False
        
    else:
        # Handle new search query
        # Clear follow-up responses for new search
        st.session_state.follow_up_responses = []
        
        # Check if we should ask clarifying questions (only for new user input)
        if (user_input and not st.session_state.enhanced_query and 
            st.session_state.ask_clarifying_questions and 
            questions_manager.should_ask_funding_questions(query_to_process)):
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
            
            elif "Original Sources Only" in search_method:
                # Use original 3 sources only (FDB, ISB, NRW) - fallback to database if not available
                try:
                    from dynamic_search import get_dynamic_funding_results
                    results = asyncio.run(get_dynamic_funding_results(query_to_process, max_results=8))
                    search_method_display = "Original Sources Only (FDB, ISB, NRW)"
                except Exception as e:
                    st.warning(f"Original sources search not available: {e}. Using database search.")
                    results = query_funding_data(query_to_process)
                    search_method_display = "Database Search (fallback)"
            
            else:
                # Use existing database search (fastest)
                results = query_funding_data(query_to_process)
                search_method_display = "Database Search"
        
        if not results:
            with st.chat_message("assistant"):
                st.error("No matching funding programs found. Try a different query or check your search settings.")
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
                
                # Show enhanced query info if it was used
                if st.session_state.enhanced_query:
                    st.success(f"✅ Enhanced search completed!")
            
            # Save recommendation and results
            st.session_state.last_recommendation = full_response
            st.session_state.last_results = results
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            
            # Save to database
            sources = extract_sources_from_response(full_response)
            source = ", ".join(sorted(sources)) or "Unknown"
            rec_count = len(results)
            save_query_to_postgres(query_to_process, f"{source} ({search_method_display})", rec_count, full_response)
            
            # Clear the enhanced query so it doesn't get processed again
            st.session_state.enhanced_query = None

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
                    
                    # Store the selected program for potential clarifying questions
                    st.session_state.selected_funding_program = metadata
                    st.session_state.selected_program_idx = idx
                    st.session_state.selected_program_name = program_name
                    
                    # Check if we should ask clarifying questions for draft
                    if st.session_state.ask_clarifying_questions:
                        original_query = st.session_state.get("original_query", query_to_process or "")
                        if questions_manager.should_ask_draft_questions(metadata, original_query):
                            st.session_state.current_draft_questions = questions_manager.generate_draft_questions(metadata, original_query)
                            st.session_state.show_draft_questions = True
                            # Don't rerun, just set the flag so questions show below
                        else:
                            # No questions needed, generate directly
                            with st.spinner("🎯 Generating application draft..."):
                                profile = {
                                    "company_name": "Your Company",
                                    "location": "Germany",
                                    "industry": "AI/Robotics",
                                    "goals": "Innovation and research in AI technology",
                                    "project_idea": query_to_process or "AI-based project",
                                    "funding_need": "Research and development funding"
                                }
                                
                                try:
                                    docx_data = generate_funding_draft(metadata, profile, client)
                                    st.success("✅ Draft generated successfully!")
                                    st.download_button(
                                        label=f"📄 Download {program_name[:15]}... Draft",
                                        data=docx_data,
                                        file_name=f"funding_draft_{idx + 1}.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        key=f"download_direct_{idx}"
                                    )
                                except Exception as e:
                                    st.error(f"Error generating draft: {e}")
                    else:
                        # Clarifying questions disabled, generate directly
                        with st.spinner("🎯 Generating application draft..."):
                            profile = {
                                "company_name": "Your Company",
                                "location": "Germany",
                                "industry": "AI/Robotics", 
                                "goals": "Innovation and research in AI technology",
                                "project_idea": query_to_process or "AI-based project",
                                "funding_need": "Research and development funding"
                            }
                            
                            try:
                                docx_data = generate_funding_draft(metadata, profile, client)
                                st.success("✅ Draft generated successfully!")
                                st.download_button(
                                    label=f"📄 Download {program_name[:15]}... Draft",
                                    data=docx_data,
                                    file_name=f"funding_draft_{idx + 1}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_basic_{idx}"
                                )
                            except Exception as e:
                                st.error(f"Error generating draft: {e}")

    # Show clarifying questions inline if enabled and triggered
    if st.session_state.get("show_draft_questions"):
        st.markdown("---")
        program_name = st.session_state.get("selected_program_name", "the selected program")
        st.markdown(f"### 🤔 Let me ask a few questions for a better application draft for **{program_name}**:")
        
        questions = st.session_state.get("current_draft_questions", [])
        funding_program = st.session_state.get("selected_funding_program", {})
        program_idx = st.session_state.get("selected_program_idx", 0)
        
        if questions:
            answers = {}
            
            for i, q_data in enumerate(questions):
                question = q_data['question']
                category = q_data['category']
                question_type = q_data.get('type', 'text')
                
                if question_type == 'select' and 'options' in q_data:
                    answer = st.selectbox(
                        question,
                        ["Select an option..."] + q_data['options'],
                        key=f"clarify_draft_{program_idx}_{i}_{category}"
                    )
                    if answer != "Select an option...":
                        answers[category] = answer
                else:
                    answer = st.text_area(
                        question,
                        height=100,
                        key=f"clarify_draft_{program_idx}_{i}_{category}"
                    )
                    if answer.strip():
                        answers[category] = answer.strip()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Enhanced Draft button
                if st.button("📄 Enhanced Draft", type="primary", key=f"enhanced_draft_btn_{program_idx}"):
                    if answers:
                        with st.spinner("🎯 Generating enhanced application draft..."):
                            try:
                                # Process answers into enhanced profile
                                original_query = st.session_state.get("original_query", "")
                                enhanced_profile = questions_manager.process_draft_answers(
                                    original_query, funding_program, answers
                                )
                                
                                # Base profile with enhancements
                                profile = {
                                    "company_name": "Your Company",
                                    "location": "Germany",
                                    "industry": "AI/Robotics",
                                    "goals": "Innovation and research in AI technology",
                                    "project_idea": original_query,
                                    "funding_need": "Research and development funding"
                                }
                                profile.update(enhanced_profile)
                                
                                # Generate draft
                                docx_data = generate_funding_draft(funding_program, profile, client)
                                
                                # Clear questions display
                                st.session_state.show_draft_questions = False
                                
                                st.success("✅ Enhanced draft generated successfully!")
                                st.download_button(
                                    label=f"📄 Download Enhanced Draft for {program_name}",
                                    data=docx_data,
                                    file_name=f"enhanced_draft_{program_name.replace(' ', '_')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_enhanced_draft_{program_idx}"
                                )
                                
                            except Exception as e:
                                st.error(f"Error generating enhanced draft: {e}")
                    else:
                        st.warning("Please answer at least one question for enhanced draft.")
            
            with col2:
                # Basic Draft button
                if st.button("📝 Basic Draft", type="secondary", key=f"basic_draft_btn_{program_idx}"):
                    with st.spinner("🎯 Generating basic application draft..."):
                        try:
                            # Use basic profile
                            original_query = st.session_state.get("original_query", "")
                            profile = {
                                "company_name": "Your Company",
                                "location": "Germany", 
                                "industry": "AI/Robotics",
                                "goals": "Innovation and research in AI technology",
                                "project_idea": original_query,
                                "funding_need": "Research and development funding"
                            }
                            
                            # Generate draft
                            docx_data = generate_funding_draft(funding_program, profile, client)
                            
                            # Clear questions display
                            st.session_state.show_draft_questions = False
                            
                            st.success("✅ Basic draft generated successfully!")
                            st.download_button(
                                label=f"📄 Download Basic Draft for {program_name}",
                                data=docx_data,
                                file_name=f"basic_draft_{program_name.replace(' ', '_')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"download_basic_draft_{program_idx}"
                            )
                            
                        except Exception as e:
                            st.error(f"Error generating basic draft: {e}")
            
            with col3:
                # Back button to hide questions
                if st.button("⬅️ Back to Drafts", type="secondary", key=f"back_to_drafts_{program_idx}"):
                    st.session_state.show_draft_questions = False
                    st.rerun()

# ------------------ 🎯 STREAM FOLLOW-UP RESPONSE AFTER DRAFT BUTTONS ------------------
# Stream follow-up responses at the bottom after draft generation section
if st.session_state.get("current_follow_up") and st.session_state.current_follow_up.get("streaming"):
    st.markdown("---")
    current_followup = st.session_state.current_follow_up
    
    # Show the follow-up question first (at bottom)
    with st.chat_message("user"):
        st.markdown(current_followup["question"])
    
    # Stream the follow-up response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": current_followup["prompt"]}],
            stream=True
        )
        
        for chunk in response:
            if chunk.choices and getattr(chunk.choices[0].delta, "content", None):
                token = chunk.choices[0].delta.content
                full_response += token
                message_placeholder.markdown(full_response + "▌")
        
        message_placeholder.markdown(full_response)
    
    # Store the follow-up Q&A for future display (but don't add to main chat history)
    st.session_state.follow_up_responses.append({
        "question": current_followup["question"],
        "answer": full_response
    })
    
    # Clear current follow-up
    st.session_state.current_follow_up = None
    
    # Rerun to show the completed response properly
    st.rerun()

# ------------------ Display Previous Follow-up Q&A After Draft Buttons ------------------
# This achieves the flow: query -> recommendation -> generate buttons -> follow-up Q&A
if st.session_state.get("follow_up_responses") and not st.session_state.get("current_follow_up"):
    st.markdown("---")
    for i, follow_up in enumerate(st.session_state.follow_up_responses):
        with st.chat_message("user"):
            st.markdown(follow_up["question"])
        with st.chat_message("assistant"):
            st.markdown(follow_up["answer"])

# ------------------ Footer ------------------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <p>🎯 <strong>AI Grant Finder</strong> - Powered by OpenAI & Comprehensive Search</p>
        <p>💡 <em>Now covering 20+ funding sources across EU, Federal, Regional & Private sectors</em></p>
    </div>
    """, 
    unsafe_allow_html=True
)

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
