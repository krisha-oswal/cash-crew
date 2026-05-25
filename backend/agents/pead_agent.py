"""
PEAD (Post-Earnings Announcement Drift) Analyst Agent.

Data source priority:
  1. Finnhub  — provides actual EPS AND analyst estimates (required for surprise %)
  2. SEC EDGAR — provides actual EPS only; used for EPS-trend scoring when Finnhub unavailable
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, VisualizationData, PEADMetrics
from services.finnhub_service import finnhub_service
from services.edgar_service import edgar_service

logger = logging.getLogger(__name__)


class PEADAgent(BaseAgent):
    """Analyzes post-earnings announcement drift patterns."""

    def __init__(self):
        super().__init__("PEAD Analyst")

    async def analyze(self, ticker: str, **kwargs) -> AgentScore:
        """
        Analyze earnings announcement patterns and predict drift.

        PEAD theory: Stocks tend to drift in the direction of earnings surprises
        for weeks/months after the announcement.

        Returns:
            AgentScore with PEAD prediction (0-100)
        """
        self.log_info(f"Starting PEAD analysis for {ticker}")

        try:
            # Fetch earnings data (Finnhub first → EDGAR fallback)
            earnings_data, has_estimates = await self._fetch_earnings_data(ticker)

            if not earnings_data:
                self.log_warning("No earnings data available")
                return self.create_score(
                    score=None,
                    confidence=0.0,
                    factors={},
                    metrics={"status": "no_earnings_data"},
                    visualizations=[],
                    explanation="Insufficient earnings data for PEAD analysis",
                    status="failed",
                    warnings=["No earnings data found via Finnhub or SEC EDGAR."],
                )

            # Calculate metrics
            metrics = self._calculate_pead_metrics(earnings_data, has_estimates)

            # Calculate factor scores
            factor_scores = self._calculate_factor_scores(metrics, has_estimates, earnings_data)

            # Calculate overall score
            overall_score = self._calculate_overall_score(factor_scores)

            # Calculate confidence
            confidence = self._calculate_confidence(earnings_data, has_estimates)

            # Generate visualizations
            visualizations = self._create_visualizations(earnings_data, metrics, has_estimates)

            # Create explanation
            explanation = self._generate_explanation(metrics, overall_score, has_estimates)

            # Build signals, risks, warnings
            signals, risks, warnings = self._build_signals_risks(metrics, has_estimates, earnings_data)
            status = "success" if has_estimates else "partial"
            if not has_estimates:
                warnings.append("Analyst estimates unavailable — using EPS trend from SEC EDGAR only (less precise PEAD signal).")
            if not warnings:
                warnings = []

            self.log_info(f"PEAD analysis complete: Score={overall_score:.2f}, has_estimates={has_estimates}")

            return self.create_score(
                score=overall_score,
                confidence=confidence,
                factors=factor_scores,
                metrics=metrics.__dict__,
                visualizations=visualizations,
                explanation=explanation,
                status=status,
                signals=signals,
                risks=risks,
                warnings=warnings,
                data_source="Finnhub" if has_estimates else "SEC EDGAR",
            )

        except Exception as e:
            self.log_error(f"PEAD analysis failed: {str(e)}")
            return self.create_failed_score(str(e))

    async def _fetch_earnings_data(self, ticker: str):
        """
        Fetch earnings data. Returns (earnings_list, has_estimates).

        Priority:
          1. Finnhub — actual + analyst estimate per quarter (best for PEAD)
          2. SEC EDGAR — actual EPS only (used for trend scoring)
        """
        # PRIMARY: Finnhub (has both actual and analyst estimates)
        try:
            if finnhub_service.is_available():
                earnings = finnhub_service.get_earnings(ticker)
                if earnings and isinstance(earnings, list) and len(earnings) > 0:
                    # Finnhub returns newest first already
                    sorted_earnings = sorted(
                        [e for e in earnings if e.get('actual') is not None],
                        key=lambda x: x.get('period', ''),
                        reverse=True
                    )
                    if sorted_earnings:
                        self.log_info(f"Fetched {len(sorted_earnings)} earnings records from Finnhub (with estimates)")
                        return sorted_earnings[:8], True
        except Exception as e:
            self.log_warning(f"Finnhub earnings fetch failed: {e}")

        # FALLBACK: SEC EDGAR (actual EPS only — no analyst estimates)
        try:
            edgar_data = edgar_service.get_earnings_history(ticker)
            if edgar_data:
                self.log_info(f"Fetched {len(edgar_data)} EPS records from SEC EDGAR (no estimates)")
                return edgar_data, False
        except Exception as e:
            self.log_warning(f"SEC EDGAR earnings fetch failed: {e}")

        return [], False

    def _calculate_pead_metrics(self, earnings_data: List[Dict[str, Any]], has_estimates: bool) -> PEADMetrics:
        """Calculate PEAD-related metrics."""
        metrics = PEADMetrics()

        if not earnings_data:
            return metrics

        latest = earnings_data[0]
        metrics.last_eps_actual = self._safe_float(latest.get('actual'))
        metrics.last_eps_estimate = self._safe_float(latest.get('estimate')) if has_estimates else None

        # Calculate surprise % (only when estimates are available)
        if has_estimates and metrics.last_eps_actual is not None and metrics.last_eps_estimate is not None:
            if metrics.last_eps_estimate != 0:
                metrics.last_surprise_percent = (
                    (metrics.last_eps_actual - metrics.last_eps_estimate) /
                    abs(metrics.last_eps_estimate) * 100
                )

        # Calculate CONSECUTIVE beat/miss streaks (stop at first break)
        if has_estimates:
            beat_streak = 0
            miss_streak = 0

            for earning in earnings_data:  # Already sorted newest → oldest
                actual = self._safe_float(earning.get('actual'))
                estimate = self._safe_float(earning.get('estimate'))

                if actual is None or estimate is None:
                    break  # Gap in data — streak ends

                if actual > estimate:
                    if miss_streak > 0:
                        break  # First miss after beats — end beat streak
                    beat_streak += 1
                elif actual < estimate:
                    if beat_streak > 0:
                        break  # First beat after misses — end miss streak
                    miss_streak += 1
                else:
                    break  # Exact match — ends streak

            metrics.consecutive_beats = beat_streak
            metrics.consecutive_misses = miss_streak

        # Average surprise over last 4 quarters (only when estimates available)
        if has_estimates:
            surprises = []
            for earning in earnings_data[:4]:
                actual = self._safe_float(earning.get('actual'))
                estimate = self._safe_float(earning.get('estimate'))

                if actual is not None and estimate is not None and estimate != 0:
                    surprise = (actual - estimate) / abs(estimate) * 100
                    surprises.append(surprise)

            if surprises:
                metrics.avg_surprise_4q = sum(surprises) / len(surprises)

        return metrics

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert to float."""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _calculate_factor_scores(
        self,
        metrics: PEADMetrics,
        has_estimates: bool,
        earnings_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate PEAD factor scores."""
        scores = {}

        if has_estimates:
            # --- Surprise-based scoring (Finnhub path) ---

            # Recent surprise score
            if metrics.last_surprise_percent is not None:
                sp = metrics.last_surprise_percent
                if sp > 15:
                    scores['recent_surprise'] = 95    # Very large beat
                elif sp > 10:
                    scores['recent_surprise'] = 85    # Big beat
                elif sp > 5:
                    scores['recent_surprise'] = 72    # Beat
                elif sp > 2:
                    scores['recent_surprise'] = 60    # Small beat
                elif sp > -2:
                    scores['recent_surprise'] = 50    # In-line
                elif sp > -5:
                    scores['recent_surprise'] = 40    # Small miss
                elif sp > -10:
                    scores['recent_surprise'] = 28    # Miss
                else:
                    scores['recent_surprise'] = 15    # Big miss

            # Consecutive streak score
            if metrics.consecutive_beats >= 4:
                scores['consistency'] = 95
            elif metrics.consecutive_beats >= 3:
                scores['consistency'] = 80
            elif metrics.consecutive_beats >= 2:
                scores['consistency'] = 65
            elif metrics.consecutive_beats == 1:
                scores['consistency'] = 55
            elif metrics.consecutive_misses >= 3:
                scores['consistency'] = 20
            elif metrics.consecutive_misses >= 2:
                scores['consistency'] = 35
            elif metrics.consecutive_misses == 1:
                scores['consistency'] = 45
            else:
                scores['consistency'] = 50

            # Average surprise trend
            if metrics.avg_surprise_4q is not None:
                avg = metrics.avg_surprise_4q
                if avg > 8:
                    scores['trend'] = 90
                elif avg > 5:
                    scores['trend'] = 78
                elif avg > 2:
                    scores['trend'] = 65
                elif avg > 0:
                    scores['trend'] = 55
                elif avg > -3:
                    scores['trend'] = 42
                elif avg > -6:
                    scores['trend'] = 30
                else:
                    scores['trend'] = 18

        else:
            # --- EPS-trend scoring (EDGAR path, no analyst estimates) ---
            # Score based on whether EPS is growing quarter over quarter
            eps_values = []
            for e in earnings_data:
                val = self._safe_float(e.get('actual'))
                if val is not None:
                    eps_values.append(val)

            if len(eps_values) >= 2:
                # Count growing vs shrinking transitions
                growing = sum(1 for i in range(len(eps_values) - 1) if eps_values[i] > eps_values[i + 1])
                ratio = growing / (len(eps_values) - 1)

                if ratio >= 0.75:
                    scores['eps_trend'] = 78
                elif ratio >= 0.5:
                    scores['eps_trend'] = 62
                elif ratio >= 0.25:
                    scores['eps_trend'] = 45
                else:
                    scores['eps_trend'] = 28

            # Most recent EPS vs year-ago EPS (YoY)
            if len(eps_values) >= 4:
                recent = eps_values[0]
                year_ago = eps_values[3]
                if year_ago != 0:
                    yoy_growth = (recent - year_ago) / abs(year_ago) * 100
                    if yoy_growth > 20:
                        scores['yoy_growth'] = 85
                    elif yoy_growth > 10:
                        scores['yoy_growth'] = 72
                    elif yoy_growth > 0:
                        scores['yoy_growth'] = 58
                    elif yoy_growth > -10:
                        scores['yoy_growth'] = 40
                    else:
                        scores['yoy_growth'] = 22

        return scores

    def _calculate_overall_score(self, factor_scores: Dict[str, float]) -> float:
        """Calculate overall PEAD score as a clean weighted average."""
        if not factor_scores:
            return 50.0

        # Weights for Finnhub path (has analyst estimates)
        surprise_weights = {
            'recent_surprise': 0.50,
            'consistency': 0.30,
            'trend': 0.20,
        }

        # Weights for EDGAR path (EPS trend only, no analyst estimates)
        trend_weights = {
            'eps_trend': 0.60,
            'yoy_growth': 0.40,
        }

        weights = surprise_weights if 'recent_surprise' in factor_scores else trend_weights

        weighted_sum = 0.0
        total_weight = 0.0
        for factor, score in factor_scores.items():
            w = weights.get(factor, 0.0)
            weighted_sum += score * w
            total_weight += w

        if total_weight == 0.0:
            # No matching weights — simple average
            return sum(factor_scores.values()) / len(factor_scores)

        return weighted_sum / total_weight


    def _calculate_confidence(self, earnings_data: List[Dict[str, Any]], has_estimates: bool) -> float:
        """Calculate confidence based on data availability and quality."""
        if not earnings_data:
            return 0.2

        # EDGAR (no estimates) is inherently less informative for PEAD
        base = 1.0 if has_estimates else 0.7

        if len(earnings_data) >= 8:
            data_factor = 0.85
        elif len(earnings_data) >= 4:
            data_factor = 0.70
        elif len(earnings_data) >= 2:
            data_factor = 0.55
        else:
            data_factor = 0.35

        return round(min(0.90, base * data_factor), 2)

    def _create_visualizations(
        self,
        earnings_data: List[Dict[str, Any]],
        metrics: PEADMetrics,
        has_estimates: bool
    ) -> List[VisualizationData]:
        """Create visualizations."""
        visualizations = []

        if has_estimates:
            # Earnings surprise history (% beat/miss)
            periods = []
            surprises = []

            for earning in reversed(earnings_data[:8]):  # Chronological order
                period = earning.get('period', '')
                actual = self._safe_float(earning.get('actual'))
                estimate = self._safe_float(earning.get('estimate'))

                if actual is not None and estimate is not None and estimate != 0:
                    surprise = (actual - estimate) / abs(estimate) * 100
                    periods.append(period)
                    surprises.append(round(surprise, 2))

            if periods:
                visualizations.append(
                    self.create_visualization(
                        chart_type="bar",
                        title="Earnings Surprise History (%)",
                        data={
                            "labels": periods,
                            "values": surprises,
                            "colors": ["#10b981" if s > 0 else "#ef4444" for s in surprises]
                        }
                    )
                )
        else:
            # EPS trend chart (actual values over time)
            periods = []
            eps_vals = []

            for earning in reversed(earnings_data[:8]):
                period = earning.get('period', '')
                val = self._safe_float(earning.get('actual'))
                if val is not None:
                    periods.append(period)
                    eps_vals.append(round(val, 4))

            if periods:
                visualizations.append(
                    self.create_visualization(
                        chart_type="line",
                        title="EPS Trend (Actual, from SEC EDGAR)",
                        data={
                            "labels": periods,
                            "values": eps_vals,
                        }
                    )
                )

        return visualizations

    def _generate_explanation(self, metrics: PEADMetrics, overall_score: float, has_estimates: bool) -> str:
        """Generate explanation."""
        parts = []

        if not has_estimates:
            parts.append("Analysis based on EPS trend (SEC EDGAR) — analyst estimates unavailable.")

        if overall_score >= 70:
            parts.append("Strong PEAD signal suggests positive momentum following earnings performance.")
        elif overall_score >= 50:
            parts.append("Mixed PEAD signals with moderate earnings performance.")
        else:
            parts.append("Weak PEAD signal due to earnings misses or declining EPS.")

        if has_estimates and metrics.last_surprise_percent is not None:
            if metrics.last_surprise_percent > 0:
                parts.append(f"Latest beat by {metrics.last_surprise_percent:.1f}%.")
            else:
                parts.append(f"Latest missed by {abs(metrics.last_surprise_percent):.1f}%.")

        if has_estimates:
            if metrics.consecutive_beats >= 3:
                parts.append(f"Strong consistency: {metrics.consecutive_beats} consecutive beats.")
            elif metrics.consecutive_misses >= 2:
                parts.append(f"Concerning pattern: {metrics.consecutive_misses} consecutive misses.")

        return " ".join(parts)

    def _build_signals_risks(
        self,
        metrics: PEADMetrics,
        has_estimates: bool,
        earnings_data: List[Dict[str, Any]],
    ) -> tuple[List[str], List[str], List[str]]:
        """Build structured signals, risks, warnings."""
        signals: List[str] = []
        risks: List[str] = []
        warnings: List[str] = []

        if has_estimates and metrics.last_surprise_percent is not None:
            if metrics.last_surprise_percent > 5:
                signals.append(f"Earnings beat by {metrics.last_surprise_percent:.1f}% last quarter.")
            elif metrics.last_surprise_percent < -5:
                risks.append(f"Earnings miss by {abs(metrics.last_surprise_percent):.1f}% last quarter.")

        if metrics.consecutive_beats >= 3:
            signals.append(f"{metrics.consecutive_beats} consecutive quarterly beats — strong earnings momentum.")
        if metrics.consecutive_misses >= 2:
            risks.append(f"{metrics.consecutive_misses} consecutive quarterly misses — deteriorating earnings trend.")

        if metrics.avg_surprise_4q is not None:
            if metrics.avg_surprise_4q > 5:
                signals.append(f"4-quarter avg surprise: +{metrics.avg_surprise_4q:.1f}% — consistent outperformer.")
            elif metrics.avg_surprise_4q < -3:
                risks.append(f"4-quarter avg surprise: {metrics.avg_surprise_4q:.1f}% — consistent underperformer.")

        if not has_estimates:
            warnings.append("Analyst EPS estimates not available — PEAD drift scoring is approximate.")

        return signals, risks, warnings


# Global instance
pead_agent = PEADAgent()
