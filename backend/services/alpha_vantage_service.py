"""
Alpha Vantage API integration for historical data and technical indicators.
"""
import requests
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import pandas as pd
import logging

from config.settings import settings
from db.cache import cache_service

logger = logging.getLogger(__name__)


class AlphaVantageService:
    """Alpha Vantage API service for historical data."""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self):
        self.api_key = settings.alpha_vantage_api_key
        self.session = requests.Session()
    
    def is_available(self) -> bool:
        """Check if Alpha Vantage service is available."""
        return bool(self.api_key)
    
    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request to Alpha Vantage."""
        if not self.is_available():
            raise Exception("Alpha Vantage API key not configured")
        
        params['apikey'] = self.api_key
        
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Alpha Vantage API request failed: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_daily_prices(self, symbol: str, outputsize: str = "compact") -> pd.DataFrame:
        """
        Get daily price data.
        
        Args:
            symbol: Stock symbol
            outputsize: compact (100 days) or full (20+ years)
        """
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize
        }
        
        cache_key = f"av:daily:{symbol}:{outputsize}"
        cached = cache_service.get(cache_key)
        if cached:
            data = cached
        else:
            data = self._make_request(params)
            if data and "Time Series (Daily)" in data:
                cache_service.set(cache_key, data, expire_seconds=86400) # 1 day
        
        if "Time Series (Daily)" in data:
            df = pd.DataFrame.from_dict(data["Time Series (Daily)"], orient='index')
            df.index = pd.to_datetime(df.index)
            df = df.astype(float)
            df.columns = ['open', 'high', 'low', 'close', 'adjusted_close', 'volume', 'dividend', 'split']
            return df.sort_index()
        else:
            raise Exception(f"Failed to get daily prices: {data.get('Note', data.get('Error Message', 'Unknown error'))}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_sma(self, symbol: str, interval: str = "daily", time_period: int = 50) -> pd.DataFrame:
        """Get Simple Moving Average."""
        params = {
            "function": "SMA",
            "symbol": symbol,
            "interval": interval,
            "time_period": time_period,
            "series_type": "close"
        }
        
        cache_key = f"av:sma:{symbol}:{interval}:{time_period}"
        cached = cache_service.get(cache_key)
        if cached:
            data = cached
        else:
            data = self._make_request(params)
            if data and "Technical Analysis: SMA" in data:
                cache_service.set(cache_key, data, expire_seconds=86400)
        
        if "Technical Analysis: SMA" in data:
            df = pd.DataFrame.from_dict(data["Technical Analysis: SMA"], orient='index')
            df.index = pd.to_datetime(df.index)
            df = df.astype(float)
            return df.sort_index()
        else:
            raise Exception(f"Failed to get SMA: {data.get('Note', 'Unknown error')}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_rsi(self, symbol: str, interval: str = "daily", time_period: int = 14) -> pd.DataFrame:
        """Get Relative Strength Index."""
        params = {
            "function": "RSI",
            "symbol": symbol,
            "interval": interval,
            "time_period": time_period,
            "series_type": "close"
        }
        
        cache_key = f"av:rsi:{symbol}:{interval}:{time_period}"
        cached = cache_service.get(cache_key)
        if cached:
            data = cached
        else:
            data = self._make_request(params)
            if data and "Technical Analysis: RSI" in data:
                cache_service.set(cache_key, data, expire_seconds=86400)
        
        if "Technical Analysis: RSI" in data:
            df = pd.DataFrame.from_dict(data["Technical Analysis: RSI"], orient='index')
            df.index = pd.to_datetime(df.index)
            df = df.astype(float)
            return df.sort_index()
        else:
            raise Exception(f"Failed to get RSI: {data.get('Note', 'Unknown error')}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_macd(self, symbol: str, interval: str = "daily") -> pd.DataFrame:
        """Get MACD indicator."""
        params = {
            "function": "MACD",
            "symbol": symbol,
            "interval": interval,
            "series_type": "close"
        }
        
        cache_key = f"av:macd:{symbol}:{interval}"
        cached = cache_service.get(cache_key)
        if cached:
            data = cached
        else:
            data = self._make_request(params)
            if data and "Technical Analysis: MACD" in data:
                cache_service.set(cache_key, data, expire_seconds=86400)
        
        if "Technical Analysis: MACD" in data:
            df = pd.DataFrame.from_dict(data["Technical Analysis: MACD"], orient='index')
            df.index = pd.to_datetime(df.index)
            df = df.astype(float)
            return df.sort_index()
        else:
            raise Exception(f"Failed to get MACD: {data.get('Note', 'Unknown error')}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_company_overview(self, symbol: str) -> Dict[str, Any]:
        """Get company fundamental data."""
        params = {
            "function": "OVERVIEW",
            "symbol": symbol
        }
        
        cache_key = f"av:overview:{symbol}"
        cached = cache_service.get(cache_key)
        if cached: return cached
        
        data = self._make_request(params)
        if data:
            cache_service.set(cache_key, data, expire_seconds=86400)
        return data


# Global service instance
alpha_vantage_service = AlphaVantageService()
