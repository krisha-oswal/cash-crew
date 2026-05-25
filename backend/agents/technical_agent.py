"""
Technical Analyst Agent - Analyzes price patterns and technical indicators.
"""
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, VisualizationData, TechnicalIndicators
from services.alpha_vantage_service import alpha_vantage_service

logger = logging.getLogger(__name__)


class TechnicalAgent(BaseAgent):
    """Analyzes technical indicators and price patterns."""
    
    def __init__(self):
        super().__init__("Technical Analyst")
    
    async def analyze(self, ticker: str, **kwargs) -> AgentScore:
        """
        Perform technical analysis on a stock.
        
        Analyzes:
        - Moving averages (MA50, MA200)
        - RSI (Relative Strength Index)
        - MACD
        - Bollinger Bands
        - Support/Resistance levels
        - Volume trends
        
        Returns:
            AgentScore with technical score (0-100)
        """
        self.log_info(f"Starting technical analysis for {ticker}")
        
        try:
            # Fetch price data and indicators
            price_data, data_source = await self._fetch_price_data(ticker)
            indicators = await self._calculate_indicators(ticker, price_data)
            
            # Calculate individual factor scores
            factor_scores = self._calculate_factor_scores(indicators, price_data)
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(factor_scores)
            
            # Calculate confidence
            confidence = self._calculate_confidence(price_data, indicators)
            
            # Generate visualizations
            visualizations = self._create_visualizations(price_data, indicators, factor_scores)

            # Create explanation
            explanation = self._generate_explanation(indicators, factor_scores, overall_score)

            # Build signals, risks, warnings
            signals, risks, warnings = self._build_signals_risks(indicators, factor_scores, price_data)
            has_data = bool(factor_scores)
            status = "success" if has_data and confidence >= 0.5 else "partial" if has_data else "failed"

            self.log_info(f"Technical analysis complete: Score={overall_score:.2f}, Confidence={confidence:.2f}")

            return self.create_score(
                score=overall_score if has_data else None,
                confidence=confidence,
                factors=factor_scores,
                metrics=indicators.__dict__ if indicators else {},
                visualizations=visualizations,
                explanation=explanation,
                status=status,
                signals=signals,
                risks=risks,
                warnings=warnings,
                data_source=data_source,
            )

        except Exception as e:
            self.log_error(f"Technical analysis failed: {str(e)}")
            return self.create_failed_score(str(e))
    
    async def _fetch_price_data(self, ticker: str) -> tuple[pd.DataFrame | None, str]:
        """Fetch historical price data, using yfinance when Alpha Vantage fails."""
        try:
            if alpha_vantage_service.is_available():
                # Full output gives MA200 a fair chance; fallback remains free/no-key.
                df = alpha_vantage_service.get_daily_prices(ticker, outputsize="full")
                if df is not None and not df.empty:
                    self.log_info(f"Fetched {len(df)} days of price data from Alpha Vantage")
                    return df, "Alpha Vantage"
            else:
                self.log_warning("Alpha Vantage not available")
        except Exception as e:
            self.log_warning(f"Alpha Vantage price fetch failed: {str(e)}")

        yf_data = await self._fetch_yfinance_price_data(ticker)
        if yf_data is not None and not yf_data.empty:
            self.log_info(f"Fetched {len(yf_data)} days of price data from yfinance fallback")
            return yf_data, "yfinance fallback"

        self.log_error("Failed to fetch price data from Alpha Vantage and yfinance")
        return None, "unavailable"

    async def _fetch_yfinance_price_data(self, ticker: str) -> pd.DataFrame | None:
        """Fetch daily OHLCV data from yfinance as a no-key fallback."""
        try:
            import yfinance as yf

            hist = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=False)
            if hist is None or hist.empty:
                return None

            hist = hist.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })
            keep_cols = [c for c in ("open", "high", "low", "close", "volume") if c in hist.columns]
            df = hist[keep_cols].dropna(subset=["close"])
            return df.sort_index()
        except ImportError:
            self.log_warning("yfinance not installed — technical fallback unavailable")
        except Exception as e:
            self.log_warning(f"yfinance price fallback failed: {str(e)}")
        return None
    
    async def _calculate_indicators(self, ticker: str, price_data: pd.DataFrame | None) -> TechnicalIndicators:
        """Calculate technical indicators."""
        indicators = TechnicalIndicators()
        
        if price_data is None or len(price_data) < 50:
            self.log_warning("Insufficient price data for indicators")
            return indicators
        
        try:
            current_price = price_data['close'].iloc[-1]
            
            # Calculate moving averages manually
            if len(price_data) >= 50:
                indicators.ma_50 = price_data['close'].tail(50).mean()
            
            if len(price_data) >= 200:
                indicators.ma_200 = price_data['close'].tail(200).mean()
            elif len(price_data) >= 100:
                # Use available data if we don't have 200 days
                indicators.ma_200 = price_data['close'].mean()
            
            # Calculate RSI manually
            indicators.rsi = self._calculate_rsi(price_data['close'])
            
            # Calculate MACD manually
            macd_data = self._calculate_macd(price_data['close'])
            if macd_data:
                indicators.macd = macd_data['macd']
                indicators.macd_signal = macd_data['signal']
            
            # Calculate Bollinger Bands
            bb_data = self._calculate_bollinger_bands(price_data['close'])
            if bb_data:
                indicators.bollinger_upper = bb_data['upper']
                indicators.bollinger_lower = bb_data['lower']
            
            # Calculate support and resistance
            support_resistance = self._calculate_support_resistance(price_data)
            if support_resistance:
                indicators.support_level = support_resistance['support']
                indicators.resistance_level = support_resistance['resistance']
            
            self.log_info("Calculated technical indicators")
            
        except Exception as e:
            self.log_error(f"Failed to calculate indicators: {str(e)}")
        
        return indicators
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float | None:
        """Calculate Relative Strength Index."""
        try:
            if len(prices) < period + 1:
                return None
            
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1])
        except:
            return None
    
    def _calculate_macd(self, prices: pd.Series) -> Dict[str, float] | None:
        """Calculate MACD indicator."""
        try:
            if len(prices) < 26:
                return None
            
            exp1 = prices.ewm(span=12, adjust=False).mean()
            exp2 = prices.ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            
            return {
                'macd': float(macd.iloc[-1]),
                'signal': float(signal.iloc[-1])
            }
        except:
            return None
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20) -> Dict[str, float] | None:
        """Calculate Bollinger Bands."""
        try:
            if len(prices) < period:
                return None
            
            sma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            
            upper = sma + (std * 2)
            lower = sma - (std * 2)
            
            return {
                'upper': float(upper.iloc[-1]),
                'lower': float(lower.iloc[-1]),
                'middle': float(sma.iloc[-1])
            }
        except:
            return None
    
    def _calculate_support_resistance(self, price_data: pd.DataFrame) -> Dict[str, float] | None:
        """Calculate support and resistance levels."""
        try:
            if len(price_data) < 20:
                return None
            
            # Simple approach: recent lows for support, recent highs for resistance
            recent_data = price_data.tail(30)
            
            support = recent_data['low'].min()
            resistance = recent_data['high'].max()
            
            return {
                'support': float(support),
                'resistance': float(resistance)
            }
        except:
            return None
    
    def _calculate_factor_scores(
        self, 
        indicators: TechnicalIndicators,
        price_data: pd.DataFrame | None
    ) -> Dict[str, float]:
        """Calculate individual factor scores."""
        scores = {}
        
        if price_data is None or len(price_data) == 0:
            return scores
        
        current_price = price_data['close'].iloc[-1]
        
        # MA Trend Score
        if indicators.ma_50 is not None and indicators.ma_200 is not None:
            if current_price > indicators.ma_50 > indicators.ma_200:
                scores['ma_trend'] = 100  # Strong uptrend
            elif current_price > indicators.ma_50:
                scores['ma_trend'] = 75
            elif current_price > indicators.ma_200:
                scores['ma_trend'] = 60
            elif indicators.ma_50 > indicators.ma_200:
                scores['ma_trend'] = 45
            else:
                scores['ma_trend'] = 25  # Downtrend
        
        # RSI Score (30-70 is neutral, <30 oversold, >70 overbought)
        if indicators.rsi is not None:
            if 40 <= indicators.rsi <= 60:
                scores['rsi'] = 100  # Neutral/healthy
            elif 30 <= indicators.rsi < 40:
                scores['rsi'] = 80  # Slightly oversold (buying opportunity)
            elif 60 < indicators.rsi <= 70:
                scores['rsi'] = 80  # Slightly overbought
            elif indicators.rsi < 30:
                scores['rsi'] = 60  # Oversold (potential reversal)
            elif indicators.rsi > 70:
                scores['rsi'] = 40  # Overbought (potential correction)
        
        # MACD Score
        if indicators.macd is not None and indicators.macd_signal is not None:
            macd_diff = indicators.macd - indicators.macd_signal
            if macd_diff > 0:
                scores['macd'] = 80  # Bullish signal
            else:
                scores['macd'] = 40  # Bearish signal
        
        # Bollinger Bands Score
        if indicators.bollinger_upper and indicators.bollinger_lower:
            bb_range = indicators.bollinger_upper - indicators.bollinger_lower
            position = (current_price - indicators.bollinger_lower) / bb_range
            
            if 0.3 <= position <= 0.7:
                scores['bollinger'] = 100  # In middle range
            elif 0.2 <= position < 0.3 or 0.7 < position <= 0.8:
                scores['bollinger'] = 70
            else:
                scores['bollinger'] = 50  # Near extremes
        
        # Volume Trend Score (if available)
        if 'volume' in price_data.columns:
            recent_volume = price_data['volume'].tail(10).mean()
            older_volume = price_data['volume'].tail(30).head(20).mean()
            
            if recent_volume > older_volume * 1.2:
                scores['volume_trend'] = 80  # Increasing volume
            elif recent_volume > older_volume:
                scores['volume_trend'] = 60
            else:
                scores['volume_trend'] = 40  # Decreasing volume
        
        return scores
    
    def _calculate_overall_score(self, factor_scores: Dict[str, float]) -> float:
        """Calculate weighted overall technical score."""
        if not factor_scores:
            return 50.0
        
        weights = {
            'ma_trend': 0.30,
            'rsi': 0.25,
            'macd': 0.20,
            'bollinger': 0.15,
            'volume_trend': 0.10
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for factor, score in factor_scores.items():
            weight = weights.get(factor, 0.1)
            weighted_sum += score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 50.0
    
    def _calculate_confidence(
        self,
        price_data: pd.DataFrame | None,
        indicators: TechnicalIndicators
    ) -> float:
        """Calculate confidence based on data availability."""
        if price_data is None or len(price_data) < 20:
            return 0.2
        
        # Count available indicators
        available = sum([
            indicators.ma_50 is not None,
            indicators.ma_200 is not None,
            indicators.rsi is not None,
            indicators.macd is not None,
            indicators.bollinger_upper is not None
        ])
        
        base_confidence = available / 5
        
        # Boost confidence if we have more historical data
        if len(price_data) >= 100:
            base_confidence = min(0.95, base_confidence * 1.2)
        
        return max(0.3, base_confidence)
    
    def _create_visualizations(
        self,
        price_data: pd.DataFrame | None,
        indicators: TechnicalIndicators,
        factor_scores: Dict[str, float]
    ) -> List[VisualizationData]:
        """Create visualization data."""
        visualizations = []
        
        # Factor scores bar chart
        if factor_scores:
            visualizations.append(
                self.create_visualization(
                    chart_type="bar",
                    title="Technical Factor Scores",
                    data={
                        "labels": [k.replace('_', ' ').title() for k in factor_scores.keys()],
                        "values": list(factor_scores.values()),
                        "colors": ["#10b981" if v >= 60 else "#f59e0b" if v >= 40 else "#ef4444" 
                                   for v in factor_scores.values()]
                    }
                )
            )
        
        # Price chart with indicators (last 30 days)
        if price_data is not None and len(price_data) > 0:
            recent_data = price_data.tail(30)
            
            visualizations.append(
                self.create_visualization(
                    chart_type="line",
                    title="Price Chart with Indicators",
                    data={
                        "dates": recent_data.index.strftime('%Y-%m-%d').tolist(),
                        "price": recent_data['close'].tolist(),
                        "ma_50": [indicators.ma_50] * len(recent_data) if indicators.ma_50 else None,
                        "ma_200": [indicators.ma_200] * len(recent_data) if indicators.ma_200 else None
                    }
                )
            )
        
        return visualizations
    
    def _generate_explanation(
        self,
        indicators: TechnicalIndicators,
        factor_scores: Dict[str, float],
        overall_score: float
    ) -> str:
        """Generate natural language explanation."""
        parts = []

        if overall_score >= 70:
            parts.append("Strong bullish technical signals.")
        elif overall_score >= 50:
            parts.append("Mixed technical signals with neutral bias.")
        else:
            parts.append("Weak technical signals with bearish bias.")

        if indicators.rsi is not None:
            if indicators.rsi < 30:
                parts.append(f"RSI at {indicators.rsi:.1f} indicates oversold conditions.")
            elif indicators.rsi > 70:
                parts.append(f"RSI at {indicators.rsi:.1f} indicates overbought conditions.")

        if 'ma_trend' in factor_scores:
            if factor_scores['ma_trend'] >= 75:
                parts.append("Price is in a strong uptrend above key moving averages.")
            elif factor_scores['ma_trend'] < 40:
                parts.append("Price is in a downtrend below key moving averages.")

        return " ".join(parts)

    def _build_signals_risks(
        self,
        indicators: TechnicalIndicators,
        factor_scores: Dict[str, float],
        price_data,
    ) -> tuple[List[str], List[str], List[str]]:
        """Build structured signals, risks, warnings from indicator values."""
        signals: List[str] = []
        risks: List[str] = []
        warnings: List[str] = []

        if price_data is None or len(price_data) < 50:
            warnings.append("Insufficient historical price data (< 50 days).")
        if price_data is None or len(price_data) < 200:
            warnings.append("Less than 200 days of data — MA200 is estimated or unavailable.")

        if indicators.rsi is not None:
            if indicators.rsi < 30:
                signals.append(f"RSI oversold ({indicators.rsi:.1f}) — potential reversal opportunity.")
            elif indicators.rsi > 70:
                risks.append(f"RSI overbought ({indicators.rsi:.1f}) — risk of pullback.")
            else:
                signals.append(f"RSI in neutral zone ({indicators.rsi:.1f}).")

        if indicators.macd is not None and indicators.macd_signal is not None:
            if indicators.macd > indicators.macd_signal:
                signals.append("MACD above signal line — bullish momentum.")
            else:
                risks.append("MACD below signal line — bearish momentum.")

        if 'ma_trend' in factor_scores:
            if factor_scores['ma_trend'] >= 75:
                signals.append("Price above both MA50 and MA200 — strong uptrend.")
            elif factor_scores['ma_trend'] < 40:
                risks.append("Price below key moving averages — downtrend.")

        return signals, risks, warnings


# Global instance
technical_agent = TechnicalAgent()
