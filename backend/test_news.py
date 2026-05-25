import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.news_service import news_service

async def main():
    try:
        articles = news_service.get_company_news("Apple", "AAPL")
        print(f"Found {len(articles)} articles")
        if articles:
            print(articles[0].get('title'))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
