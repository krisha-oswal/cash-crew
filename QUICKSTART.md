# Cash Crew - Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Step 1: Setup (First Time Only)

```bash
cd /Users/kriii/Desktop/cash-crew
./setup.sh
```

This will:
- Create Python virtual environment
- Install all dependencies
- Create `.env` file

### Step 2: Add API Keys

Edit `backend/.env` and add at least these keys:

```bash
# Required for basic functionality
GROQ_API_KEY=gsk_...                    # Get from console.groq.com
ALPHA_VANTAGE_API_KEY=...               # Get from alphavantage.co
FINNHUB_API_KEY=...                     # Get from finnhub.io

# Optional but recommended
GOOGLE_API_KEY=AIza...                  # Get from makersuite.google.com
HUGGINGFACE_API_KEY=hf_...              # Get from huggingface.co
NEWS_API_KEY=...                        # Get from newsapi.org
```

**Don't have API keys?** See [GETTING_STARTED.md](GETTING_STARTED.md) for links to get free API keys.

### Step 3: Start the Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Starting Cash Crew API...
INFO:     Cash Crew API started successfully!
```

### Step 4: Test the API

Open a new terminal and run:

```bash
cd /Users/kriii/Desktop/cash-crew
./test_api.sh
```

Or test manually:

```bash
# Health check
curl http://localhost:8000/health

# Analyze a stock (takes 30-60 seconds)
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "timeframe": "1y",
    "risk_preference": "balanced"
  }'
```

### Step 5: View API Docs

Open in your browser:
- **Interactive API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **LLM Stats**: http://localhost:8000/llm-stats

---

## ✅ What's Working Now

### Implemented Agents (Phase 1)
1. **Fundamental Analyst** ✅
   - Fetches financial data from Alpha Vantage & Finnhub
   - Calculates: ROE, ROA, D/E, P/E, P/B, Current Ratio, Quick Ratio
   - Scores 0-100 based on financial health
   - Generates bar chart visualizations

2. **Technical Analyst** ✅
   - Fetches historical price data
   - Calculates: MA(50), MA(200), RSI, MACD, Bollinger Bands
   - Detects support/resistance levels
   - Scores 0-100 based on technical signals
   - Generates price charts with indicators

3. **Sentiment Analyst** ✅
   - Fetches news from News API & Finnhub
   - Analyzes sentiment using HuggingFace Mixtral LLM
   - Classifies articles as Positive/Neutral/Negative
   - Scores 0-100 based on overall sentiment
   - Generates sentiment distribution charts

### Orchestration ✅
- Parallel execution of all 3 agents
- Weighted score aggregation (Fundamental: 25%, Technical: 15%, Sentiment: 10%)
- BUY/HOLD/SELL recommendation based on final score:
  - **BUY**: Score ≥ 61
  - **HOLD**: Score 41-60
  - **SELL**: Score ≤ 40
- Confidence calculation
- XAI explanations

---

## 📊 Example Analysis

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "timeframe": "1y",
    "risk_preference": "balanced"
  }' | python3 -m json.tool
```

**Expected Response:**
```json
{
  "ticker": "AAPL",
  "company_name": "Apple Inc",
  "analysis_date": "2026-02-07T18:09:38Z",
  "fundamental_score": {
    "agent_name": "Fundamental Analyst",
    "score": 75.2,
    "confidence": 0.85,
    "explanation": "Strong fundamental health with solid financial metrics..."
  },
  "technical_score": {
    "agent_name": "Technical Analyst",
    "score": 68.5,
    "confidence": 0.78,
    "explanation": "Mixed technical signals with neutral bias..."
  },
  "sentiment_score": {
    "agent_name": "Sentiment Analyst",
    "score": 72.3,
    "confidence": 0.82,
    "explanation": "Predominantly positive sentiment..."
  },
  "final_score": 71.8,
  "recommendation": "BUY",
  "confidence": 0.82,
  "latency_seconds": 45.2
}
```

---

## 🧪 Test Different Stocks

### US Stocks
```bash
# Apple
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "timeframe": "1y"}'

# Microsoft
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"ticker": "MSFT", "timeframe": "1y"}'

# Tesla
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"ticker": "TSLA", "timeframe": "1y"}'
```

### Indian Stocks
```bash
# TCS
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"ticker": "TCS.NS", "timeframe": "1y", "region": "India"}'

# Infosys
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"ticker": "INFY.NS", "timeframe": "1y", "region": "India"}'
```

---

## 🐛 Troubleshooting

### "Module not found" errors
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### "API key not configured"
- Make sure `.env` file exists in `backend/` directory
- Check that API keys are set correctly (no quotes needed)
- Restart the server after changing `.env`

### "No data available" errors
- Check that your API keys are valid
- Some free tiers have rate limits - wait a few minutes
- Try a different stock ticker

### Slow responses
- First request may be slower (cold start)
- Free API tiers may have slower response times
- Sentiment analysis with LLM takes 20-40 seconds

---

## 📈 Next Steps

### Still To Implement
- [ ] Governance & Fraud Agent
- [ ] PEAD Analyst Agent
- [ ] RAG Filing & Financial Health Agent
- [ ] Risk Analyst Agent (Vertical Leader)
- [ ] XAI Reasoning Agent (enhanced)
- [ ] Report Writer Agent (PDF generation)
- [ ] Frontend Dashboard (Next.js)

### Current Capabilities
✅ Fundamental analysis with 7 key ratios  
✅ Technical analysis with 5 indicators  
✅ Sentiment analysis with LLM  
✅ Weighted scoring and recommendations  
✅ Parallel agent execution  
✅ Confidence scoring  
✅ RESTful API with OpenAPI docs  

---

## 💡 Tips

1. **Use the interactive docs** at http://localhost:8000/docs to test the API
2. **Check LLM stats** at http://localhost:8000/llm-stats to see provider usage
3. **Monitor logs** in the terminal to see agent execution
4. **Start with US stocks** (AAPL, MSFT) - they have better data availability
5. **Be patient** - first analysis takes 30-60 seconds

---

## 🎯 Demo Mode

For offline demos or to save API costs:

```bash
# In backend/.env
DEMO_MODE=offline
```

This will:
- Use mock financial data
- Use Ollama local LLMs (if installed)
- Work without internet

---

**Ready to analyze! 💰📊**
