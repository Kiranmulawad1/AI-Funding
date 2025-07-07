# 🤖 AI Funding Finder – Thesis Project (End-to-End Semantic Matching & LLM Recommendations)

This project is part of a master's thesis focused on building an intelligent system that helps startups and SMEs discover **relevant public funding opportunities** in Germany.

Users can upload a **PDF company profile** or enter a **text-based query**, and the system:
- Extracts and embeds the input
- Performs semantic search on a vector store (Pinecone)
- Uses GPT to recommend matching grants

---

## 🧠 Project Architecture

```
        [Funding Websites / Portals]
                     ↓
             Scraping Scripts
                     ↓
       Preprocessing & Normalization
                     ↓
        Embedding with OpenAI API
                     ↓
      Upload to Pinecone Vector DB
                     ↓
 ┌────────────────────────────────────┐
 │   User Upload (PDF or Text Query) │
 └────────────────────────────────────┘
                     ↓
         Embedding with OpenAI
                     ↓
    Semantic Search (Pinecone: CSV only)
                     ↓
     GPT-4 Turbo → Grant Recommendation
```

---

## 🗂️ Folder Structure

```
AI-Funding/
├── 1_scraping_data/
│   ├── scrape_isb.py                      # Scrapes ISB funding portal
│   ├── scrape_foerderdatenbank.py         # Scrapes foerderdatenbank.de
│   ├── preprocess_funding_data.ipynb      # Cleans & structures scraped data
│   └── output_funding_data.csv            # Unified funding CSV used for embedding
│
├── 3_openai_model/
│   ├── 0_reset_pinecone_index.ipynb       # Clears Pinecone index
│   ├── 1_upload_csv_embeddings.ipynb      # Embeds & uploads funding entries to Pinecone (openai-v3)
│   ├── 2_upload_pdf_chunks.ipynb          # Chunks & uploads user PDF to Pinecone (pdf-upload)
│   ├── 3_unified_query_pdf_csv_llm.ipynb  # Unified semantic query + GPT recommendation
│   └── sample_user_profile.pdf            # Sample input profile
│
├── .env.example                           # Safe template of required environment variables
├── requirements.txt                       # Python dependencies
└── README.md                              # Project documentation
```

---

## ⚙️ Tech Stack

- **Python 3.10+**
- **Web Scraping**: `requests`, `BeautifulSoup`, `Selenium`
- **PDF Extraction**: `PyMuPDF`
- **Chunking**: `tiktoken`
- **Semantic Embeddings**: `OpenAI text-embedding-3-small`
- **Vector Search**: `Pinecone`
- **LLM Responses**: `gpt-4-turbo`
- **Environment Management**: `python-dotenv`, `.venv`

---

## 🔐 Environment Variables

Create a `.env` file based on `.env.example`:

```env
OPENAI_API_KEY=your-openai-api-key
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENV=your-pinecone-environment
DEEPL_API_KEY=your-deepl-api-key (optional for translations)
```

---

## 🚀 How to Use

### 1. Scrape and Prepare Funding Data
- Run scraping scripts in `1_scraping_data/`
- Use `preprocess_funding_data.ipynb` to clean and format output
- Result: `output_funding_data.csv`

### 2. Embed and Upload Fundings
- Run `1_upload_csv_embeddings.ipynb` to embed and upload the CSV into Pinecone (`openai-v3` namespace)

### 3. Upload User Profile (PDF)
- Run `2_upload_pdf_chunks.ipynb` to extract, chunk, and upload the PDF (`pdf-upload` namespace)

### 4. Run Semantic Search + GPT Recommendation
- Run `3_unified_query_pdf_csv_llm.ipynb`
  - Auto-generates query from PDF
  - Searches fundings in Pinecone (CSV-only)
  - Uses GPT to return top 2–3 matched grants with rationale

---

## 🧼 Best Practices

- `.env` is globally and locally ignored
- `.env.example` shared for reproducibility
- `.venv/`, `__pycache__/`, `.ipynb_checkpoints/` all excluded via `.gitignore`
- Modular code (scraping, embedding, querying all separated)

---

## 📌 Future Ideas

- Add Streamlit UI for easy PDF upload and grant display
- PDF result download (funding summary)
- Feedback loop to improve recommendations
- Translation fallback with DeepL (already tested)

---

## 👨‍🎓 Author

**Kiran Mulawad**  
Thesis Project – M.Sc. in Applied Data Science and Analytics  
SRH Hochschule Heidelberg  
GitHub: [KiranMulawad1](https://github.com/Kiranmulawad1)

---
