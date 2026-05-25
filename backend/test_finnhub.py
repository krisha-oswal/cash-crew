import asyncio
import sys
import os
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.finnhub_service import finnhub_service

async def main():
    try:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        articles = finnhub_service.get_news("AAPL", from_date, to_date)
        print(f"Found {len(articles)} articles from finnhub")
        if articles:
            print(articles[0].get('headline'))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
