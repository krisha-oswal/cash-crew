"""
Fundamental Analyst Agent - Analyzes financial statements and ratios.
"""
from typing import Dict, Any, List, Optional
import logging

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, VisualizationData, FundamentalMetrics
from services.finnhub_service import finnhub_service
from services.alpha_vantage_service import alpha_vantage_service

logger = logging.getLogger(__name__)


class FundamentalAgent(BaseAgent):
    """Analyzes fundamental financial metrics and ratios."""
    
    def __init__(self):
        super().__init__("Fundamental Analyst")
    
    async def analyze(self, ticker: str, **kwargs) -> AgentScore:
        """
        Perform fundamental analysis on a stock.
        
        Analyzes:
        - Profitability ratios (ROE, ROA)
        - Valuation ratios (P/E, P/B)
        - Leverage ratios (D/E)
        - Liquidity ratios (Current, Quick)
        - Cash flow metrics
        
        Returns:
            AgentScore with fundamental score (0-100)
        """
        self.log_info(f"Starting fundamental analysis for {ticker}")
        
        try:
            # Fetch financial data
            metrics = await self._fetch_financial_metrics(ticker)
            
            # Calculate individual factor scores
            factor_scores = self._calculate_factor_scores(metrics)
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(factor_scores)
            
            # Calculate confidence based on data availability
            confidence = self._calculate_confidence(metrics)
            
            # Generate visualizations
            visualizations = self._create_visualizations(factor_scores, metrics)
            
            # Create explanation
            explanation = self._generate_explanation(metrics, factor_scores, overall_score)
            
            # Build signals and risks from factor scores
            signals, risks, warnings = self._build_signals_risks(metrics, factor_scores)

            # Determine status based on data availability
            available_fields = sum(1 for v in factor_scores.values() if v > 0)
            status = "success" if available_fields >= 4 else "partial" if available_fields > 0 else "failed"
            if status == "partial":
                warnings.append(f"Only {available_fields} of 7 fundamental metrics available.")

            self.log_info(f"Fundamental analysis complete: Score={overall_score:.2f}, Confidence={confidence:.2f}")

            return self.create_score(
                score=overall_score,
                confidence=confidence,
                factors=factor_scores,
                metrics=metrics.__dict__ if metrics else {},
                visualizations=visualizations,
                explanation=explanation,
                status=status,
                signals=signals,
                risks=risks,
                warnings=warnings,
                data_source="Alpha Vantage" if alpha_vantage_service.is_available() else "Finnhub",
            )

        except Exception as e:
            self.log_error(f"Fundamental analysis failed: {str(e)}")
            return self.create_failed_score(str(e))
    
    async def _fetch_financial_metrics(self, ticker: str) -> FundamentalMetrics:
        """Fetch financial metrics from APIs."""
        metrics = FundamentalMetrics()
        
        try:
            # Try Alpha Vantage first for comprehensive data
            if alpha_vantage_service.is_available():
                overview = alpha_vantage_service.get_company_overview(ticker)
                
                if overview and 'Symbol' in overview:
                    metrics.roe = self._safe_float(overview.get('ReturnOnEquityTTM'))
                    metrics.roa = self._safe_float(overview.get('ReturnOnAssetsTTM'))
                    metrics.debt_to_equity = self._safe_float(overview.get('DebtToEquity'))
                    metrics.pe_ratio = self._safe_float(overview.get('PERatio'))
                    metrics.pb_ratio = self._safe_float(overview.get('PriceToBookRatio'))
                    metrics.current_ratio = self._safe_float(overview.get('CurrentRatio'))
                    metrics.quick_ratio = self._safe_float(overview.get('QuickRatio'))
                    
                    self.log_info("Fetched metrics from Alpha Vantage")
                    return metrics
        except Exception as e:
            self.log_warning(f"Alpha Vantage fetch failed: {str(e)}")
        
        try:
            # Fallback to Finnhub
            if finnhub_service.is_available():
                basic_financials = finnhub_service.get_basic_financials(ticker)
                
                if basic_financials and 'metric' in basic_financials:
                    metric = basic_financials['metric']
                    
                    metrics.roe = self._safe_float(metric.get('roeTTM'))
                    metrics.roa = self._safe_float(metric.get('roaTTM'))
                    metrics.debt_to_equity = self._safe_float(metric.get('totalDebt/totalEquityQuarterly'))
                    metrics.pe_ratio = self._safe_float(metric.get('peBasicExclExtraTTM'))
                    metrics.pb_ratio = self._safe_float(metric.get('pbQuarterly'))
                    metrics.current_ratio = self._safe_float(metric.get('currentRatioQuarterly'))
                    
                    self.log_info("Fetched metrics from Finnhub")
        except Exception as e:
            self.log_warning(f"Finnhub fetch failed: {str(e)}")
        
        return metrics
    
    def _safe_float(self, value) -> float | None:
        """Safely convert value to float."""
        if value is None or value == 'None' or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _calculate_factor_scores(self, metrics: FundamentalMetrics) -> Dict[str, float]:
        """Calculate individual factor scores (0-100)."""
        scores = {}
        
        # ROE Score (higher is better, 15%+ is excellent)
        if metrics.roe is not None:
            roe_pct = metrics.roe * 100 if metrics.roe < 1 else metrics.roe
            if roe_pct >= 20:
                scores['roe'] = 100
            elif roe_pct >= 15:
                scores['roe'] = 80
            elif roe_pct >= 10:
                scores['roe'] = 60
            elif roe_pct >= 5:
                scores['roe'] = 40
            else:
                scores['roe'] = 20
        
        # ROA Score (higher is better, 5%+ is good)
        if metrics.roa is not None:
            roa_pct = metrics.roa * 100 if metrics.roa < 1 else metrics.roa
            if roa_pct >= 10:
                scores['roa'] = 100
            elif roa_pct >= 5:
                scores['roa'] = 80
            elif roa_pct >= 2:
                scores['roa'] = 60
            elif roa_pct >= 0:
                scores['roa'] = 40
            else:
                scores['roa'] = 20
        
        # Debt-to-Equity Score (lower is better, <1 is good)
        if metrics.debt_to_equity is not None:
            if metrics.debt_to_equity < 0.5:
                scores['debt_to_equity'] = 100
            elif metrics.debt_to_equity < 1.0:
                scores['debt_to_equity'] = 80
            elif metrics.debt_to_equity < 1.5:
                scores['debt_to_equity'] = 60
            elif metrics.debt_to_equity < 2.0:
                scores['debt_to_equity'] = 40
            else:
                scores['debt_to_equity'] = 20
        
        # P/E Ratio Score (moderate is better, 15-25 is ideal)
        if metrics.pe_ratio is not None and metrics.pe_ratio > 0:
            if 15 <= metrics.pe_ratio <= 25:
                scores['pe_ratio'] = 100
            elif 10 <= metrics.pe_ratio < 15 or 25 < metrics.pe_ratio <= 30:
                scores['pe_ratio'] = 80
            elif 5 <= metrics.pe_ratio < 10 or 30 < metrics.pe_ratio <= 40:
                scores['pe_ratio'] = 60
            elif metrics.pe_ratio < 5 or metrics.pe_ratio > 40:
                scores['pe_ratio'] = 40
        
        # P/B Ratio Score (lower is better, <3 is good)
        if metrics.pb_ratio is not None and metrics.pb_ratio > 0:
            if metrics.pb_ratio < 1:
                scores['pb_ratio'] = 100
            elif metrics.pb_ratio < 2:
                scores['pb_ratio'] = 80
            elif metrics.pb_ratio < 3:
                scores['pb_ratio'] = 60
            elif metrics.pb_ratio < 5:
                scores['pb_ratio'] = 40
            else:
                scores['pb_ratio'] = 20
        
        # Current Ratio Score (>1.5 is good)
        if metrics.current_ratio is not None:
            if metrics.current_ratio >= 2.0:
                scores['current_ratio'] = 100
            elif metrics.current_ratio >= 1.5:
                scores['current_ratio'] = 80
            elif metrics.current_ratio >= 1.0:
                scores['current_ratio'] = 60
            elif metrics.current_ratio >= 0.5:
                scores['current_ratio'] = 40
            else:
                scores['current_ratio'] = 20
        
        # Quick Ratio Score (>1.0 is good)
        if metrics.quick_ratio is not None:
            if metrics.quick_ratio >= 1.5:
                scores['quick_ratio'] = 100
            elif metrics.quick_ratio >= 1.0:
                scores['quick_ratio'] = 80
            elif metrics.quick_ratio >= 0.75:
                scores['quick_ratio'] = 60
            elif metrics.quick_ratio >= 0.5:
                scores['quick_ratio'] = 40
            else:
                scores['quick_ratio'] = 20
        
        return scores
    
    def _calculate_overall_score(self, factor_scores: Dict[str, float]) -> float:
        """Calculate weighted overall fundamental score."""
        if not factor_scores:
            return 50.0  # Neutral score if no data
        
        # Weights for each factor
        weights = {
            'roe': 0.25,
            'roa': 0.15,
            'debt_to_equity': 0.20,
            'pe_ratio': 0.15,
            'pb_ratio': 0.10,
            'current_ratio': 0.10,
            'quick_ratio': 0.05
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for factor, score in factor_scores.items():
            weight = weights.get(factor, 0.1)
            weighted_sum += score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 50.0
    
    def _calculate_confidence(self, metrics: FundamentalMetrics) -> float:
        """Calculate confidence based on data availability."""
        total_metrics = 8  # Total number of metrics we try to fetch
        available_metrics = sum([
            metrics.roe is not None,
            metrics.roa is not None,
            metrics.debt_to_equity is not None,
            metrics.pe_ratio is not None,
            metrics.pb_ratio is not None,
            metrics.fcf_yield is not None,
            metrics.current_ratio is not None,
            metrics.quick_ratio is not None
        ])
        
        # Confidence is proportion of available metrics
        base_confidence = available_metrics / total_metrics
        
        # Minimum confidence of 0.3 if we have at least some data
        return max(0.3, base_confidence) if available_metrics > 0 else 0.1
    
    def _create_visualizations(
        self, 
        factor_scores: Dict[str, float],
        metrics: FundamentalMetrics
    ) -> List[VisualizationData]:
        """Create visualization data for charts."""
        visualizations = []
        
        # Bar chart of factor contributions
        if factor_scores:
            visualizations.append(
                self.create_visualization(
                    chart_type="bar",
                    title="Fundamental Factor Scores",
                    data={
                        "labels": [k.replace('_', ' ').title() for k in factor_scores.keys()],
                        "values": list(factor_scores.values()),
                        "colors": ["#10b981" if v >= 60 else "#f59e0b" if v >= 40 else "#ef4444" 
                                   for v in factor_scores.values()]
                    },
                    config={"yAxis": {"max": 100, "label": "Score"}}
                )
            )
        
        # Metrics table data
        metrics_data = {}
        if metrics.roe is not None:
            metrics_data['ROE'] = f"{metrics.roe * 100:.2f}%" if metrics.roe < 1 else f"{metrics.roe:.2f}%"
        if metrics.roa is not None:
            metrics_data['ROA'] = f"{metrics.roa * 100:.2f}%" if metrics.roa < 1 else f"{metrics.roa:.2f}%"
        if metrics.debt_to_equity is not None:
            metrics_data['D/E Ratio'] = f"{metrics.debt_to_equity:.2f}"
        if metrics.pe_ratio is not None:
            metrics_data['P/E Ratio'] = f"{metrics.pe_ratio:.2f}"
        if metrics.pb_ratio is not None:
            metrics_data['P/B Ratio'] = f"{metrics.pb_ratio:.2f}"
        if metrics.current_ratio is not None:
            metrics_data['Current Ratio'] = f"{metrics.current_ratio:.2f}"
        
        if metrics_data:
            visualizations.append(
                self.create_visualization(
                    chart_type="bar",
                    title="Key Financial Metrics",
                    data=metrics_data
                )
            )
        
        return visualizations
    
    def _generate_explanation(
        self,
        metrics: FundamentalMetrics,
        factor_scores: Dict[str, float],
        overall_score: float
    ) -> str:
        """Generate natural language explanation of the analysis."""
        explanation_parts = []

        if overall_score >= 70:
            explanation_parts.append("Strong fundamental health with solid financial metrics.")
        elif overall_score >= 50:
            explanation_parts.append("Moderate fundamental health with mixed indicators.")
        else:
            explanation_parts.append("Weak fundamental health with concerning metrics.")

        strong_factors = [k for k, v in factor_scores.items() if v >= 80]
        if strong_factors:
            factors_str = ", ".join([f.replace('_', ' ').title() for f in strong_factors])
            explanation_parts.append(f"Strengths: {factors_str}.")

        weak_factors = [k for k, v in factor_scores.items() if v < 40]
        if weak_factors:
            factors_str = ", ".join([f.replace('_', ' ').title() for f in weak_factors])
            explanation_parts.append(f"Concerns: {factors_str}.")

        return " ".join(explanation_parts)

    def _build_signals_risks(
        self,
        metrics: FundamentalMetrics,
        factor_scores: Dict[str, float],
    ) -> tuple[List[str], List[str], List[str]]:
        """Build structured signals, risks, and warnings lists."""
        signals: List[str] = []
        risks: List[str] = []
        warnings: List[str] = []

        if metrics.roe is not None:
            roe_pct = metrics.roe * 100 if metrics.roe < 1 else metrics.roe
            if roe_pct >= 15:
                signals.append(f"High ROE of {roe_pct:.1f}% — strong shareholder returns.")
            elif roe_pct < 5:
                risks.append(f"Low ROE of {roe_pct:.1f}% — weak equity returns.")

        if metrics.pe_ratio is not None and metrics.pe_ratio > 0:
            if metrics.pe_ratio > 40:
                risks.append(f"High P/E of {metrics.pe_ratio:.1f}x — elevated valuation risk.")
            elif metrics.pe_ratio < 10:
                signals.append(f"Low P/E of {metrics.pe_ratio:.1f}x — potentially undervalued.")

        if metrics.debt_to_equity is not None:
            if metrics.debt_to_equity > 2.0:
                risks.append(f"High D/E ratio of {metrics.debt_to_equity:.2f} — significant leverage.")
            elif metrics.debt_to_equity < 0.5:
                signals.append(f"Low D/E of {metrics.debt_to_equity:.2f} — conservative balance sheet.")

        if metrics.current_ratio is not None and metrics.current_ratio < 1.0:
            risks.append(f"Current ratio below 1 ({metrics.current_ratio:.2f}) — liquidity concern.")

        return signals, risks, warnings


# Global instance
fundamental_agent = FundamentalAgent()
