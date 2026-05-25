"""
News API integration for company news and sentiment analysis.
Includes automatic fallback to Google News RSS (no API key required).
"""
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from config.settings import settings

logger = logging.getLogger(__name__)


class NewsService:
    """News API service for fetching company news."""
    
    BASE_URL = "https://newsapi.org/v2"
    
    def __init__(self):
        self.api_key = settings.news_api_key
        self.session = requests.Session()
    
    def is_available(self) -> bool:
        """Check if News API service is available."""
        return bool(self.api_key)
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request to News API."""
        if not self.is_available():
            raise Exception("News API key not configured")
        
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {"X-Api-Key": self.api_key}
        
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"News API request failed: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_company_news(
        self,
        company_name: str,
        ticker: Optional[str] = None,
        days_back: int = 30,
        language: str = "en",
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent news articles about a company.
        
        Args:
            company_name: Company name to search for
            ticker: Optional ticker symbol to include in search
            days_back: Number of days to look back
            language: Language code (en, etc.)
            page_size: Number of articles to return (max 100)
        
        Returns:
            List of news articles
        """
        # Return RSS news if API key is not configured or in demo mode
        if not self.api_key or self.api_key in ("", "your_news_api_key_here"):
            logger.info(f"No NewsAPI key — falling back to Google News RSS for {company_name}")
            return self._get_rss_news(company_name, ticker)
            
        # Build search query
        query_parts = [company_name]
        if ticker:
            query_parts.append(ticker)
        query = " OR ".join(query_parts)
        
        # Calculate date range
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)
        
        params = {
            "q": query,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "language": language,
            "sortBy": "relevancy",
            "pageSize": page_size
        }
        
        data = self._make_request("everything", params)
        
        if data.get("status") == "ok":
            return data.get("articles", [])
        else:
            logger.warning(f"News API returned status: {data.get('status')}")
            return []
    
    def _get_rss_news(self, company_name: str, ticker: Optional[str]) -> List[Dict[str, Any]]:
        """Fetch real news from Google News RSS feed. No API key required."""
        articles = []
        query_term = ticker if ticker else company_name
        
        urls = [
            f"https://news.google.com/rss/search?q={query_term}+stock&hl=en-US&gl=US&ceid=US:en",
            f"https://news.google.com/rss/search?q={company_name}&hl=en-US&gl=US&ceid=US:en",
        ]
        
        for rss_url in urls:
            if len(articles) >= 20:
                break
            try:
                response = requests.get(rss_url, timeout=8, headers={"User-Agent": "CashCrew/1.0"})
                response.raise_for_status()
                root = ET.fromstring(response.content)
                channel = root.find('channel')
                if channel is None:
                    continue
                for item in channel.findall('item'):
                    title_elem = item.find('title')
                    desc_elem = item.find('description')
                    pub_date_elem = item.find('pubDate')
                    link_elem = item.find('link')
                    source_elem = item.find('source')
                    
                    if title_elem is None:
                        continue
                    
                    # Clean HTML from title and description
                    title = title_elem.text or ""
                    description = (desc_elem.text or "") if desc_elem is not None else ""
                    link = link_elem.text if link_elem is not None else ""
                    
                    # Parse pubDate
                    pub_date = ""
                    if pub_date_elem is not None and pub_date_elem.text:
                        try:
                            from email.utils import parsedate_to_datetime
                            pub_date = parsedate_to_datetime(pub_date_elem.text).isoformat()
                        except Exception:
                            pub_date = datetime.now().isoformat()
                    
                    # Source name from the source attribute or title suffix
                    source_name = "Google News"
                    if source_elem is not None and source_elem.text:
                        source_name = source_elem.text
                    elif " - " in title:
                        parts = title.rsplit(" - ", 1)
                        if len(parts) == 2:
                            title = parts[0].strip()
                            source_name = parts[1].strip()
                    
                    articles.append({
                        "title": title,
                        "description": description[:500],
                        "publishedAt": pub_date,
                        "url": link,
                        "source": {"name": source_name}
                    })
            except Exception as e:
                logger.warning(f"RSS fetch failed for {rss_url}: {e}")
                continue
        
        logger.info(f"Fetched {len(articles)} articles from Google News RSS for {query_term}")
        return articles[:30]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_top_headlines(
        self,
        query: str,
        category: str = "business",
        country: str = "us",
        page_size: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get top headlines.
        
        Args:
            query: Search query
            category: News category
            country: Country code (us, in, etc.)
            page_size: Number of articles to return
        
        Returns:
            List of news articles
        """
        params = {
            "q": query,
            "category": category,
            "country": country,
            "pageSize": page_size
        }
        
        data = self._make_request("top-headlines", params)
        
        if data.get("status") == "ok":
            return data.get("articles", [])
        else:
            logger.warning(f"News API returned status: {data.get('status')}")
            return []


    def get_yfinance_news(self, ticker: str) -> List[Dict[str, Any]]:
        """
        Fetch news from yfinance (free, no API key required).
        Returns articles in the same schema as get_company_news().
        """
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            raw_news = t.news  # List of dicts from yfinance
            if not raw_news:
                logger.warning(f"yfinance returned no news for {ticker}")
                return []

            articles = []
            for item in raw_news:
                # yfinance schema: title, link, publisher, providerPublishTime, type, thumbnail, relatedTickers
                title = item.get("title") or item.get("headline", "")
                if not title:
                    continue

                pub_time = item.get("providerPublishTime")
                pub_date = ""
                if pub_time:
                    try:
                        pub_date = datetime.utcfromtimestamp(pub_time).isoformat()
                    except Exception:
                        pub_date = ""

                publisher = item.get("publisher", "yfinance")

                articles.append({
                    "title": title,
                    "description": item.get("summary", ""),
                    "publishedAt": pub_date,
                    "url": item.get("link", ""),
                    "source": {"name": publisher},
                })

            logger.info(f"Fetched {len(articles)} articles from yfinance for {ticker}")
            return articles

        except ImportError:
            logger.warning("yfinance not installed — skipping yfinance news fallback")
            return []
        except Exception as e:
            logger.warning(f"yfinance news fetch failed for {ticker}: {e}")
            return []


# Global service instance
news_service = NewsService()

