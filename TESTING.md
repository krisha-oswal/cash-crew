# Cash Crew - Testing Guide

## 🧪 Complete Testing Workflow

### 1. Start the Backend

```bash
cd /Users/kriii/Desktop/cash-crew/backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Starting Cash Crew API...
INFO:     Registering LLM providers...
INFO:     Cash Crew API started successfully!
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Open the Frontend

Open `frontend/index.html` in your browser:

```bash
# macOS
open /Users/kriii/Desktop/cash-crew/frontend/index.html

# Or just double-click the file
```

### 3. Test Analysis

1. Enter a stock ticker (e.g., `AAPL`, `MSFT`, `TCS.NS`)
2. Select timeframe and risk preference
3. Click "Analyze Stock"
4. Wait 30-60 seconds for analysis
5. View results with:
   - BUY/HOLD/SELL recommendation
   - Overall score and confidence
   - Individual agent scores
   - Detailed XAI explanation
6. Download full text report

### 4. Test API Directly

```bash
# Health check
curl http://localhost:8000/health | python3 -m json.tool

# Analyze AAPL
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "timeframe": "1y",
    "risk_preference": "balanced"
  }' | python3 -m json.tool

# Download text report
curl -X POST http://localhost:8000/report/text \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "timeframe": "1y",
    "risk_preference": "balanced"
  }' > AAPL_report.txt
```

---

## 📊 What Gets Analyzed

### Phase 1: Horizontal Agents (Parallel)
1. **Fundamental Analyst**
   - Fetches financial data from Alpha Vantage/Finnhub
   - Calculates: ROE, ROA, D/E, P/E, P/B, Current Ratio, Quick Ratio
   - Scores based on financial health (0-100)

2. **Technical Analyst**
   - Fetches historical price data
   - Calculates: MA(50), MA(200), RSI, MACD, Bollinger Bands
   - Detects support/resistance levels
   - Scores based on technical signals (0-100)

3. **Sentiment Analyst**
   - Fetches news from News API/Finnhub
   - Analyzes sentiment using HuggingFace Mixtral LLM
   - Classifies articles as Positive/Neutral/Negative
   - Scores based on overall sentiment (0-100)

### Phase 2: Vertical Leader
4. **Risk Analyst**
   - Detects conflicts between agents
   - Calculates agent agreement score
   - Assesses data quality
   - Generates spider chart of all agent scores

### Phase 3: XAI & Reporting
5. **XAI Agent**
   - Generates detailed explanations using Groq LLaMA-3-70B
   - Calculates factor contributions
   - Creates confidence visualizations

6. **Report Writer**
   - Generates executive summary using Groq
   - Formats complete text report
   - Provides downloadable output

---

## ✅ Expected Results

### For AAPL (Apple Inc)
- **Fundamental**: Usually 70-80 (strong financials)
- **Technical**: Varies 50-75 (depends on market)
- **Sentiment**: Usually 60-75 (generally positive)
- **Risk**: Usually 65-75 (low conflict)
- **Final Score**: ~65-75 (BUY)
- **Confidence**: ~75-85%

### For TCS.NS (Tata Consultancy Services)
- **Fundamental**: Usually 75-85 (excellent financials)
- **Technical**: Varies 55-70
- **Sentiment**: Usually 65-75
- **Final Score**: ~70-80 (BUY)

---

## 🐛 Common Issues & Solutions

### Issue: "API key not configured"
**Solution:**
```bash
cd backend
cat .env  # Check if API keys are set
# If not, edit .env and add your keys
nano .env
```

### Issue: "No data available"
**Causes:**
- Invalid ticker symbol
- API rate limits exceeded
- API keys not working

**Solutions:**
- Try a different ticker (AAPL, MSFT are reliable)
- Wait a few minutes for rate limits to reset
- Verify API keys are valid

### Issue: "CORS error" in browser
**Solution:**
The backend is configured with CORS enabled. Make sure:
1. Backend is running on port 8000
2. Frontend is accessing http://localhost:8000
3. Check browser console for specific error

### Issue: Slow analysis (>2 minutes)
**Causes:**
- Free API tier rate limits
- LLM provider slowness
- Network issues

**Solutions:**
- Be patient on first run (cold start)
- Check LLM stats: http://localhost:8000/llm-stats
- Try offline mode (set DEMO_MODE=offline in .env)

---

## 📈 Performance Metrics

**Expected Latency:**
- Fundamental Agent: 2-5 seconds
- Technical Agent: 3-7 seconds
- Sentiment Agent: 20-40 seconds (LLM processing)
- Risk Agent: <1 second
- XAI Agent: 5-15 seconds (LLM generation)
- Report Writer: 3-8 seconds (LLM summary)
- **Total: 30-70 seconds**

**API Calls Made:**
- Alpha Vantage: 3-5 calls
- Finnhub: 2-4 calls
- News API: 1-2 calls
- HuggingFace: 5-10 calls (sentiment batches)
- Groq: 2-3 calls (XAI + summary)

---

## 🎯 Test Scenarios

### Scenario 1: Strong BUY Signal
```json
{
  "ticker": "AAPL",
  "timeframe": "1y",
  "risk_preference": "balanced"
}
```
**Expected:** Score 70-80, BUY recommendation

### Scenario 2: Mixed Signals
```json
{
  "ticker": "TSLA",
  "timeframe": "6m",
  "risk_preference": "aggressive"
}
```
**Expected:** Score 50-65, HOLD/BUY recommendation

### Scenario 3: Indian Stock
```json
{
  "ticker": "TCS.NS",
  "timeframe": "1y",
  "region": "India",
  "risk_preference": "conservative"
}
```
**Expected:** Score 70-85, BUY recommendation

---

## 📊 Monitoring

### Check System Health
```bash
curl http://localhost:8000/health
```

### Check LLM Usage
```bash
curl http://localhost:8000/llm-stats
```

### Check System Metrics
```bash
curl http://localhost:8000/metrics
```

### View Logs
Backend logs show:
- Agent execution progress
- LLM provider usage
- API call status
- Error messages

---

## 🎓 Understanding the Output

### Recommendation Thresholds
- **BUY**: Score ≥ 61
- **HOLD**: Score 41-60
- **SELL**: Score ≤ 40

### Confidence Levels
- **High (>70%)**: Strong data availability, low conflicts
- **Medium (50-70%)**: Moderate data, some uncertainty
- **Low (<50%)**: Limited data, high conflicts

### Agent Weights
- Fundamental: 25%
- Technical: 15%
- Sentiment: 10%
- Risk: 5%
- (Others not yet implemented: 45%)

---

## 💡 Pro Tips

1. **First analysis is slower** - LLM cold start
2. **US stocks have better data** - More news, better coverage
3. **Check confidence scores** - Low confidence = unreliable
4. **Read XAI explanations** - Understand the reasoning
5. **Download reports** - Keep records for comparison

---

**Happy Testing! 💰📊**
