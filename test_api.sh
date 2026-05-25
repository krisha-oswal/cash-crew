#!/bin/bash

# Quick test script for Cash Crew API

echo "🧪 Testing Cash Crew API"
echo "======================="
echo ""

# Check if server is running
echo "1. Checking if API is running..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ API is running"
else
    echo "❌ API is not running. Start it with:"
    echo "   cd backend && source venv/bin/activate && uvicorn main:app --reload"
    exit 1
fi

echo ""
echo "2. Health check..."
curl -s http://localhost:8000/health | python3 -m json.tool

echo ""
echo ""
echo "3. Testing stock analysis for AAPL..."
echo "   (This may take 30-60 seconds...)"
echo ""

curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "timeframe": "1y",
    "risk_preference": "balanced"
  }' | python3 -m json.tool

echo ""
echo ""
echo "✅ Test complete!"
echo ""
echo "To test with other stocks:"
echo "  US: AAPL, MSFT, GOOGL, TSLA"
echo "  India: TCS.NS, INFY.NS, RELIANCE.NS"
