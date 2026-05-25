"""
Finnhub API integration for financial data.
"""
import requests
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from config.settings import settings
from db.cache import cache_service

logger = logging.getLogger(__name__)


class FinnhubService:
    """Finnhub API service for financial data."""
    
    BASE_URL = "https://finnhub.io/api/v1"
    
    def __init__(self):
        self.api_key = settings.finnhub_api_key
        self.session = requests.Session()
    
    def is_available(self) -> bool:
        """Check if Finnhub service is available."""
        return bool(self.api_key)
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make API request to Finnhub."""
        if not self.is_available():
            raise Exception("Finnhub API key not configured")
        
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params['token'] = self.api_key
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Finnhub API request failed: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote for a symbol."""
        cache_key = f"finnhub:quote:{symbol}"
        cached = cache_service.get(cache_key)
        if cached: return cached
        
        res = self._make_request("quote", {"symbol": symbol})
        if res: cache_service.set(cache_key, res, expire_seconds=300) # 5 mins
        return res
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_company_profile(self, symbol: str) -> Dict[str, Any]:
        """Get company profile."""
        cache_key = f"finnhub:profile:{symbol}"
        cached = cache_service.get(cache_key)
        if cached: return cached
        
        res = self._make_request("stock/profile2", {"symbol": symbol})
        if res: cache_service.set(cache_key, res, expire_seconds=86400) # 1 day
        return res
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_financials(self, symbol: str, statement: str = "bs", freq: str = "annual") -> Dict[str, Any]:
        """
        Get financial statements.
        
        Args:
            symbol: Stock symbol
            statement: Statement type (bs=balance sheet, ic=income statement, cf=cash flow)
            freq: Frequency (annual, quarterly)
        """
        cache_key = f"finnhub:financials:{symbol}:{statement}:{freq}"
        cached = cache_service.get(cache_key)
        if cached: return cached
        
        res = self._make_request("stock/financials-reported", {
            "symbol": symbol,
            "statement": statement,
            "freq": freq
        })
        if res: cache_service.set(cache_key, res, expire_seconds=86400) # 1 day
        return res
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_basic_financials(self, symbol: str) -> Dict[str, Any]:
        """Get basic financial metrics."""
        cache_key = f"finnhub:basic_financials:{symbol}"
        cached = cache_service.get(cache_key)
        if cached: return cached
        
        res = self._make_request("stock/metric", {"symbol": symbol, "metric": "all"})
        if res: cache_service.set(cache_key, res, expire_seconds=86400) # 1 day
        return res
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_news(self, symbol: str, from_date: str, to_date: str) -> List[Dict[str, Any]]:
        """
        Get company news.
        
        Args:
            symbol: Stock symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
        """
        cache_key = f"finnhub:news:{symbol}:{from_date}:{to_date}"
        cached = cache_service.get(cache_key)
        if cached: return cached
        
        res = self._make_request("company-news", {
            "symbol": symbol,
            "from": from_date,
            "to": to_date
        })
        if res: cache_service.set(cache_key, res, expire_seconds=3600) # 1 hour
        return res
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_earnings(self, symbol: str) -> List[Dict[str, Any]]:
        """Get earnings data."""
        cache_key = f"finnhub:earnings:{symbol}"
        cached = cache_service.get(cache_key)
        if cached: return cached
        
        res = self._make_request("stock/earnings", {"symbol": symbol})
        if res: cache_service.set(cache_key, res, expire_seconds=43200) # 12 hours
        return res


# Global service instance
finnhub_service = FinnhubService()
