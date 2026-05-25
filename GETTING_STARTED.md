# Cash Crew - Getting Started Guide

## 🎯 Quick Start (5 Minutes)

### Step 1: Run Setup Script
```bash
chmod +x setup.sh
./setup.sh
```

This will:
- Create Python virtual environment
- Install all dependencies
- Create `.env` files from templates

### Step 2: Add API Keys

Edit `backend/.env` and add your API keys:

```bash
# Required for live demo
GROQ_API_KEY=gsk_...                    # Get from console.groq.com
GOOGLE_API_KEY=AIza...                  # Get from makersuite.google.com
HUGGINGFACE_API_KEY=hf_...              # Get from huggingface.co
FINNHUB_API_KEY=...                     # Get from finnhub.io
ALPHA_VANTAGE_API_KEY=...               # Get from alphavantage.co
NEWS_API_KEY=...                        # Get from newsapi.org

# Optional for offline demo
OLLAMA_BASE_URL=http://localhost:11434
```

### Step 3: Start the Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload
```

### Step 4: Test the API

Open http://localhost:8000/docs in your browser to see the interactive API documentation.

Or test with curl:
```bash
curl http://localhost:8000/health
```

---

## 🎬 Demo Modes

### Live Mode (Best for Hackathon Demo)
```bash
# In backend/.env
DEMO_MODE=live
```
- Uses real financial APIs
- Uses cloud LLMs (Groq, Gemini, HuggingFace)
- Best performance and accuracy

### Hybrid Mode (Development)
```bash
# In backend/.env
DEMO_MODE=hybrid
```
- Uses real financial APIs
- Uses Ollama local LLMs only
- No cloud LLM costs

### Offline Mode (No Internet)
```bash
# In backend/.env
DEMO_MODE=offline
```
- Uses mock financial data
- Uses Ollama local LLMs
- Perfect for offline demos

---

## 🔑 Getting API Keys (All Free Tiers!)

### 1. Groq (Required - Ultra Fast!)
1. Go to https://console.groq.com/
2. Sign up with GitHub/Google
3. Create API key
4. Free tier: 30 requests/minute

### 2. Google AI Studio (Required - Long Context)
1. Go to https://makersuite.google.com/app/apikey
2. Sign in with Google account
3. Create API key
4. Free tier available

### 3. HuggingFace (Required - Sentiment)
1. Go to https://huggingface.co/settings/tokens
2. Sign up/login
3. Create new token
4. Free inference API

### 4. Finnhub (Required - Financial Data)
1. Go to https://finnhub.io/register
2. Sign up for free account
3. Copy API key from dashboard
4. Free tier: 60 calls/minute

### 5. Alpha Vantage (Required - Historical Data)
1. Go to https://www.alphavantage.co/support/#api-key
2. Enter email to get free API key
3. Free tier: 25 calls/day

### 6. News API (Required - News Data)
1. Go to https://newsapi.org/register
2. Sign up for developer account
3. Copy API key
4. Free tier: 100 requests/day

---

## 🤖 Ollama Setup (Optional - For Offline Demo)

### Install Ollama
```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Or download from https://ollama.ai/
```

### Pull Required Models
```bash
ollama pull llama3      # For XAI agent
ollama pull mixtral     # For RAG agent
ollama pull mistral     # For report writer
```

### Verify Installation
```bash
ollama list
```

---

## 📊 Testing the System

### 1. Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "demo_mode": "live",
  "llm_providers": {
    "groq_llama3_70b": true,
    "gemini_1.5_pro": true,
    ...
  }
}
```

### 2. LLM Stats
```bash
curl http://localhost:8000/llm-stats
```

### 3. Analyze Stock (Coming Soon)
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "timeframe": "1y",
    "risk_preference": "balanced"
  }'
```

---

## 🐛 Troubleshooting

### "Module not found" errors
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### "API key not configured" errors
- Check that `.env` file exists in `backend/` directory
- Verify API keys are correctly set (no quotes needed)
- Restart the server after changing `.env`

### Ollama connection errors
```bash
# Check if Ollama is running
ollama list

# Start Ollama service (if needed)
ollama serve
```

### Rate limit errors
- Free tiers have rate limits
- Wait a few minutes and try again
- Consider upgrading to paid tiers for production

---

## 📚 Next Steps

1. ✅ Complete agent implementations (in progress)
2. ✅ Build frontend dashboard
3. ✅ Add PDF report generation
4. ✅ Implement backtesting
5. ✅ Create sample reports

---

## 💡 Tips for Hackathon Demo

1. **Pre-generate sample reports** for offline backup
2. **Use Ollama** as fallback if internet is unstable
3. **Test with both US and Indian stocks** (AAPL, TCS.NS)
4. **Show the hybrid LLM architecture** - judges love this!
5. **Explain the XAI features** - transparency is key

---

## 🆘 Need Help?

- Check the [README.md](README.md) for architecture details
- View API docs at http://localhost:8000/docs
- Open an issue on GitHub

---

**Ready to analyze some stocks! 💰📊**
