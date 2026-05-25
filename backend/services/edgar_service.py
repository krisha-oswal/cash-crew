"""
SEC EDGAR API service for earnings and financial data.
Completely free, no API key required.
"""
import requests
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from db.cache import cache_service

logger = logging.getLogger(__name__)

# Map of well-known tickers to CIK numbers to seed the lookup cache
KNOWN_CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "GOOG": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "TSLA": "0001318605",
    "NVDA": "0001045810",
    "JPM": "0000019617",
    "JNJ": "0000200406",
    "V": "0000732834",
    "WMT": "0000104169",
    "UNH": "0000731766",
    "BRK": "0001067983",
    "PG": "0000080424",
    "MA": "0001141391",
    "HD": "0000354950",
    "CVX": "0000093410",
    "MRK": "0000310158",
    "ABBV": "0001551152",
}

EDGAR_HEADERS = {"User-Agent": "CashCrew research@cashcrew.ai"}


class EdgarService:
    """SEC EDGAR API wrapper for earnings and financial data."""

    BASE_URL = "https://data.sec.gov"
    COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions"

    def _get_cik(self, ticker: str) -> Optional[str]:
        """Resolve ticker to CIK."""
        ticker_upper = ticker.upper()
        
        # Try cache first
        cached = cache_service.get(f"edgar:cik:{ticker_upper}")
        if cached:
            return cached

        # Try known CIK map
        if ticker_upper in KNOWN_CIKS:
            cik = KNOWN_CIKS[ticker_upper]
            cache_service.set(f"edgar:cik:{ticker_upper}", cik, expire_seconds=86400 * 30)
            return cik

        # Search SEC company search endpoint
        try:
            url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker_upper}%22&dateRange=custom&startdt=2020-01-01&forms=10-K"
            r = requests.get(url, headers=EDGAR_HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json()
            hits = data.get("hits", {}).get("hits", [])
            if hits:
                entity_id = hits[0].get("_source", {}).get("entity_id")
                if entity_id:
                    cik = str(entity_id).zfill(10)
                    cache_service.set(f"edgar:cik:{ticker_upper}", cik, expire_seconds=86400 * 30)
                    return cik
        except Exception as e:
            logger.warning(f"CIK lookup failed for {ticker}: {e}")

        # Fallback: EDGAR full-text search
        try:
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK={ticker_upper}&type=10-K&dateb=&owner=include&count=5&search_text=&action=getcompany&output=atom"
            r = requests.get(url, headers=EDGAR_HEADERS, timeout=10)
            r.raise_for_status()
            # Look for CIK in the XML
            import re
            match = re.search(r"CIK=(\d{10})", r.text)
            if not match:
                match = re.search(r"cik=(\d+)", r.text, re.IGNORECASE)
            if match:
                cik = match.group(1).zfill(10)
                cache_service.set(f"edgar:cik:{ticker_upper}", cik, expire_seconds=86400 * 30)
                return cik
        except Exception as e:
            logger.warning(f"EDGAR CIK search failed for {ticker}: {e}")

        return None

    def get_earnings_history(self, ticker: str) -> List[Dict[str, Any]]:
        """
        Get earnings per share history from SEC filings.
        Returns list of quarters with actual EPS and date.
        """
        cache_key = f"edgar:earnings:{ticker.upper()}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        cik = self._get_cik(ticker)
        if not cik:
            logger.warning(f"Could not resolve CIK for {ticker}")
            return []

        try:
            url = f"{self.COMPANY_FACTS_URL}/CIK{cik}.json"
            r = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"EDGAR company facts request failed for {ticker}: {e}")
            return []

        # Look for EPS data - try multiple XBRL concepts
        us_gaap = data.get("facts", {}).get("us-gaap", {})

        eps_concepts = [
            "EarningsPerShareBasic",
            "EarningsPerShareDiluted",
            "EarningsPerShareBasicAndDiluted",
        ]

        eps_units = None
        for concept in eps_concepts:
            concept_data = us_gaap.get(concept)
            if concept_data:
                units = concept_data.get("units", {})
                # Prefer USD/shares over pure USD
                eps_units = units.get("USD/shares") or units.get("USD")
                if eps_units:
                    break

        if not eps_units:
            logger.warning(f"No EPS data found in EDGAR for {ticker}")
            return []

        # Filter to quarterly filings (10-Q and 10-K) for the last 3 years
        cutoff = datetime.now() - timedelta(days=365 * 3)
        earnings = []

        for entry in eps_units:
            form = entry.get("form", "")
            if form not in ("10-Q", "10-K"):
                continue
            end_date_str = entry.get("end")
            if not end_date_str:
                continue
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                if end_date < cutoff:
                    continue
                # Convert to quarter label
                q = (end_date.month - 1) // 3 + 1
                period_label = f"{end_date.year}-Q{q}"
                earnings.append({
                    "period": period_label,
                    "end_date": end_date_str,
                    "actual": entry.get("val"),
                    "estimate": None,  # SEC doesn't have analyst estimates
                    "form": form,
                })
            except ValueError:
                continue

        # Deduplicate by period and keep the most recent filing per period
        seen = {}
        for e in earnings:
            p = e["period"]
            if p not in seen:
                seen[p] = e
        
        result = sorted(seen.values(), key=lambda x: x["end_date"], reverse=True)[:8]

        if result:
            cache_service.set(cache_key, result, expire_seconds=3600 * 6)
        return result

    def get_financial_metrics(self, ticker: str) -> Dict[str, Any]:
        """
        Get key financial metrics from SEC company facts (XBRL data).
        Returns dict of financials: revenue, net income, assets, liabilities, etc.
        """
        cache_key = f"edgar:financials:{ticker.upper()}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        cik = self._get_cik(ticker)
        if not cik:
            return {}

        try:
            url = f"{self.COMPANY_FACTS_URL}/CIK{cik}.json"
            r = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"EDGAR financials request failed for {ticker}: {e}")
            return {}

        us_gaap = data.get("facts", {}).get("us-gaap", {})

        def latest_annual(concept_name: str) -> Optional[float]:
            """Get the most recent annual value for a concept."""
            concept = us_gaap.get(concept_name)
            if not concept:
                return None
            units = concept.get("units", {})
            values = units.get("USD", [])
            # Filter by 10-K (annual)
            annual_vals = [v for v in values if v.get("form") == "10-K"]
            if not annual_vals:
                # Fallback to any recent
                annual_vals = values
            if not annual_vals:
                return None
            annual_vals.sort(key=lambda x: x.get("end", ""), reverse=True)
            return annual_vals[0].get("val")

        revenue = latest_annual("Revenues") or latest_annual("RevenueFromContractWithCustomerExcludingAssessedTax")
        net_income = latest_annual("NetIncomeLoss")
        total_assets = latest_annual("Assets")
        total_liabilities = latest_annual("Liabilities")
        total_equity = latest_annual("StockholdersEquity")
        current_assets = latest_annual("AssetsCurrent")
        current_liabilities = latest_annual("LiabilitiesCurrent")

        metrics = {}

        if revenue:
            metrics["revenue"] = revenue
        if net_income and revenue and revenue != 0:
            metrics["net_margin"] = round(net_income / revenue * 100, 2)
        if net_income and total_equity and total_equity != 0:
            metrics["roe"] = round(net_income / total_equity * 100, 2)
        if net_income and total_assets and total_assets != 0:
            metrics["roa"] = round(net_income / total_assets * 100, 2)
        if current_assets and current_liabilities and current_liabilities != 0:
            metrics["current_ratio"] = round(current_assets / current_liabilities, 2)
        if total_liabilities and total_equity and total_equity != 0:
            metrics["debt_to_equity"] = round(total_liabilities / total_equity, 2)
        if total_assets:
            metrics["total_assets"] = total_assets
        if total_equity:
            metrics["total_equity"] = total_equity

        if metrics:
            cache_service.set(cache_key, metrics, expire_seconds=3600 * 12)

        return metrics


edgar_service = EdgarService()
