"""
Quick smoke test for PEAD and Sentiment agents.
Run from: /Users/kriii/Desktop/cash-crew/backend
Usage: python test_agents.py [TICKER]
"""
import asyncio
import sys
import os
import logging

# Allow running from backend directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(levelname)s  %(message)s"
)
logger = logging.getLogger("test_agents")

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

async def test_pead():
    print("\n" + "=" * 60)
    print(f"  PEAD AGENT — {TICKER}")
    print("=" * 60)

    from services.finnhub_service import finnhub_service
    from services.edgar_service import edgar_service

    print(f"\n[1] Finnhub available: {finnhub_service.is_available()}")

    # Test EDGAR fallback
    edgar_data = edgar_service.get_earnings_history(TICKER)
    print(f"[2] EDGAR EPS records: {len(edgar_data)}")
    if edgar_data:
        print(f"    Sample: period={edgar_data[0].get('period')}, actual={edgar_data[0].get('actual')}, estimate={edgar_data[0].get('estimate')}")

    # Run the full agent
    from agents.pead_agent import pead_agent
    result = await pead_agent.analyze(TICKER)

    print(f"\n[3] PEAD Score: {result.score:.1f}")
    print(f"    Confidence: {result.confidence:.2f}")
    print(f"    Factors: {result.factors}")
    print(f"    Explanation: {result.explanation}")

    assert result.score is not None, "Score is None!"
    assert 0 <= result.score <= 100, f"Score out of range: {result.score}"

    if result.score == 50.0 and result.confidence < 0.3:
        print("\n  ⚠️  Score is 50 with low confidence — likely no usable earnings data (add Finnhub key?)")
    else:
        print(f"\n  ✅ PEAD score is meaningful ({result.score:.1f})")


async def test_sentiment():
    print("\n" + "=" * 60)
    print(f"  SENTIMENT AGENT — {TICKER}")
    print("=" * 60)

    from services.news_service import news_service
    from services.llm_service import llm_router, LLMProvider

    # Check LLM availability
    for provider in [LLMProvider.GROQ_LLAMA3_70B, LLMProvider.GROQ_MIXTRAL,
                     LLMProvider.HUGGINGFACE_MIXTRAL, LLMProvider.OLLAMA_MIXTRAL]:
        svc = llm_router.providers.get(provider)
        available = svc.is_available() if svc else False
        print(f"[1] LLM {provider}: {'✅ available' if available else '❌ unavailable'}")

    # Test news sources
    rss_articles = news_service._get_rss_news(TICKER, TICKER)
    print(f"\n[2] Google News RSS articles: {len(rss_articles)}")
    if rss_articles:
        print(f"    Sample: {rss_articles[0].get('title', '')[:80]}")

    yf_articles = news_service.get_yfinance_news(TICKER)
    print(f"[3] yfinance articles: {len(yf_articles)}")
    if yf_articles:
        print(f"    Sample: {yf_articles[0].get('title', '')[:80]}")

    # Run the full agent
    from agents.sentiment_agent import sentiment_agent
    result = await sentiment_agent.analyze(TICKER)

    print(f"\n[4] Sentiment Score: {result.score:.1f}")
    print(f"    Confidence: {result.confidence:.2f}")
    print(f"    Factors: {result.factors}")
    print(f"    Article count: {result.metrics.get('positive_count', 0) + result.metrics.get('negative_count', 0) + result.metrics.get('neutral_count', 0)}")
    print(f"    Overall sentiment: {result.metrics.get('overall_sentiment', 'n/a')}")
    print(f"    Explanation: {result.explanation}")

    assert result.score is not None, "Score is None!"
    assert 0 <= result.score <= 100, f"Score out of range: {result.score}"

    if result.confidence < 0.25:
        print("\n  ⚠️  Low confidence — add a Groq API key for better LLM sentiment")
    else:
        print(f"\n  ✅ Sentiment score is meaningful ({result.score:.1f})")


async def main():
    print(f"\n🔍 Testing agents for ticker: {TICKER}")

    try:
        await test_pead()
    except Exception as e:
        print(f"\n  ❌ PEAD test failed: {e}")
        import traceback; traceback.print_exc()

    try:
        await test_sentiment()
    except Exception as e:
        print(f"\n  ❌ Sentiment test failed: {e}")
        import traceback; traceback.print_exc()

    print("\n" + "=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
