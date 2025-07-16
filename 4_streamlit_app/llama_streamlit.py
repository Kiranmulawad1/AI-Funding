import os
import fitz  # PyMuPDF
import streamlit as st
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from ollama import Client

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

# 🔍 Button
if st.button("🔍 Find Grants") and profile_text:
    with st.spinner("Analyzing and finding relevant grants..."):

        # Step 1: Use input directly as query
        query = profile_text.strip()

        # Step 2: Embed query locally
        embedding = embed_model.encode(query).tolist()

        # Step 3: Semantic search from Pinecone
        results = index.query(
            vector=embedding,
            top_k=5,
            include_metadata=True,
            namespace="open-source-v1"
        )

        # Step 4: Format semantic results
        def format_semantic_results(matches, user_query: str):
            formatted_blocks = []
            field_aliases = {
                "Amount": ["amount", "how much", "funding", "money"],
                "Deadline": ["deadline", "last date", "until", "submission date"],
                "Eligibility": ["eligible", "eligibility", "who can apply"],
                "Procedure": ["procedure", "how to apply", "application", "steps", "process"],
                "Contact": ["contact", "email", "person", "support"],
            }

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

                missing_fields = []
                for key, value in fields.items():
                    if key in field_aliases:
                        if any(alias in user_query.lower() for alias in field_aliases[key]):
                            if not value or "not found" in str(value).lower():
                                missing_fields.append(key)

                block = f"""**{idx}. {name}**\n"""
                for key in ["Description", "Domain", "Eligibility", "Amount", "Deadline", "Procedure", "Contact"]:
                    val = fields[key]
                    if val and "not found" not in str(val).lower():
                        block += f"   - **{key}**: {val}\n"

                if missing_fields:
                    block += f"   - *Couldn't trace information about {', '.join(missing_fields)}.*\n"

                if fields["URL"]:
                    block += f"   - **For more information visit**: {fields['URL']}\n"

                formatted_blocks.append(block)

            return "\n".join(formatted_blocks)

        semantic_output = format_semantic_results(results["matches"], query)

        # Step 5: LLM prompt
        llm_prompt = f"""
The company described itself as:

"{query}"

Here are the top 5 most relevant public funding programs in Germany, based on a semantic search match to their needs:

{semantic_output}

Now:

Please write a concise and professional recommendation containing **only the top 2–3 most relevant funding programs** in this format:

Only select the top programs that most directly match the company’s domain, maturity stage (e.g., early-stage research), or funding needs. Ignore entries that are vague or poorly aligned.

For each recommendation, follow this format exactly:

1. <Program Name>  
Why it fits: <1–2 lines explaining relevance to the company’s domain (or) industry (or) field of work>  
**Description**: <1–3 sentence summary of what the program funds and its focus>  
**Domain**: <Domain>  
**Eligibility**: <Eligibility>  
**Amount**: <Amount>  
**Deadline**: <Deadline>  
**Contact**: <Contact person, email, or organization — not the URL>  
**For more information**: <Program URL>  
**Next Steps**:  
- Step 1: <Visit the official call page or other action>  
- Step 2: <Provide one or two helpful next steps, e.g., form a consortium, prepare documents>  
- Step 3: (Optional) <Any extra steps from the program's procedure>  

If any field like **Amount**, **Deadline**, **Eligibility**, **Procedure**, **Contact**, or **Domain** is missing, either omit the line or say “Not specified”.

Use simple bullet points under **Next Steps**. Only list the top 2 or 3 programs — not all 5.
"""

        # Step 6: LLaMA 3.2 generation
        response = llm_client.generate(
            model="llama3.2",
            prompt=llm_prompt,
            stream=False
        )

        # Step 7: Display result
        st.subheader("🧾 LLaMA 3.2 Recommendation")
        st.markdown(response['response'])
