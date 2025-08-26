import os
import re
import fitz  # PyMuPDF
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from dateutil import parser
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from ollama import Client
from utils.draft_generator import generate_funding_draft, save_draft_to_docx

# Load environment variables
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
assert PINECONE_API_KEY

# Load merged CSV
full_df = pd.read_csv("/Users/kiranmulawad/AI-Funding/2_preprocessing/data/merged_funding_data.csv")

# Initialize services
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("funding-search-bge")
embed_model = SentenceTransformer("BAAI/bge-small-en", device="cpu")
llm_client = Client(host="http://localhost:11434")

# Streamlit setup
st.set_page_config(page_title="AI Funding Finder", layout="wide")
st.title("💸 AI Funding Finder (LLaMA 3.2 Edition)")
st.markdown("Discover relevant public funding in Germany for your AI or robotics project.")

# Input method
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
        embedding = embed_model.encode(query).tolist()

        semantic_matches = index.query(vector=embedding, top_k=5, include_metadata=True, namespace="open-source-v1")
        pdf_matches = index.query(vector=embedding, top_k=5, include_metadata=True, namespace="pdf-upload")

        all_matches = semantic_matches["matches"] + pdf_matches["matches"]
        seen = set()
        unique_matches = []
        for m in all_matches:
            key = (m["metadata"].get("name", ""), m["metadata"].get("description", ""))
            if key not in seen:
                unique_matches.append(m)
                seen.add(key)

        def safe_parse_deadline(deadline_str):
            try:
                return parser.parse(deadline_str, dayfirst=True, fuzzy=True)
            except:
                return None

        def compute_relevance_score(row, query, funding_need="200000", target_domain="AI", user_location="Rhineland-Palatinate"):
            score = 0
            if target_domain.lower() in str(row.get("domain", "")).lower():
                score += 0.4
            try:
                amount_val = int(re.sub(r"[^\d]", "", str(row.get("amount", "0"))))
                if amount_val >= int(funding_need):
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

        results_df = pd.DataFrame([m["metadata"] for m in unique_matches])
        results_df["deadline_date"] = results_df["deadline"].apply(safe_parse_deadline)
        results_df["days_left"] = (results_df["deadline_date"] - datetime.now()).dt.days
        results_df = results_df[results_df["days_left"].fillna(0) >= 0]
        results_df["relevance_score"] = results_df.apply(lambda r: compute_relevance_score(r, query, user_location=user_location), axis=1)
        results_df = results_df.sort_values(by="relevance_score", ascending=False)
        matches = [{"metadata": r} for r in results_df.to_dict("records")]

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
                    if key == "Deadline" and val and "not found" not in str(val).lower():
                        days_left = meta.get("days_left", None)
                        if pd.notnull(days_left):
                            val += f" (🕒 {int(days_left)} days left)"
                    if val and "not found" not in str(val).lower():
                        block += f"   - **{key}**: {val}\n"
                if fields["URL"]:
                    block += f"   - **For more information visit**: {fields['URL']}\n"
                formatted_blocks.append(block)
            return "\n".join(formatted_blocks)

        semantic_output = format_semantic_results(matches, query)

        llm_prompt = f"""The company described itself as:

"{query}"

Here are the top 5 most relevant public funding programs in Germany, based on a semantic search match to their needs:

{semantic_output}

Now:

Please write a concise and professional recommendation containing **only the top 2-3 most relevant funding programs** in this format:

1. <Program Name>  
Why it fits: <1-2 lines>  
**Description**: <...>  
**Domain**: <...>  
**Eligibility**: <...>  
**Amount**: <...>  
**Deadline**: <...>  
**Location**: <...>  
**Contact**: <...>  
**Next Steps**:  
- Step 1: Visit the official call page  
- Step 2: Prepare documents  
- Step 3: (Optional) Other steps from procedure
"""

        response = llm_client.generate(model="llama3.2", prompt=llm_prompt, stream=False)
        st.session_state["query"] = query
        st.session_state["results"] = results_df
        st.session_state["recommendation"] = response["response"]

if "recommendation" in st.session_state:
    st.subheader("🧾 LLaMA 3.2 Recommendation")
    st.markdown(st.session_state["recommendation"])

st.markdown("---")
st.subheader("📄 Want a Full Application Draft?")

if st.button("🧠 Generate Application Draft"):
    if "query" not in st.session_state or "results" not in st.session_state:
        st.warning("Please run 'Find Grants' first.")
    else:
        with st.spinner("Generating with LLaMA 3.2..."):
            query = st.session_state["query"]
            top_match = st.session_state["results"].iloc[0]
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
            draft = generate_funding_draft(company_profile, funding_data)
            filename = save_draft_to_docx(draft)
            st.success("✅ Application draft is ready!")
            st.download_button("📥 Download .docx", data=open(filename, "rb"), file_name="application_draft.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.markdown("### 🧾 Draft Preview")
            st.text(draft[:3000])
