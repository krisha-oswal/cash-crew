"""
Live stock price service.
- US/global stocks: Stooq (free, no API key)
- Indian stocks (NSE/BSE): NSE India official API (free, no API key)

Detects Indian tickers by .NS / .BO suffix or known patterns.
Users can also append .NS or .BO to their ticker when adding to portfolio.
"""
import requests
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from db.cache import cache_service

logger = logging.getLogger(__name__)

# Well-known Indian tickers that don't need a suffix
KNOWN_INDIAN_TICKERS = {
    "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "RELIANCE", "ONGC", "IOC",
    "BHEL", "NTPC", "POWERGRID", "TATASTEEL", "HINDALCO", "JSWSTEEL",
    "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "BAJFINANCE",
    "BAJAJFINSV", "HDFC", "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB",
    "BRITANNIA", "NESTLEIND", "HINDUNILVR", "ITC", "ASIANPAINT", "TITAN",
    "ULTRACEMCO", "GRASIM", "ADANIPORTS", "ADANIENT", "LT", "SIEMENS",
    "MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO",
    "INDIGO", "IRCTC", "ZOMATO", "PAYTM", "NAUKRI", "POLICYBAZAAR",
    "DMART", "TRENT", "VEDL", "COALINDIA",
}


class PriceService:
    """Fetches live stock prices from free public APIs."""

    NSE_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self):
        self._nse_session = None

    def _is_indian_ticker(self, ticker: str) -> bool:
        """Detect if a ticker is Indian (NSE/BSE)."""
        t = ticker.upper()
        if t.endswith(".NS") or t.endswith(".BO"):
            return True
        return t in KNOWN_INDIAN_TICKERS

    def _clean_ticker(self, ticker: str) -> tuple[str, str]:
        """Return (clean_ticker, market). market = 'IN' or 'US'."""
        t = ticker.upper()
        if t.endswith(".NS") or t.endswith(".BO"):
            return t.removesuffix(".NS").removesuffix(".BO"), "IN"
        if t in KNOWN_INDIAN_TICKERS:
            return t, "IN"
        return t, "US"

    def _get_nse_session(self) -> requests.Session:
        """Get or create an authenticated NSE session (cookies required)."""
        if self._nse_session is None:
            s = requests.Session()
            try:
                s.get("https://www.nseindia.com", headers=self.NSE_HEADERS, timeout=10)
            except Exception as e:
                logger.warning(f"NSE session init failed: {e}")
            self._nse_session = s
        return self._nse_session

    def _get_nse_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch live price from NSE India API."""
        cache_key = f"price:nse:{symbol.upper()}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        try:
            session = self._get_nse_session()
            url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol.upper()}"
            r = session.get(url, headers=self.NSE_HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json()

            price_info = data.get("priceInfo", {})
            info = data.get("info", {})
            intrinsic = data.get("industryInfo", {})

            last_price = price_info.get("lastPrice")
            if last_price is None:
                logger.warning(f"NSE returned no price for {symbol}")
                return None

            result = {
                "ticker": symbol.upper(),
                "price": float(last_price),
                "change": float(price_info.get("change", 0)),
                "change_pct": float(price_info.get("pChange", 0)),
                "high": float(price_info.get("intraDayHighLow", {}).get("max", 0) or 0),
                "low": float(price_info.get("intraDayHighLow", {}).get("min", 0) or 0),
                "open": float(price_info.get("open", 0)),
                "prev_close": float(price_info.get("previousClose", 0)),
                "volume": 0,  # Not directly available in this endpoint
                "currency": "INR",
                "exchange": "NSE",
                "company_name": info.get("companyName", symbol),
                "industry": intrinsic.get("basicIndustry", ""),
                "timestamp": datetime.now().isoformat(),
            }

            # Cache for 60 seconds (live data)
            cache_service.set(cache_key, result, expire_seconds=60)
            return result

        except Exception as e:
            logger.error(f"NSE price fetch failed for {symbol}: {e}")
            # Reset session on failure so next call retries auth
            self._nse_session = None
            return None

    def _get_stooq_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch EOD/live price from Stooq (US and global markets)."""
        cache_key = f"price:stooq:{symbol.upper()}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        try:
            # Stooq uses suffixes: .US for US, can also handle .UK, .JP etc.
            stooq_symbol = f"{symbol.lower()}.us"
            url = f"https://stooq.com/q/l/?s={stooq_symbol}&f=sd2t2ohlcv&e=csv"
            r = requests.get(url, timeout=8, headers={"User-Agent": "CashCrew/1.0"})
            r.raise_for_status()

            lines = r.text.strip().split("\n")
            if len(lines) < 2:
                return None

            parts = lines[1].split(",")
            if len(parts) < 7 or parts[1] == "N/D":
                logger.warning(f"Stooq returned no data for {symbol}")
                return None

            ticker_sym = parts[0]
            date_str = parts[1]        # YYYY-MM-DD
            time_str = parts[2]        # HH:MM:SS
            open_p = float(parts[3]) if parts[3] != "N/D" else 0
            high_p = float(parts[4]) if parts[4] != "N/D" else 0
            low_p = float(parts[5]) if parts[5] != "N/D" else 0
            close_p = float(parts[6]) if parts[6] != "N/D" else 0
            volume = int(float(parts[7])) if len(parts) > 7 and parts[7] != "N/D" else 0

            result = {
                "ticker": symbol.upper(),
                "price": close_p,
                "change": 0,   # Stooq CSV doesn't include change directly
                "change_pct": 0,
                "high": high_p,
                "low": low_p,
                "open": open_p,
                "prev_close": 0,
                "volume": volume,
                "currency": "USD",
                "exchange": "NASDAQ/NYSE",
                "company_name": symbol.upper(),
                "timestamp": f"{date_str}T{time_str}",
            }

            # Cache for 60 seconds  
            cache_service.set(cache_key, result, expire_seconds=60)
            return result

        except Exception as e:
            logger.error(f"Stooq price fetch failed for {symbol}: {e}")
            return None

    def get_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get live stock price. Auto-detects market (US vs India).
        
        For Indian stocks, use plain ticker (eg. TCS, INFY) or append .NS/.BO
        For US stocks, use plain ticker (eg. AAPL, MSFT, NVDA)
        """
        clean, market = self._clean_ticker(ticker)

        if market == "IN":
            result = self._get_nse_price(clean)
            if result:
                logger.info(f"Got NSE price for {clean}: ₹{result['price']}")
                return result
            logger.warning(f"Failed to get NSE price for {clean}")
            return None
        else:
            result = self._get_stooq_price(clean)
            if result:
                logger.info(f"Got Stooq price for {clean}: ${result['price']}")
                return result
            logger.warning(f"Failed to get Stooq price for {clean}")
            return None

    def get_batch_prices(self, tickers: list[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Fetch prices for multiple tickers."""
        results = {}
        for ticker in tickers:
            results[ticker.upper()] = self.get_price(ticker)
        return results


price_service = PriceService()
