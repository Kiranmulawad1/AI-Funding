import os
import fitz  # PyMuPDF
import streamlit as st
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from ollama import Client

# Load env variables
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("funding-search-bge")

# Initialize Ollama and SentenceTransformer
llm = Client(host="http://localhost:11434")
embed_model = SentenceTransformer("BAAI/bge-small-en")

# Layout setup
st.set_page_config(page_title="AI Funding Finder (LLaMA 3.2)", layout="wide")
st.title("💸 AI Funding Finder")
st.markdown("Discover relevant public funding programs in Germany based on your company profile.")

# Input selector
input_method = st.sidebar.radio("Choose Input Method", ["Type Description", "Upload PDF"])
profile_text = ""

if input_method == "Type Description":
    profile_text = st.text_area("📝 Describe your company/project", height=250)

elif input_method == "Upload PDF":
    uploaded_file = st.file_uploader("📄 Upload PDF (Company Profile)", type="pdf")
    if uploaded_file:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        profile_text = "\n".join(page.get_text() for page in doc)
        st.text_area("📄 Extracted Text", profile_text, height=300)

# Main process
if st.button("🔍 Find Grants") and profile_text:
    with st.spinner("Analyzing and matching funding opportunities..."):

        # Step 1: Generate semantic embedding
        query = profile_text.strip()
        query_embedding = embed_model.encode(query).tolist()

        # Step 2: Semantic search from Pinecone
        results = index.query(
            vector=query_embedding,
            top_k=5,
            include_metadata=True,
            namespace="open-source-v1"
        )

        # Step 3: Format for LLM
        def format_results(matches):
            formatted = ""
            for i, match in enumerate(matches["matches"], 1):
                m = match["metadata"]
                formatted += f"""**{i}. {m.get("name", "Unnamed")}**
- **Description**: {m.get("description", "Not available")}
- **Domain**: {m.get("domain", "Not available")}
- **Eligibility**: {m.get("eligibility", "Not available")}
- **Amount**: {m.get("amount", "Not available")}
- **Deadline**: {m.get("deadline", "Not available")}
- **Contact**: {m.get("contact", "Not specified")}
- **Procedure**: {m.get("procedure", "Not specified")}
- **Link**: {m.get("url", "")}

"""
            return formatted.strip()

        semantic_output = format_results(results)

        # Step 4: Load prompt template from file
        with open("llm_prompt_llama.txt", "r") as f:
            llm_prompt = f.read()

        final_prompt = llm_prompt.replace("{query}", query).replace("{semantic_output}", semantic_output)

        # Step 5: Generate with LLaMA
        response = llm.generate(model="llama3.2", prompt=final_prompt, stream=False)
        final_text = response["response"]

        # Step 6: Display structured output
        st.subheader("📑 Recommendations (LLaMA 3.2)")

        programs = final_text.strip().split("\n\n")

        for i, program in enumerate(programs, 1):
            with st.expander(f"Program {i}"):
                st.markdown(program.strip())

        # Optional: Display copy-to-clipboard
        st.markdown("#### 📋 Copy Full Response")
        st.text_area("Copy-ready output", final_text, height=300)

        # Optional: Table Summary
        if st.checkbox("🔄 Show tabular summary"):
            import pandas as pd
            table_rows = []
            for program in programs:
                row = {}
                for line in program.split("\n"):
                    if "**Description**" in line:
                        row["Description"] = line.split("**Description**:")[-1].strip()
                    elif "**Amount**" in line:
                        row["Amount"] = line.split("**Amount**:")[-1].strip()
                    elif "**Deadline**" in line:
                        row["Deadline"] = line.split("**Deadline**:")[-1].strip()
                    elif "**Eligibility**" in line:
                        row["Eligibility"] = line.split("**Eligibility**:")[-1].strip()
                    elif line.strip().startswith("1.") or line.strip().startswith("2.") or line.strip().startswith("3."):
                        row["Program"] = line.strip().split(". ", 1)[-1]
                if row:
                    table_rows.append(row)
            if table_rows:
                st.dataframe(pd.DataFrame(table_rows))

