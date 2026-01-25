# 🤖 AI-Funding-Agents

> **Multi-Agent AI Platform for Finding and Applying to German Grants**

An intelligent system that uses autonomous AI agents to discover funding opportunities and write grant proposals. Built with LangGraph, GPT-4, and modern Python tooling.

---

## 🌟 Features

### 🕵️ Deep Research Agent
- **Autonomous Web Scraping**: Searches official German and EU funding portals in real-time
- **Multi-Language Support**: Automatically translates queries to German for better results
- **Ethical Compliance**: Respects `robots.txt` and implements rate limiting
- **Smart Discovery**: Uses DuckDuckGo and Playwright to find live funding opportunities

### ✍️ Interactive Grant Writer
- **AI Co-Pilot**: Interviews you to gather missing information
- **Context-Aware**: Analyzes grant requirements and tailors questions
- **Document Generation**: Creates professional Word documents (.docx)
- **Conversational**: Natural language interaction for proposal building

### 💾 Database Search
- **Vector Search**: Fast semantic search through cached grant data using Pinecone
- **Historical Data**: Quick access to previously indexed funding programs

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- OpenAI API key
- Pinecone API key (optional, for database search)
- PostgreSQL database (optional, for query history)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Kiranmulawad1/AI-Funding-Agents.git
cd AI-Funding-Agents
```

2. **Install dependencies using uv** (recommended)
```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync
```

Or using pip:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env and add your API keys
```

Required environment variables:
```env
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=your-key  # Optional
PINECONE_INDEX_NAME=funding-search  # Optional
POSTGRES_URL=postgresql://...  # Optional
```

4. **Run the application**
```bash
uv run streamlit run src/app.py
```

Visit `http://localhost:8501` in your browser.

---

## 📖 Usage

### Finding Grants

1. Select **"🕵️‍♂️ Deep Research Agent"** in the sidebar
2. Enter your query (e.g., *"AI healthcare funding in Bavaria"*)
3. The agent will search live websites and return detailed results

### Writing Proposals

1. Search for a grant using any method
2. Click **"📝 Interactive Draft"** on a result
3. Answer the agent's questions about your project
4. Download your professional proposal as a Word document

---

## 🏗️ Architecture

```
src/
├── agents/           # AI Agent implementations
│   ├── deep_researcher.py   # Web scraping agent
│   ├── grant_writer.py      # Proposal writing agent
│   └── tools.py             # Shared tools (search, browser)
├── core/             # Shared utilities
│   ├── config.py            # Configuration management
│   ├── database.py          # PostgreSQL integration
│   ├── vector_search.py     # Pinecone semantic search
│   ├── document_generator.py
│   └── ...
└── app.py            # Streamlit UI
```

### Tech Stack
- **Agents**: LangGraph + GPT-4
- **UI**: Streamlit
- **Scraping**: Playwright + BeautifulSoup
- **Search**: DuckDuckGo, Pinecone
- **Documents**: python-docx
- **Packaging**: uv

---

## 🔧 Development

### Running Tests
```bash
uv run pytest
```

### Code Quality
```bash
# Format code
uv run black src/

# Lint
uv run ruff check src/
```

### Building Package
```bash
uv build
```

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Powered by [OpenAI GPT-4](https://openai.com)
- UI by [Streamlit](https://streamlit.io)

---

## 📧 Contact

**Kiran Mulawad** - [GitHub](https://github.com/Kiranmulawad1)

Project Link: [https://github.com/Kiranmulawad1/AI-Funding-Agents](https://github.com/Kiranmulawad1/AI-Funding-Agents)
