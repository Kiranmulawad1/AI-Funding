import os
import fitz  # PyMuPDF
import streamlit as st
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from ollama import Client
from utils.draft_generator import generate_funding_draft, save_draft_to_docx

# Load environment variables
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
assert PINECONE_API_KEY

# Initialize clients
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("funding-search-bge")
embed_model = SentenceTransformer("BAAI/bge-small-en", device="cpu")
llm_client = Client(host="http://localhost:11434")

# Streamlit layout
st.set_page_config(page_title="AI Funding Finder", layout="wide")
st.title("💸 AI Funding Finder (LLaMA 3.2 Edition)")
st.markdown("Discover relevant public funding in Germany for your AI or robotics project.")

# Input method
input_method = st.sidebar.radio("Input Method", ["Type Description", "Upload PDF"])
profile_text = ""

if input_method == "Type Description":
    profile_text = st.text_area("📝 Describe your company/project", height=250)

elif input_method == "Upload PDF":
    uploaded_pdf = st.file_uploader("📄 Upload your company profile (PDF)", type="pdf")
    if uploaded_pdf:
        doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
        profile_text = "\n".join(page.get_text() for page in doc)
        st.text_area("📄 Extracted PDF Text", profile_text, height=300)

# 🔍 Funding Search
if st.button("🔍 Find Grants") and profile_text:
    with st.spinner("Analyzing and finding relevant grants..."):
        query = profile_text.strip()
        embedding = embed_model.encode(query).tolist()
        results = index.query(
            vector=embedding,
            top_k=5,
            include_metadata=True,
            namespace="open-source-v1"
        )

        st.session_state["query"] = query
        st.session_state["results"] = results

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
                    "Contact": meta.get("contact"),
                    "URL": meta.get("url"),
                }

                block = f"""**{idx}. {name}**\n"""
                for key, value in fields.items():
                    if value and "not found" not in str(value).lower():
                        block += f"   - **{key}**: {value}\n"
                formatted_blocks.append(block)
            return "\n".join(formatted_blocks)

        semantic_output = format_semantic_results(results["matches"], query)

        llm_prompt = f"""
The company described itself as:

"{query}"

Here are the top 5 most relevant public funding programs in Germany, based on a semantic search match to their needs:

{semantic_output}

Now:

Please write a concise and professional recommendation containing **only the top 2–3 most relevant funding programs** in this format:

1. <Program Name>  
Why it fits: <1–2 lines>  
**Description**: <...>  
**Domain**: <...>  
**Eligibility**: <...>  
**Amount**: <...>  
**Deadline**: <...>  
**Contact**: <...>  
**Next Steps**:  
- Step 1: Visit the official call page  
- Step 2: Prepare documents  
- Step 3: (Optional) Other steps from procedure
"""

        response = llm_client.generate(
            model="llama3.2",
            prompt=llm_prompt,
            stream=False
        )

        st.session_state["recommendation"] = response["response"]

# 🧾 Show Recommendation
if "recommendation" in st.session_state:
    st.subheader("🧾 LLaMA 3.2 Recommendation")
    st.markdown(st.session_state["recommendation"])

# 📄 Generate Application Draft
st.markdown("---")
st.subheader("📄 Want a Full Application Draft?")

if st.button("🧠 Generate Application Draft"):
    if "query" not in st.session_state or "results" not in st.session_state:
        st.warning("Please run 'Find Grants' first.")
    else:
        with st.spinner("Generating with LLaMA 3.2..."):
            query = st.session_state["query"]
            results = st.session_state["results"]

            company_profile = {
                "company_name": "Unnamed",
                "location": "Not specified",
                "industry": "Artificial Intelligence, Robotics",
                "goals": "- Advance AI-based robotic systems for automation\n- Collaborate with academic institutions",
                "project_idea": query,
                "funding_need": "Looking for public funding for early research and prototyping (~€200,000)"
            }

            top_match = results["matches"][0]["metadata"]
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

            st.download_button(
                label="📥 Download .docx",
                data=open(filename, "rb"),
                file_name="application_draft.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            st.markdown("### 🧾 Draft Preview")
            st.text(draft[:3000])
