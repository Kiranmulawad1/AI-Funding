import os
import fitz  # PyMuPDF
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV")
assert OPENAI_API_KEY and PINECONE_API_KEY and PINECONE_ENV

# Initialize clients
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("funding-search")

# Streamlit layout
st.set_page_config(page_title="AI Funding Finder", layout="wide")
st.title("💸 AI Funding Finder")
st.markdown("Discover relevant public funding in Germany for your AI or robotics project.")

# Input method selection (Type Description first)
input_method = st.sidebar.radio("Input Method", ["Type Description", "Upload PDF"])

# Get user input
profile_text = ""
if input_method == "Type Description":
    profile_text = st.text_area("📝 Describe your company/project", height=250)
elif input_method == "Upload PDF":
    uploaded_pdf = st.file_uploader("📄 Upload your company profile (PDF)", type="pdf")
    if uploaded_pdf:
        doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
        profile_text = "\n".join(page.get_text() for page in doc)
        st.text_area("📄 Extracted PDF Text", profile_text, height=300)

# On button click
if st.button("🔍 Find Grants") and profile_text:
    with st.spinner("Analyzing and finding relevant grants..."):

        # Step 1: GPT-generated funding search query
        query_prompt = f"""
        You are an expert grant advisor. Based on the following user profile, generate a single-sentence query to find relevant public funding in Germany:

        \"\"\"
        {profile_text[:2000]}
        \"\"\"

        Only output the query.
        """

        query_response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You generate funding search queries from user descriptions."},
                {"role": "user", "content": query_prompt.strip()}
            ]
        )
        query = query_response.choices[0].message.content.strip()

        # Step 2: Embed the query
        embedding = client.embeddings.create(
            input=[query],
            model="text-embedding-3-small"
        ).data[0].embedding

        # Step 3: Query Pinecone for similar funding matches
        results = index.query(
            vector=embedding,
            top_k=5,
            include_metadata=True,
            namespace="openai-v3"
        )

        # Step 4: Format semantic search output for GPT
        def format_semantic_results(matches):
            formatted = ""
            for idx, match in enumerate(matches, 1):
                meta = match["metadata"]
                name = meta.get("name", "Unnamed")
                description = meta.get("description", "Not available")
                domain = meta.get("domain", "Not available")
                eligibility = meta.get("eligibility", "Not available")
                amount = meta.get("amount", "Not available")
                deadline = meta.get("deadline", "Not available")
                url = meta.get("url", "")
                formatted += f"""**{idx}. {name}**
- **Description**: {description}
- **Domain**: {domain}
- **Eligibility**: {eligibility}
- **Amount**: {amount}
- **Deadline**: {deadline}
- **Link**: {url}

"""
            return formatted.strip()

        semantic_output = format_semantic_results(results["matches"])

        # Step 5: Construct GPT prompt for recommendation
        llm_prompt = f"""
The company described itself as:

"{query}"

Here are the top 5 most relevant public funding programs in Germany, based on a semantic search match to their needs:

{semantic_output}

Now:

Please write a concise and professional recommendation containing **only the top 2–3 most relevant funding programs** in this format:

For each recommendation, follow this format exactly:

1. <Program Name>  
Why it fits: <1–2 lines explaining relevance to the company’s domain>  
**Amount**: <Amount>  
**Deadline**: <Deadline>  
**Eligibility**: <Eligibility>  
**Description**: <1–3 sentence summary of what the program funds and its focus>

**Next Steps**:  
- <Step 1> Visit the official call page: <Program URL>   
- <Step 2>  
- <Step 3 (if needed)>  

Use simple bullet points under **Next Steps**. Only list the top 2 or 3 programs — not all 5.
**Use only the official program title from the "name" field — not long topic phrases.**
"""

        # Step 6: Call GPT to generate the recommendation
        final_response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a funding advisor for AI and robotics companies."},
                {"role": "user", "content": llm_prompt}
            ]
        )

        # Step 7: Show final result
        st.subheader("🧾 GPT Recommendation")
        st.markdown(final_response.choices[0].message.content)
