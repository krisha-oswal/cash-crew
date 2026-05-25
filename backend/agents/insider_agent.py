"""
Insider Trading Agent

Status: Always "experimental" / "partial" — no reliable free real-time SEC Form 4 feed is connected.

Behavior:
  - Attempts to fetch basic insider data via yfinance (limited availability)
  - If yfinance provides clean data, uses it with clear data_source labeling
  - NEVER uses random scoring or fabricated values
  - Returns score=None if no real data is available
  - Always includes warning about data limitations
"""
from typing import Any, Dict, List, Optional
from models.schemas import AgentScore
from agents.base_agent import BaseAgent
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class InsiderTradingAgent(BaseAgent):
    """
    Analyzes recent insider buying and selling activity.

    Data source: yfinance basic insider transactions (when available).
    Limitation: yfinance insider data is incomplete and often delayed.
    Does NOT use SEC EDGAR Form 4 real-time feed.
    """

    def __init__(self):
        super().__init__(agent_name="Insider Trading Agent")

    async def analyze(self, ticker: str, data: Dict[str, Any]) -> AgentScore:
        logger.info(f"Running insider trading analysis for {ticker}")

        STANDARD_WARNINGS = [
            "Experimental signal: excluded from the final weighted score.",
            "Insider data is not sourced from a real-time SEC Form 4 feed.",
            "yfinance insider data is limited and may be delayed or incomplete.",
            "Treat this signal as supplementary — not actionable on its own.",
        ]

        # In offline mode, skip entirely
        if settings.data_mode == "offline":
            return self.create_score(
                score=None,
                confidence=0.0,
                factors={},
                metrics={"data_mode": "offline"},
                visualizations=[],
                explanation="Insider agent skipped — offline mode.",
                status="failed",
                warnings=["Insider agent disabled in offline mode."],
            )

        # Try yfinance insider data
        insider_result = await self._fetch_yfinance_insider(ticker)

        if not insider_result["available"]:
            # No data — return null score, do NOT fabricate
            return self.create_score(
                score=None,
                confidence=0.0,
                factors={},
                metrics={"error": insider_result.get("error", "No insider data returned")},
                visualizations=[],
                explanation="Experimental insider signal: no insider trading data available from yfinance for this ticker.",
                status="partial",
                signals=[],
                risks=[],
                warnings=STANDARD_WARNINGS + ["No yfinance insider data available for this ticker."],
                data_source="experimental yfinance insider data (excluded from final score)",
            )

        transactions = insider_result["transactions"]
        buyer_count = insider_result["buyer_count"]
        seller_count = insider_result["seller_count"]
        net_shares_bought = insider_result["net_shares_bought"]

        # Build signals & risks from real data
        signals: List[str] = []
        risks: List[str] = []

        if buyer_count > seller_count and buyer_count > 0:
            signals.append(f"{buyer_count} insider buyer(s) vs {seller_count} seller(s) recently.")
            if net_shares_bought > 0:
                signals.append(f"Net insider purchase of ~{net_shares_bought:,.0f} shares.")
        elif seller_count > buyer_count and seller_count > 0:
            risks.append(f"{seller_count} insider seller(s) vs {buyer_count} buyer(s) recently.")
            if net_shares_bought < 0:
                risks.append(f"Net insider sale of ~{abs(net_shares_bought):,.0f} shares.")
        else:
            signals.append("Insider activity is balanced — no strong directional signal.")

        # Score: only if we have real transaction data
        # Range: buyer-heavy → higher score, seller-heavy → lower score
        # Neutral at 50. No randomness.
        total_activity = buyer_count + seller_count
        if total_activity == 0:
            raw_score = 50.0
            net_label = "Neutral"
        elif buyer_count > seller_count:
            ratio = buyer_count / total_activity
            raw_score = 50.0 + ratio * 30.0   # Max ~80
            net_label = "Bullish"
        elif seller_count > buyer_count:
            ratio = seller_count / total_activity
            raw_score = 50.0 - ratio * 30.0   # Min ~20
            net_label = "Bearish"
        else:
            raw_score = 50.0
            net_label = "Neutral"

        final_score = max(0.0, min(100.0, raw_score))

        explanation = (
            f"Experimental insider signal based on limited yfinance data: "
            f"{buyer_count} insider buyer(s), {seller_count} seller(s). Net signal: {net_label}."
        )

        return self.create_score(
            score=final_score,
            confidence=0.40,   # Low confidence — yfinance data is limited
            factors={"insider_conviction": 1.0},
            metrics={
                "buyer_count": buyer_count,
                "seller_count": seller_count,
                "net_shares_bought": net_shares_bought,
                "net_activity": net_label,
                "transaction_count": len(transactions),
            },
            visualizations=[],
            explanation=explanation,
            status="partial",
            signals=signals,
            risks=risks,
            warnings=STANDARD_WARNINGS,
            data_source="experimental yfinance insider data (excluded from final score)",
        )

    async def _fetch_yfinance_insider(self, ticker: str) -> Dict[str, Any]:
        """
        Attempt to fetch insider transactions from yfinance.
        Returns structured result dict with 'available' flag.
        """
        result: Dict[str, Any] = {
            "available": False,
            "transactions": [],
            "buyer_count": 0,
            "seller_count": 0,
            "net_shares_bought": 0,
            "error": None,
        }

        try:
            import yfinance as yf
            import pandas as pd

            t = yf.Ticker(ticker)
            insider_df = t.insider_transactions

            # yfinance returns None or empty DataFrame when no data
            if insider_df is None or (hasattr(insider_df, "empty") and insider_df.empty):
                result["error"] = "yfinance returned no insider transactions"
                return result

            # Normalise column names (yfinance API changes over versions)
            insider_df.columns = [c.lower().replace(" ", "_") for c in insider_df.columns]

            # Filter to recent 6 months if date column exists
            if "start_date" in insider_df.columns or "date" in insider_df.columns:
                date_col = "start_date" if "start_date" in insider_df.columns else "date"
                insider_df[date_col] = pd.to_datetime(insider_df[date_col], errors="coerce")
                cutoff = pd.Timestamp.now() - pd.DateOffset(months=6)
                insider_df = insider_df[insider_df[date_col] >= cutoff]

            if insider_df.empty:
                result["error"] = "No recent insider transactions in last 6 months"
                return result

            # Count buyers vs sellers using 'transaction' or 'text' column
            tx_col = next(
                (c for c in insider_df.columns if c in ("transaction", "text", "relation")),
                None
            )
            shares_col = next(
                (c for c in insider_df.columns if "share" in c or "value" in c),
                None
            )

            buyer_count = 0
            seller_count = 0
            net_shares = 0

            for _, row in insider_df.iterrows():
                tx_text = str(row.get(tx_col, "")).lower() if tx_col else ""
                is_buy = any(w in tx_text for w in ("purchase", "buy", "acquisition", "acquired"))
                is_sell = any(w in tx_text for w in ("sale", "sell", "sold", "disposition"))

                shares = 0
                if shares_col:
                    try:
                        shares = float(str(row[shares_col]).replace(",", ""))
                    except Exception:
                        shares = 0

                if is_buy:
                    buyer_count += 1
                    net_shares += shares
                elif is_sell:
                    seller_count += 1
                    net_shares -= shares

            result["available"] = True
            result["transactions"] = insider_df.to_dict("records")
            result["buyer_count"] = buyer_count
            result["seller_count"] = seller_count
            result["net_shares_bought"] = net_shares

        except ImportError:
            result["error"] = "yfinance not installed"
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"InsiderAgent yfinance fetch failed: {e}")

        return result


insider_agent = InsiderTradingAgent()
