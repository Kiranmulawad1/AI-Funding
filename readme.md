# 🎯 AI-Powered Funding Discovery & Document Generation System

**Streamlining Business Funding Applications with AI-Based Discovery and Document Generation**

A comprehensive system that automates the discovery of German public funding opportunities and generates tailored application documents using advanced AI technologies.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-green.svg)](https://openai.com/)
[![Pinecone](https://img.shields.io/badge/Pinecone-Vector%20DB-purple.svg)](https://pinecone.io/)

## 🚀 Features

### Core Capabilities
- **Multi-Source Data Scraping**: Automated extraction from 3+ German funding portals
- **Intelligent Translation**: German-to-English translation using DeepL API
- **Semantic Search**: Vector-based matching using OpenAI embeddings + Pinecone
- **AI Recommendations**: GPT-4 powered funding program recommendations
- **Document Generation**: Automated application draft creation
- **Profile Processing**: PDF company profile upload and analysis
- **Query Memory**: PostgreSQL-based conversation history

### Advanced Features
- **RAG Architecture**: Retrieval-Augmented Generation for accurate responses
- **Relevance Scoring**: Custom scoring algorithm considering deadlines, location, domain
- **Multi-format Support**: PDF parsing, DOCX generation, CSV processing  
- **Real-time Processing**: Streamlit-based interactive web interface

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Sources  │    │   AI Processing  │    │   User Interface│
│                 │    │                  │    │                 │
│ • Förderdatenbank│───▶│ • OpenAI GPT-4   │◀──▶│ • Streamlit App │
│ • ISB Portal    │    │ • Text Embeddings│    │ • PDF Upload    │
│ • NRW Europa    │    │ • Pinecone VectorDB│   │ • Chat Interface│
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Data Processing │    │   Document Gen   │    │   Memory Layer  │
│                 │    │                  │    │                 │
│ • Web Scraping  │    │ • Draft Creation │    │ • PostgreSQL    │
│ • Translation   │    │ • DOCX Export    │    │ • Query History │
│ • Data Cleaning │    │ • Template Logic │    │ • User Sessions │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📂 Project Structure

```
AI-Funding/
├── 1_scraping/                    # Web scraping modules
│   ├── foerderdatenbank/         # Federal funding database scraper
│   ├── isb/                      # ISB Rhineland-Palatinate scraper  
│   └── nrweuropa/               # NRW Europa cascade funding scraper
├── 2_preprocessing/              # Data cleaning and merging
│   └── merging.ipynb            # Standardizes and combines datasets
├── 3_embeddings_query/          # Vector processing and search
│   ├── embedding_uploader.ipynb # Creates Pinecone embeddings
│   ├── funding_query_engine.py  # Core search functionality
│   └── query_openai.ipynb      # Query processing pipeline
├── 4_streamlit_app/             # Web application
│   ├── app_streamlit.py         # Main Streamlit application
│   ├── config.py               # Configuration management
│   ├── rag_core.py             # RAG implementation
│   ├── gpt_recommender.py      # AI recommendation engine
│   ├── docs_generator.py       # Document generation
│   ├── memory.py               # PostgreSQL integration
│   └── utils.py                # Utility functions
├── company_profile_samples/      # Sample company profiles for testing
├── data/                        # Processed datasets
│   └── merged_funding_data.csv  # Final consolidated funding data
├── requirements.txt             # Python dependencies
└── README.md                   # Project documentation
```

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- PostgreSQL database
- API keys for: OpenAI, Pinecone, DeepL

### 1. Clone Repository
```bash
git clone https://github.com/your-username/AI-Funding.git
cd AI-Funding
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory:
```env
# AI APIs
OPENAI_API_KEY=your_openai_api_key
DEEPL_API_KEY=your_deepl_api_key

# Vector Database
PINECONE_API_KEY=your_pinecone_api_key  
PINECONE_ENV=your_pinecone_environment
PINECONE_INDEX_NAME=funding-search
PINECONE_NAMESPACE=openai-v3

# Database
POSTGRES_URL=postgresql://user:password@localhost:5432/funding_db
```

### 4. Database Setup
```sql
CREATE TABLE funding_queries (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    query TEXT NOT NULL,
    source VARCHAR(255),
    result_count INTEGER,
    recommendation TEXT
);
```

### 5. Run Data Pipeline

#### Step 1: Scrape Data
```bash
# Run scraping notebooks for each source
jupyter notebook 1_scraping/foerderdatenbank/foerderdatenbank_scraping_data.ipynb
jupyter notebook 1_scraping/isb/isb_scraping_data.ipynb  
jupyter notebook 1_scraping/nrweuropa/nrweuropa_scraping_data.ipynb
```

#### Step 2: Translate Content
```bash
# Translate German content to English
jupyter notebook 1_scraping/*/translation_english.ipynb
```

#### Step 3: Process & Merge
```bash
# Clean and combine all datasets
jupyter notebook 2_preprocessing/merging.ipynb
```

#### Step 4: Create Embeddings
```bash
# Generate vector embeddings and upload to Pinecone
jupyter notebook 3_embeddings_query/embedding_uploader.ipynb
```

### 6. Launch Application
```bash
cd 4_streamlit_app
streamlit run app_streamlit.py
```

## 🎮 Usage

### Basic Query Flow
1. **Input**: Describe your company or upload a PDF profile
2. **Processing**: System searches 500+ German funding programs
3. **AI Analysis**: GPT-4 analyzes matches and generates recommendations  
4. **Output**: Ranked funding opportunities with application guidance
5. **Document Generation**: Create tailored application drafts

### Advanced Features
- **Chat Interface**: Ask follow-up questions about recommendations
- **PDF Processing**: Upload company profiles for automatic query generation
- **Memory**: System remembers conversation context and query history
- **Filtering**: Results filtered by deadlines, relevance, and location

## 🔧 Technical Implementation

### Data Collection Pipeline
- **Web Scraping**: Selenium + BeautifulSoup + Playwright for dynamic content
- **Translation**: DeepL API for German-to-English conversion
- **Data Cleaning**: Standardized formatting, duplicate removal, field mapping

### AI/ML Components  
- **Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
- **Vector Search**: Pinecone similarity search with cosine distance
- **Language Models**: GPT-4-turbo for recommendations, GPT-3.5 for summaries
- **RAG Pipeline**: Retrieval-Augmented Generation for context-aware responses

### Application Architecture
- **Frontend**: Streamlit with responsive chat interface
- **Backend**: Python with modular component design
- **Database**: PostgreSQL for query history and user sessions  
- **Document Processing**: python-docx for application draft generation

## 📊 Performance Metrics

- **Data Coverage**: 500+ funding programs from 3 major German portals
- **Search Speed**: <2 seconds average query response time
- **Accuracy**: Semantic search with 0.85+ relevance scores
- **Languages**: German source data, English user interface
- **Document Types**: PDF input, DOCX output generation

## 🧪 Testing

### Sample Queries
```python
# Example company descriptions for testing
queries = [
    "AI startup developing robotics automation solutions",
    "Sustainable energy research project at university",
    "SME looking for digitization funding in manufacturing",
    "Early-stage biotech company developing medical devices"
]
```

### Performance Testing
```bash
# Test embedding generation speed
python -c "from rag_core import get_embedding; import time; start=time.time(); get_embedding('test query'); print(f'Embedding time: {time.time()-start:.2f}s')"

# Test search accuracy  
jupyter notebook 3_embeddings_query/query_openai.ipynb
```

## 📈 Future Enhancements

### Planned Features
- **Multi-language Support**: French, Spanish funding sources
- **Private Funding**: Venture capital, accelerator programs  
- **API Integration**: RESTful API for external system integration
- **Mobile App**: Native mobile application development
- **Machine Learning**: Custom relevance ranking algorithms

### Technical Improvements
- **Caching**: Redis integration for faster repeated queries
- **Monitoring**: Application performance and usage analytics
- **Scalability**: Kubernetes deployment for production use
- **Security**: Enhanced authentication and data protection

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Make changes and test thoroughly
4. Submit pull request with detailed description

### Code Standards
- Follow PEP 8 Python style guidelines
- Add docstrings for all functions and classes
- Include unit tests for new functionality
- Update README for significant changes

## 📝 License

This project is part of a Master's thesis at SRH Hochschule Heidelberg. 

**Academic Use**: Free for educational and research purposes
**Commercial Use**: Contact author for licensing terms

## 📞 Contact & Support

**Author**: Kiran Mulawad  
**University**: SRH Hochschule Heidelberg  
**Program**: MSc Applied Data Science and Analytics  
**Supervisors**: Prof. Dr. Mehrdad Jalali, Aashwin Shrivastava (iiterate Technologies)

### Getting Help
- **Issues**: Open GitHub issues for bugs or feature requests
- **Questions**: Contact via university email or LinkedIn
- **Documentation**: Check inline code comments and Jupyter notebooks

## 🙏 Acknowledgments

- **iiterate Technologies GmbH** for internship opportunity and continued support
- **SRH Hochschule Heidelberg** for academic guidance and resources  
- **OpenAI** for GPT-4 and embedding model access
- **German Federal Funding Databases** for public data availability

## 📚 Research Context

This system was developed as part of a Master's thesis research project focusing on:
- **AI-powered information retrieval** in the public funding domain
- **Natural language processing** for German bureaucratic documents
- **Automated document generation** using large language models
- **Human-AI interaction** design for complex decision-making processes

The project extends previous internship work by adding comprehensive document generation capabilities and advanced AI integration, representing a significant contribution to the field of AI-assisted business development tools.

---
**⭐ If this project helps your research or business, please consider starring the repository!**