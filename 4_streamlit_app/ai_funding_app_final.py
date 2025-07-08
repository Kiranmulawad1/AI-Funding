#!/usr/bin/env python
# coding: utf-8

# # 🚀 Streamlit App: AI Funding Finder
# This notebook contains the full source code for the Streamlit UI.

# In[ ]:


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


# In[ ]:


st.set_page_config(page_title="AI Funding Finder", layout="wide")
st.title("💸 AI Funding Finder")
st.markdown("Upload your company profile (PDF) or type your project description to discover relevant grants in Germany.")


# In[ ]:


# Helper: extract PDF text
def extract_text_from_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


# In[ ]:


# Sidebar: Choose input method
input_method = st.sidebar.radio("Input Method", ["Upload PDF", "Type Description"])

if input_method == "Upload PDF":
    uploaded_pdf = st.file_uploader("Upload your company profile PDF", type="pdf")
    if uploaded_pdf:
        profile_text = extract_text_from_pdf(uploaded_pdf)
        st.text_area("📄 Extracted Profile Text", profile_text, height=300)
elif input_method == "Type Description":
    profile_text = st.text_area("📝 Describe your company/project", height=250)


# In[ ]:


if st.button("🔍 Find Grants") and profile_text:
    with st.spinner("Generating query and searching..."):

        # Generate query from profile
        query_prompt = f"""
        You are an expert grant advisor. Based on the following user profile text, generate a single-sentence query to find relevant public funding in Germany:

        Profile:
        \"\"\"
        {profile_text[:2000]}
        \"\"\"

        Only output the query — do not include explanations or headers.
        """

        query_response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You generate funding search queries from user descriptions."},
                {"role": "user", "content": query_prompt.strip()}
            ]
        )
        query = query_response.choices[0].message.content.strip()

        # Embed query
        embedding = client.embeddings.create(
            input=[query],
            model="text-embedding-3-small"
        ).data[0].embedding

        # Search in Pinecone (CSV namespace)
        results = index.query(
            vector=embedding,
            top_k=5,
            include_metadata=True,
            namespace="openai-v3"
        )

        # Format results
        funding_chunks = []
        st.subheader("📊 Top Funding Matches")
        for i, match in enumerate(results["matches"], start=1):
            meta = match["metadata"]
            name = meta.get("name", "Unnamed Program")
            url = meta.get("url", "#")
            desc = meta.get("description", "")[:400]
            st.markdown(f"**{i}. [{name}]({url})**\n\n{desc}")
            funding_chunks.append(f"{name}: {desc}")

        # GPT Recommendation
        llm_prompt = f"""
        The user's profile is:
        {query}

        Here are the top matched fundings:
        {chr(10).join(funding_chunks)}

        Suggest the 2–3 most relevant grants and advise next steps for the company.
        """

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a funding advisor."},
                {"role": "user", "content": llm_prompt}
            ]
        )

        st.subheader("🧾 GPT Recommendation")
        st.markdown(response.choices[0].message.content)

