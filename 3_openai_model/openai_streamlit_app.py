import os
import re
import pandas as pd
import fitz  # PyMuPDF
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from dateutil import parser
from pinecone import Pinecone
from openai import OpenAI
import numpy as np

# --- Setup and config ---

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV")
assert OPENAI_API_KEY and PINECONE_API_KEY and PINECONE_ENV

# Load data
full_df = pd.read_csv("/Users/kiranmulawad/AI-Funding/2_preprocessing/data/merged_funding_data.csv")

# Pinecone + OpenAI init
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
index = pc.Index("funding-search")  # <-- use your OpenAI-embedding Pinecone index

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Streamlit layout ---

st.set_page_config(page_title="AI Funding Finder", layout="wide")
st.title("💸 AI Funding Finder (OpenAI Edition)")
st.markdown("Discover relevant public funding in Germany for your AI or robotics project.")

input_method = st.sidebar.radio("Input Method", ["Type Description", "Upload PDF"])
profile_text = ""
user_location = ""

if input_method == "Type Description":
    profile_text = st.text_area("📝 Describe your company/project", height=250)
    user_location = st.text_input("🌍 Enter your location (optional)", value="Rhineland-Palatinate")
elif input_method == "Upload PDF":
    uploaded_pdf = st.file_uploader("📄 Upload your company profile (PDF)", type="pdf")
    if uploaded_pdf:
        doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
        profile_text = "\n".join(page.get_text() for page in doc)
        st.text_area("📄 Extracted PDF Text", profile_text, height=300)
        location_match = re.search(r"Location:\s*(.+)", profile_text)
        user_location = location_match.group(1).strip() if location_match else "Unknown"

if st.button("🔍 Find Grants") and profile_text:
    with st.spinner("Analyzing and finding relevant grants..."):
        query = profile_text.strip()
        # --- Make OpenAI embedding ---
        embedding = client.embeddings.create(
            input=[query],
            model="text-embedding-3-small"
        ).data[0].embedding
        # --- Query Pinecone via OpenAI namespace ---
        namespace = "openai-v3"
        semantic_matches = index.query(vector=embedding, top_k=5, include_metadata=True, namespace=namespace)
        # Post-process results
        matches = semantic_matches["matches"]

        # Deduplicate (rare but good if you expand later)
        seen = set()
        unique_matches = []
        for m in matches:
            key = (m["metadata"].get("name", ""), m["metadata"].get("description", ""))
            if key not in seen:
                unique_matches.append(m)
                seen.add(key)
        # --- Data cleaning, deadline, scoring, sorting ---
        def safe_parse_deadline(deadline_str):
            try:
                if pd.isna(deadline_str) or deadline_str.strip() == "":
                    return None
                return parser.parse(deadline_str, dayfirst=True, fuzzy=True)
            except Exception:
                return None
        
        results_df = pd.DataFrame([m["metadata"] for m in unique_matches])
        # Clean deadline field
        placeholder_values = [
            "deadline information not found", "amount information not found",
            "contact information not found", "procedure information not found",
            "location information not found", ""
        ]
        results_df["deadline"] = results_df["deadline"].replace(placeholder_values, np.nan)
        results_df["deadline"] = results_df["deadline"].astype("string")
        results_df["deadline_date"] = results_df["deadline"].apply(safe_parse_deadline)
        results_df["deadline_date"] = pd.to_datetime(results_df["deadline_date"], errors="coerce")
        results_df["days_left"] = (results_df["deadline_date"] - datetime.now()).dt.days
        # Keep either missing deadlines or future
        results_df = results_df[
            (results_df["days_left"].isna()) | (results_df["days_left"] >= 0)
        ]
        # Scoring
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
        results_df["relevance_score"] = results_df.apply(
            lambda r: compute_relevance_score(r, query, user_location=user_location),
            axis=1
        )
        results_df = results_df.sort_values(by="relevance_score", ascending=False)
        matches = [{"metadata": r} for r in results_df.to_dict("records")]

        # --- Formatting ---
        def format_semantic_results(matches, user_query: str):
            formatted_blocks = []
            for idx, match in enumerate(matches, start=1):
                meta = match["metadata"]
                name = meta.get("name", "Unnamed")
                fields = {
                    "Description": meta.get("description"),
                    "Domain": meta.get("domain"),
                    "Eligibility": meta.get("eligibility"),
                    "Amount": meta.get("amount"),
                    "Deadline": meta.get("deadline"),
                    "Procedure": meta.get("procedure"),
                    "Location": meta.get("location"),
                    "Contact": meta.get("contact"),
                    "URL": meta.get("url"),
                    "Source": meta.get("source", "Unknown")
                }
                block = f"**{idx}. {name}**\n"
                for key, val in fields.items():
                    if key == "Deadline":
                        deadline_val = val
                        if deadline_val is None or pd.isna(deadline_val) or "not found" in str(deadline_val).lower():
                            deadline_str = "Not specified"
                        else:
                            days_left = meta.get("days_left", None)
                            if pd.notnull(days_left):
                                deadline_str = f"{deadline_val} (🕒 {int(days_left)} days left)"
                            else:
                                deadline_str = deadline_val
                        block += f"   - **Deadline**: {deadline_str}\n"
                        continue
                    if val and "not found" not in str(val).lower():
                        block += f"   - **{key}**: {val}\n"
                if fields["URL"]:
                    block += f"   - **For more information visit**: {fields['URL']}\n"
                formatted_blocks.append(block + "\n")  # <-- Add blank line between blocks
            return "\n".join(formatted_blocks)

        
        semantic_output = format_semantic_results(matches, query)

        # --- GPT-4 completion prompt ---
        llm_prompt = f"""The company described itself as:

"{query}"

Here are the top 5 most relevant public funding programs in Germany, based on a semantic search match to their needs:

{semantic_output}

Now:

Please write a concise and professional recommendation containing **only the top 2–3 most relevant funding programs** in this format:

Only select the top programs that most directly match the company’s domain, maturity stage (e.g., early-stage research), or funding needs. Ignore entries that are vague or poorly aligned.

For each recommendation, follow this format exactly:

1. <Program Name> (Source) 
**Why it fits**: <1–2 lines explaining relevance to the company’s domain (or) industry (or) field of work>  
**Description**: <Brief summary of the program’s goal and what it funds>
**Domain**: <Domain>      
**Eligibility**: <Eligibility>  
**Amount**: <Amount>  
**Deadline**: <Deadline (date or timeframe)>
**Location**: <Location or applicable regions>  
**Contact**: <Contact person, email, or organization>  
**Next Steps**:  
- Step 1: [Visit the (source) official page:]({{url}})  
- Step 2: <One key action the company must take>  
- Step 3: <Another action (e.g., submit proposal, form consortium)>  

If any field like **Amount**, **Deadline**, **Eligibility**, **Procedure**, or **Contact** is missing, either omit the line or say “Not specified”.

Use simple bullet points under **Next Steps**. Only list the top 2 or 3 programs — not all 5.

"""

        # GPT call
        gpt_response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in funding opportunities."},
                {"role": "user", "content": llm_prompt}
            ]
        )
        st.session_state["query"] = query
        st.session_state["results"] = results_df
        st.session_state["recommendation"] = gpt_response.choices[0].message.content

if "recommendation" in st.session_state:
    st.subheader("🧾 GPT Recommendation")
    st.markdown(st.session_state["recommendation"])

st.markdown("---")
st.subheader("📄 Want a Full Application Draft?")

if st.button("🧠 Generate Application Draft"):
    if "query" not in st.session_state or "results" not in st.session_state:
        st.warning("Please run 'Find Grants' first.")
    else:
        with st.spinner("Generating with GPT-4..."):
            query = st.session_state["query"]
            top_match = st.session_state["results"].iloc[0]
            # -- Dummy code for drafting, replace with your own function --
            company_profile = {
                "company_name": "Unnamed",
                "location": user_location,
                "industry": "Artificial Intelligence, Robotics",
                "goals": "- Advance AI-based robotic systems for automation\n- Collaborate with academic institutions",
                "project_idea": query,
                "funding_need": "Looking for public funding for early research and prototyping (~€200,000)"
            }
            funding_data = {
                "name": top_match.get("name", "Unnamed Program"),
                "amount": top_match.get("amount", "Not specified"),
                "deadline": top_match.get("deadline", "Not specified"),
                "eligibility": top_match.get("eligibility", "Not specified"),
                "description": top_match.get("description", "No description available")
            }
            # Here you would call your OpenAI-based drafting function, for now:
            draft = f"""Funding Application Draft\nCompany: {company_profile['company_name']}\nLocation: {company_profile['location']}\n---\nGoals: {company_profile['goals']}\nProject idea: {company_profile['project_idea']}\nFunding Need: {company_profile['funding_need']}\n---\nFunding call: {funding_data['name']}\nAmount: {funding_data['amount']}\nDeadline: {funding_data['deadline']}\nEligibility: {funding_data['eligibility']}\n---\nSummary: {funding_data['description']}\n"""
            filename = "application_draft.docx"
            with open(filename, "w") as f:
                f.write(draft)
            st.success("✅ Application draft is ready!")
            st.download_button("📥 Download .docx", data=open(filename, "rb"), file_name="application_draft.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.markdown("### 🧾 Draft Preview")
            st.text(draft[:3000])
