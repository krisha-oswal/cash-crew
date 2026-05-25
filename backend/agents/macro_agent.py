"""
Macro Economic Agent — Uses yfinance proxy indicators.

Data sources (all via yfinance, no API key required):
  IRX/^IRX    → 13-week Treasury Bill yield (short-term rates proxy)
  TNX/^TNX    → 10-year Treasury yield (long-term rates)
  VIX/^VIX    → CBOE Volatility Index (market fear gauge)
  GSPC/^GSPC  → S&P 500 (broad market trend)

Status: always "partial" — proxy data, not full macro modeling.
"""
from typing import Any, Dict, List, Optional
from models.schemas import AgentScore
from agents.base_agent import BaseAgent
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class MacroEconomicAgent(BaseAgent):
    """
    Analyzes macroeconomic conditions using yfinance proxy indicators.

    Limitations:
    - Treasury yields used as interest rate proxies (not FOMC data)
    - No GDP growth data (not available from free sources)
    - VIX used as market sentiment proxy
    - Always marks outputs as "partial" to reflect these limitations
    """

    def __init__(self):
        super().__init__(agent_name="Macro Economic Agent")

    async def analyze(self, ticker: str, data: Dict[str, Any]) -> AgentScore:
        logger.info(f"Running macro economic analysis for {ticker}")

        # In offline mode, return partial with explanation
        if settings.data_mode == "offline":
            return self.create_score(
                score=None,
                confidence=0.0,
                factors={},
                metrics={"data_mode": "offline"},
                visualizations=[],
                explanation="Macro agent disabled in offline mode.",
                status="failed",
                warnings=["Macro agent skipped — offline mode active."],
            )

        macro_data = await self._fetch_macro_proxies()

        if not macro_data["available"]:
            return self.create_score(
                score=None,
                confidence=0.0,
                factors={},
                metrics={"error": macro_data.get("error", "Unknown fetch error")},
                visualizations=[],
                explanation="Unable to fetch macro proxy data.",
                status="failed",
                warnings=[
                    "yfinance macro proxy fetch failed.",
                    macro_data.get("error", ""),
                ],
            )

        # Score the macro environment
        factor_scores, signals, risks = self._score_macro_environment(macro_data)

        if not factor_scores:
            return self.create_score(
                score=None,
                confidence=0.1,
                factors={},
                metrics=macro_data,
                visualizations=[],
                explanation="Macro proxy data fetched but could not be scored.",
                status="partial",
                warnings=["Insufficient macro data to produce a reliable score."],
            )

        overall_score = sum(factor_scores.values()) / len(factor_scores)

        explanation_parts = []
        if macro_data.get("short_rate") is not None:
            explanation_parts.append(
                f"Short-term rates ({macro_data.get('short_rate_symbol', 'IRX')}) at {macro_data['short_rate']:.2f}%."
            )
        if macro_data.get("long_rate") is not None:
            explanation_parts.append(
                f"10-yr yield ({macro_data.get('long_rate_symbol', 'TNX')}) at {macro_data['long_rate']:.2f}%."
            )
        if macro_data.get("vix") is not None:
            vix_label = "elevated" if macro_data["vix"] > 25 else "low"
            explanation_parts.append(
                f"VIX at {macro_data['vix']:.1f} ({vix_label} fear)."
            )
        if macro_data.get("sp500_change_pct") is not None:
            direction = "up" if macro_data["sp500_change_pct"] > 0 else "down"
            explanation_parts.append(
                f"S&P 500 is {direction} {abs(macro_data['sp500_change_pct']):.1f}% over 30d."
            )

        return self.create_score(
            score=overall_score,
            confidence=0.55,  # Capped — these are proxies, not full macro models
            factors={k: float(v) for k, v in factor_scores.items()},
            metrics=macro_data,
            visualizations=[],
            explanation=" ".join(explanation_parts) if explanation_parts else "Macro proxy analysis complete.",
            status="partial",
            signals=signals,
            risks=risks,
            warnings=[
                "Macro analysis based on yfinance proxy indicators (IRX/TNX/VIX/GSPC, with caret-symbol fallbacks).",
                "No GDP, CPI, or FOMC data is used. Score reflects market-based proxies only.",
            ],
            data_source="yfinance proxy indicators (IRX/TNX/VIX/GSPC)",
        )

    async def _fetch_macro_proxies(self) -> Dict[str, Any]:
        """
        Fetch macro proxy data from yfinance.
        Returns dict with available fields and an 'available' boolean.
        """
        result: Dict[str, Any] = {
            "available": False,
            "short_rate": None,   # ^IRX — 13-week T-bill
            "long_rate": None,    # ^TNX — 10-year yield
            "vix": None,          # ^VIX
            "sp500_change_pct": None,  # S&P 500 30-day %change
            "short_rate_symbol": None,
            "long_rate_symbol": None,
            "vix_symbol": None,
            "sp500_symbol": None,
        }
        fetched_any = False

        try:
            import yfinance as yf

            def latest_close(symbols: List[str], period: str = "5d") -> tuple[Optional[float], Optional[str]]:
                for symbol in symbols:
                    try:
                        hist = yf.Ticker(symbol).history(period=period)
                        if hist is not None and not hist.empty:
                            return float(hist["Close"].iloc[-1]), symbol
                    except Exception as e:
                        logger.warning(f"Macro: {symbol} fetch failed: {e}")
                return None, None

            def change_pct(symbols: List[str], period: str = "35d") -> tuple[Optional[float], Optional[str]]:
                for symbol in symbols:
                    try:
                        hist = yf.Ticker(symbol).history(period=period)
                        if hist is not None and len(hist) >= 2:
                            price_now = float(hist["Close"].iloc[-1])
                            price_then = float(hist["Close"].iloc[0])
                            if price_then > 0:
                                return ((price_now - price_then) / price_then) * 100, symbol
                    except Exception as e:
                        logger.warning(f"Macro: {symbol} fetch failed: {e}")
                return None, None

            # Short-term interest rate proxy (^IRX = 13-week T-bill annualised %)
            value, symbol = latest_close(["^IRX", "IRX"])
            if value is not None:
                result["short_rate"] = value
                result["short_rate_symbol"] = symbol
                fetched_any = True

            # Long-term rate proxy (^TNX = 10-year Treasury yield %)
            value, symbol = latest_close(["^TNX", "TNX"])
            if value is not None:
                result["long_rate"] = value
                result["long_rate_symbol"] = symbol
                fetched_any = True

            # VIX — market fear gauge
            value, symbol = latest_close(["^VIX", "VIX"])
            if value is not None:
                result["vix"] = value
                result["vix_symbol"] = symbol
                fetched_any = True

            # S&P 500 30-day % change
            value, symbol = change_pct(["^GSPC", "GSPC"])
            if value is not None:
                result["sp500_change_pct"] = value
                result["sp500_symbol"] = symbol
                fetched_any = True

        except ImportError:
            result["error"] = "yfinance not installed"
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

        result["available"] = fetched_any
        return result

    def _score_macro_environment(
        self, macro_data: Dict[str, Any]
    ) -> tuple[Dict[str, float], List[str], List[str]]:
        """
        Score the macro environment from 0–100 (100 = very favorable).
        Returns (factor_scores, signals, risks).
        """
        factor_scores: Dict[str, float] = {}
        signals: List[str] = []
        risks: List[str] = []

        # Short-term rate score (lower rates → better for equities)
        short_rate = macro_data.get("short_rate")
        if short_rate is not None:
            if short_rate < 2.0:
                factor_scores["short_rate_env"] = 85.0
                signals.append("Low short-term rates — favorable for equity valuations.")
            elif short_rate < 4.0:
                factor_scores["short_rate_env"] = 65.0
                signals.append("Moderate short-term rates.")
            elif short_rate < 5.5:
                factor_scores["short_rate_env"] = 45.0
                risks.append("Elevated short-term rates — may pressure equity multiples.")
            else:
                factor_scores["short_rate_env"] = 25.0
                risks.append("High short-term rates — significant headwind for equities.")

        # Long-term rate score (10-yr yield — yield curve health)
        long_rate = macro_data.get("long_rate")
        if long_rate is not None:
            if long_rate < 3.0:
                factor_scores["long_rate_env"] = 80.0
                signals.append("Low 10-yr yield — growth-friendly environment.")
            elif long_rate < 4.5:
                factor_scores["long_rate_env"] = 60.0
            elif long_rate < 5.5:
                factor_scores["long_rate_env"] = 40.0
                risks.append("High 10-yr yield — discount rates elevated.")
            else:
                factor_scores["long_rate_env"] = 20.0
                risks.append("Very high 10-yr yield — significant valuation compression risk.")

        # VIX score (low VIX = low fear = bullish)
        vix = macro_data.get("vix")
        if vix is not None:
            if vix < 15:
                factor_scores["market_fear"] = 90.0
                signals.append(f"VIX at {vix:.1f} — very low fear, risk-on environment.")
            elif vix < 20:
                factor_scores["market_fear"] = 72.0
                signals.append(f"VIX at {vix:.1f} — calm market conditions.")
            elif vix < 25:
                factor_scores["market_fear"] = 55.0
            elif vix < 35:
                factor_scores["market_fear"] = 35.0
                risks.append(f"VIX at {vix:.1f} — elevated market uncertainty.")
            else:
                factor_scores["market_fear"] = 15.0
                risks.append(f"VIX at {vix:.1f} — extreme fear / volatility regime.")

        # S&P 500 momentum score
        sp500_chg = macro_data.get("sp500_change_pct")
        if sp500_chg is not None:
            if sp500_chg > 5:
                factor_scores["market_momentum"] = 85.0
                signals.append(f"S&P 500 up {sp500_chg:.1f}% in 30 days — strong broad market.")
            elif sp500_chg > 0:
                factor_scores["market_momentum"] = 65.0
                signals.append(f"S&P 500 modestly positive (+{sp500_chg:.1f}% in 30d).")
            elif sp500_chg > -5:
                factor_scores["market_momentum"] = 45.0
                risks.append(f"S&P 500 flat/slightly negative ({sp500_chg:.1f}% in 30d).")
            else:
                factor_scores["market_momentum"] = 20.0
                risks.append(f"S&P 500 down {abs(sp500_chg):.1f}% in 30 days — bearish broad market.")

        return factor_scores, signals, risks


macro_agent = MacroEconomicAgent()
