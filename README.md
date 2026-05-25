# Cash Crew 

**Professional Multi-Agent AI Equity Research System**

Cash Crew is a sophisticated AI-powered equity research platform that generates professional-grade, explainable financial analysis reports using real-time data, technical analysis, sentiment analysis, governance checks, PEAD analytics, and RAG-based filing parsing.

##  Key Features

### **Hybrid LLM Architecture** (Hackathon Showstopper!)
- **Groq LLaMA-3-70B**: Ultra-fast XAI explanations and report generation
- **Google Gemini 1.5 Pro**: Long-context filing analysis (1M tokens)
- **HuggingFace Mixtral**: Cost-effective sentiment analysis
- **Ollama**: Fully offline demo capability

### **8 Specialized AI Agents**
1. **Fundamental Analyst** - Financial ratios, metrics, company health
2. **Technical Analyst** - Price patterns, indicators, trend analysis
3. **Sentiment Analyst** - News & social media sentiment (HF Mixtral)
4. **Governance & Fraud** - Red flags, auditor changes, insider trading
5. **PEAD Analyst** - Post-earnings drift prediction with backtesting
6. **RAG Filing Agent** - SEC/BSE filing analysis (Gemini/Groq)
7. **Risk Analyst** - Vertical leader, conflict resolution, final scoring
8. **XAI Agent** - Explainable AI with factor contributions (Groq LLaMA-3-70B)

### **Professional Outputs**
- Interactive dashboards with real-time charts
- PDF reports with embedded visualizations
- Explainable AI factor contributions
- BUY/HOLD/SELL recommendations with confidence scores

---

##  Prerequisites

### API Keys (Free Tiers Available)
- **Groq** - [Get API Key](https://console.groq.com/) (30 req/min free)
- **Google AI Studio** - [Get API Key](https://makersuite.google.com/app/apikey) (Gemini free tier)
- **HuggingFace** - [Get API Key](https://huggingface.co/settings/tokens) (Free inference)
- **Finnhub** - [Get API Key](https://finnhub.io/) (Free tier)
- **Alpha Vantage** - [Get API Key](https://www.alphavantage.co/support/#api-key) (Free tier)
- **News API** - [Get API Key](https://newsapi.org/) (Free tier)

### Local Requirements
- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Ollama** (optional, for offline demo) - [Install](https://ollama.ai/)

---

##  Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/cash-crew.git
cd cash-crew
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
nano .env
```

### 3. Frontend Setup
```bash
cd ../frontend

# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local

# Edit .env.local
nano .env.local
```

### 4. (Optional) Install Ollama for Offline Demo
```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama3
ollama pull mixtral
ollama pull mistral
```

---

##  Quick Start

### Start Backend
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Start Frontend
```bash
cd frontend
npm run dev
```

### Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

##  Demo Modes

Cash Crew supports 3 demo modes for different scenarios:

### 1. **Live Mode** (Production)
- Real financial APIs
- Cloud LLMs (Groq, Gemini, HuggingFace)
- Best performance
```bash
# In .env
DEMO_MODE=live
```

### 2. **Hybrid Mode** (Development)
- Real financial APIs
- Ollama local LLMs only
- No cloud LLM costs
```bash
# In .env
DEMO_MODE=hybrid
```

### 3. **Offline Mode** (Demo/Hackathon)
- Mock financial data
- Ollama local LLMs
- No internet required
```bash
# In .env
DEMO_MODE=offline
```

---

## Usage Example

### API Request
```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "TCS.NS",
    "timeframe": "1y",
    "region": "India",
    "risk_preference": "balanced"
  }'
```

### Python Client
```python
import requests

response = requests.post("http://localhost:8000/analyze", json={
    "ticker": "AAPL",
    "timeframe": "1y",
    "region": "US",
    "risk_preference": "balanced"
})

report = response.json()
print(f"Recommendation: {report['recommendation']}")
print(f"Final Score: {report['final_score']}")
print(f"Confidence: {report['confidence']}")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
│  Interactive Dashboard | Charts | PDF Download | Real-time  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                          │
│                  Multi-Agent Orchestrator                    │
├─────────────────────────────────────────────────────────────┤
│  Horizontal Agents (Parallel Execution)                      │
│  ├─ Fundamental │ Technical │ Sentiment │ Governance │ PEAD │
│  └─ RAG Filing Agent                                         │
├─────────────────────────────────────────────────────────────┤
│  Vertical Leader                                             │
│  └─ Risk Analyst (Conflict Resolution & Aggregation)         │
├─────────────────────────────────────────────────────────────┤
│  Support Agents                                              │
│  ├─ XAI Agent (Groq LLaMA-3-70B)                            │
│  └─ Report Writer (Groq)                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌────────┐     ┌──────────┐    ┌─────────┐
    │  LLMs  │     │   Data   │    │ Storage │
    │ Groq   │     │ Finnhub  │    │  Redis  │
    │ Gemini │     │ AlphaV   │    │Postgres │
    │   HF   │     │ NewsAPI  │    │  FAISS  │
    │ Ollama │     │   SEC    │    └─────────┘
    └────────┘     └──────────┘
```

---

##  Agent Scoring Weights

| Agent | Weight | Purpose |
|-------|--------|---------|
| Fundamental | 25% | Financial health & ratios |
| Technical | 15% | Price trends & indicators |
| Sentiment | 10% | News & social sentiment |
| Governance | 15% | Red flags & fraud detection |
| PEAD | 10% | Earnings drift prediction |
| Financial Health | 20% | RAG filing analysis |
| Risk | 5% | Overall risk assessment |

**Final Score Thresholds:**
- 0-40: **SELL**
- 41-60: **HOLD**
- 61-100: **BUY**

---

##  Testing

```bash
# Backend tests
cd backend
pytest tests/ --cov=agents --cov=services

# Frontend tests
cd frontend
npm test

# Integration tests
pytest tests/integration/
```

---

##  Project Structure

```
cash-crew/
├── backend/
│   ├── agents/           # 8 AI agents
│   ├── services/         # API integrations (LLMs, data sources)
│   ├── models/           # Pydantic schemas
│   ├── config/           # Settings & configuration
│   ├── utils/            # Helper functions
│   ├── tests/            # Unit & integration tests
│   └── main.py           # FastAPI app
├── frontend/
│   ├── app/              # Next.js pages
│   ├── components/       # React components
│   ├── lib/              # Utilities
│   └── public/           # Static assets
├── docs/                 # Documentation
├── samples/              # Sample reports
└── docker-compose.yml    # Docker setup
```

---

##  Key Technologies

- **Backend**: Python, FastAPI, LangChain, Pandas
- **Frontend**: Next.js, TypeScript, Recharts, Tailwind CSS
- **LLMs**: Groq, Gemini, HuggingFace, Ollama
- **Data**: Finnhub, Alpha Vantage, News API, SEC EDGAR
- **Storage**: PostgreSQL, Redis, FAISS

---

##  Acknowledgments

- Groq for ultra-fast LLM inference
- Google for Gemini's long-context capabilities
- HuggingFace for open-source models
- Ollama for local LLM support

---

##  Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/cash-crew/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/cash-crew/discussions)


# cash-crew
