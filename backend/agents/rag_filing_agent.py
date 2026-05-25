"""
RAG Filing & Financial Health Agent - Uses Gemini 1.5 Pro for document analysis.
"""
from typing import Dict, Any, List
import logging

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, VisualizationData, RAGMetrics
from services.llm_service import llm_router, LLMProvider
from services.finnhub_service import finnhub_service
from services.edgar_service import edgar_service

logger = logging.getLogger(__name__)


class RAGFilingAgent(BaseAgent):
    """
    Analyzes SEC/regulatory filings using RAG and Gemini 1.5 Pro.
    
    Note: This is a simplified implementation. Full RAG would require:
    - Document embedding and vector storage
    - Semantic search
    - Long-context processing
    
    Current implementation uses available financial data and LLM analysis.
    """
    
    def __init__(self):
        super().__init__("RAG Filing & Financial Health")
    
    async def analyze(self, ticker: str, **kwargs) -> AgentScore:
        """
        Analyze financial health using available data and LLM reasoning.
        
        Returns:
            AgentScore with financial health assessment (0-100)
        """
        self.log_info(f"Starting RAG filing analysis for {ticker}")
        
        try:
            # Fetch available financial data
            financial_data = await self._fetch_financial_data(ticker)
            
            if not financial_data:
                self.log_warning("No financial data available")
                return self.create_score(
                    score=None,
                    confidence=0.0,
                    factors={},
                    metrics={"status": "no_data"},
                    visualizations=[],
                    explanation="Insufficient data for financial health analysis",
                    status="failed",
                    warnings=["No financial data available from SEC EDGAR or Finnhub."],
                )
            
            # Analyze using LLM
            analysis = await self._analyze_with_llm(ticker, financial_data)
            
            # Calculate metrics
            metrics = self._calculate_metrics(financial_data, analysis)
            
            # Calculate factor scores
            factor_scores = self._calculate_factor_scores(metrics, analysis)
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(factor_scores)
            
            # Calculate confidence
            confidence = self._calculate_confidence(financial_data)
            
            # Generate visualizations
            visualizations = self._create_visualizations(metrics, factor_scores)
            
            # Create explanation
            explanation = analysis.get('explanation', 'Financial health analysis complete.')

            # Build signals, risks, warnings
            signals, risks, warnings = self._build_signals_risks(metrics, factor_scores, analysis)
            has_llm = analysis.get('provider', 'none') != 'none'
            status = "success" if has_llm and confidence >= 0.6 else "partial"
            if not has_llm:
                warnings.append("LLM analysis unavailable — score based on heuristics only.")

            self.log_info(f"RAG analysis complete: Score={overall_score:.2f}")

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
                data_source=f"{financial_data.get('source', 'financial data')} + {analysis.get('provider', 'heuristic')}",
            )

        except Exception as e:
            self.log_error(f"RAG analysis failed: {str(e)}")
            return self.create_failed_score(str(e))
    
    async def _fetch_financial_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch financial data - tries SEC EDGAR first, then Finnhub."""
        data = {}
        
        # Primary: SEC EDGAR (free, no API key, real XBRL data)
        try:
            edgar_metrics = edgar_service.get_financial_metrics(ticker)
            if edgar_metrics and self._has_usable_financial_metrics(edgar_metrics):
                self.log_info(f"Fetched financial metrics from SEC EDGAR: {list(edgar_metrics.keys())}")
                # Normalise into the shape the rest of the agent expects
                data['financials'] = {
                    'metric': {
                        'roaRfy': edgar_metrics.get('roa'),
                        'roeRfy': edgar_metrics.get('roe'),
                        'currentRatioQuarterly': edgar_metrics.get('current_ratio'),
                        'totalDebt/totalEquityQuarterly': edgar_metrics.get('debt_to_equity'),
                        'net_margin': edgar_metrics.get('net_margin'),
                        'revenue': edgar_metrics.get('revenue'),
                    }
                }
                data['source'] = 'SEC EDGAR'
                # Also try to add a profile from Finnhub if available
                try:
                    if finnhub_service.is_available():
                        profile = finnhub_service.get_company_profile(ticker)
                        if profile:
                            data['profile'] = profile
                except Exception:
                    data['profile'] = {'name': ticker, 'finnhubIndustry': 'N/A', 'marketCapitalization': 0}
                    
                return data
            if edgar_metrics:
                self.log_warning("SEC EDGAR returned no usable ratios; falling back to Finnhub basic financials")
        except Exception as e:
            self.log_warning(f"SEC EDGAR financial fetch failed: {e}")
        
        # Fallback: Finnhub
        try:
            if finnhub_service.is_available():
                profile = finnhub_service.get_company_profile(ticker)
                if profile:
                    data['profile'] = profile
                financials = finnhub_service.get_basic_financials(ticker)
                if financials and self._has_usable_financial_metrics(financials.get('metric', {})):
                    data['financials'] = financials
                    data['source'] = 'Finnhub basic financials'
        except Exception as e:
            self.log_warning(f"Finnhub financial fetch failed: {e}")
        
        return data

    def _has_usable_financial_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Return True when at least one meaningful ratio/metric is present."""
        if not metrics:
            return False

        keys = (
            'roa', 'roe', 'current_ratio', 'debt_to_equity', 'net_margin',
            'roaRfy', 'roeRfy', 'currentRatioQuarterly', 'quickRatioQuarterly',
            'totalDebt/totalEquityQuarterly', 'peBasicExclExtraTTM',
        )
        return any(metrics.get(key) is not None for key in keys)
    
    async def _analyze_with_llm(
        self,
        ticker: str,
        financial_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use Gemini 1.5 Pro to analyze financial health."""
        
        # Prepare data summary
        profile = financial_data.get('profile', {})
        financials = financial_data.get('financials', {})
        
        data_summary = f"""
Company: {profile.get('name', ticker)}
Industry: {profile.get('finnhubIndustry', 'N/A')}
Market Cap: ${profile.get('marketCapitalization', 0):,.0f}M

Financial Metrics:
{self._format_financials(financials)}
"""
        
        prompt = f"""Analyze the financial health of this company based on available data:

{data_summary}

Provide a brief assessment (2-3 sentences) covering:
1. Overall financial health (strong/moderate/weak)
2. Key strengths or concerns
3. Risk factors to monitor

Be concise and investor-focused."""

        system_prompt = "You are a financial analyst assessing company financial health."
        
        try:
            # Use Gemini 1.5 Pro for analysis
            response, provider = await llm_router.generate(
                prompt=prompt,
                provider_priority=[
                    LLMProvider.GEMINI_1_5_PRO,
                    LLMProvider.GROQ_LLAMA3_70B,
                    LLMProvider.OLLAMA_LLAMA3
                ],
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=300
            )
            
            return {
                'explanation': response.strip(),
                'provider': provider.value
            }
            
        except Exception as e:
            self.log_error(f"LLM analysis failed: {str(e)}")
            return {
                'explanation': 'Unable to generate detailed analysis.',
                'provider': 'none'
            }
    
    def _format_financials(self, financials: Dict[str, Any]) -> str:
        """Format financial data for LLM."""
        if not financials:
            return "No detailed financials available"
        
        metrics = financials.get('metric', {})
        if not metrics:
            return "No detailed financials available"
        
        lines = []
        
        # Key metrics
        key_metrics = {
            'roaRfy': 'ROA',
            'roeRfy': 'ROE',
            'currentRatioQuarterly': 'Current Ratio',
            'quickRatioQuarterly': 'Quick Ratio',
            'totalDebt/totalEquityQuarterly': 'D/E Ratio',
            'peBasicExclExtraTTM': 'P/E Ratio'
        }
        
        for key, label in key_metrics.items():
            value = metrics.get(key)
            if value is not None:
                lines.append(f"- {label}: {value:.2f}")
        
        return '\n'.join(lines) if lines else "Limited metrics available"
    
    def _calculate_metrics(
        self,
        financial_data: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> RAGMetrics:
        """Calculate RAG metrics."""
        metrics = RAGMetrics()
        
        # Extract key findings from LLM analysis
        explanation = analysis.get('explanation', '')
        
        # Simple keyword-based extraction
        if 'strong' in explanation.lower():
            metrics.key_findings.append('Strong financial position')
        if 'weak' in explanation.lower() or 'concern' in explanation.lower():
            metrics.key_findings.append('Financial concerns identified')
        if 'risk' in explanation.lower():
            metrics.risk_factors_count = 1
        
        # Store financial indicators
        financials = financial_data.get('financials', {})
        if financials:
            metrics.financial_health_indicators = financials.get('metric', {})
        
        return metrics
    
    def _calculate_factor_scores(
        self,
        metrics: RAGMetrics,
        analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate factor scores."""
        scores = {}
        
        # Parse LLM sentiment
        explanation = analysis.get('explanation', '').lower()
        indicators = metrics.financial_health_indicators or {}

        heuristic_health_scores: List[float] = []
        roe = indicators.get('roeRfy')
        roa = indicators.get('roaRfy')
        current_ratio = indicators.get('currentRatioQuarterly')
        debt_to_equity = indicators.get('totalDebt/totalEquityQuarterly')
        pe_ratio = indicators.get('peBasicExclExtraTTM')

        if roe is not None:
            heuristic_health_scores.append(85 if roe >= 15 else 65 if roe >= 8 else 45 if roe >= 0 else 25)
        if roa is not None:
            heuristic_health_scores.append(85 if roa >= 8 else 65 if roa >= 3 else 45 if roa >= 0 else 25)
        if current_ratio is not None:
            heuristic_health_scores.append(80 if current_ratio >= 1.5 else 60 if current_ratio >= 1 else 35)
        if debt_to_equity is not None:
            heuristic_health_scores.append(80 if debt_to_equity <= 0.75 else 60 if debt_to_equity <= 1.5 else 35)
        if pe_ratio is not None and pe_ratio > 0:
            heuristic_health_scores.append(70 if pe_ratio <= 25 else 55 if pe_ratio <= 40 else 40)
        
        if 'strong' in explanation and 'health' in explanation:
            scores['financial_health'] = 85
        elif 'moderate' in explanation or 'stable' in explanation:
            scores['financial_health'] = 65
        elif 'weak' in explanation or 'concern' in explanation:
            scores['financial_health'] = 40
        elif heuristic_health_scores:
            scores['financial_health'] = sum(heuristic_health_scores) / len(heuristic_health_scores)
        else:
            scores['financial_health'] = 60  # Neutral
        
        # Risk assessment
        if metrics.risk_factors_count > 0 or 'risk' in explanation:
            scores['risk_assessment'] = 45
        else:
            scores['risk_assessment'] = 75
        
        # Data quality
        if metrics.financial_health_indicators:
            scores['data_quality'] = 80
        else:
            scores['data_quality'] = 40
        
        return scores
    
    def _calculate_overall_score(self, factor_scores: Dict[str, float]) -> float:
        """Calculate overall score."""
        if not factor_scores:
            return 50.0
        
        # Weighted average
        weights = {
            'financial_health': 0.60,
            'risk_assessment': 0.25,
            'data_quality': 0.15
        }
        
        weighted_sum = sum(
            factor_scores.get(factor, 50) * weight
            for factor, weight in weights.items()
        )
        
        return weighted_sum
    
    def _calculate_confidence(self, financial_data: Dict[str, Any]) -> float:
        """Calculate confidence based on data availability."""
        if not financial_data:
            return 0.2
        
        has_profile = bool(financial_data.get('profile'))
        has_financials = bool(financial_data.get('financials'))
        
        if has_profile and has_financials:
            return 0.75
        elif has_profile or has_financials:
            return 0.55
        else:
            return 0.30
    
    def _create_visualizations(
        self,
        metrics: RAGMetrics,
        factor_scores: Dict[str, float]
    ) -> List[VisualizationData]:
        """Create visualizations."""
        visualizations = []

        if factor_scores:
            visualizations.append(
                self.create_visualization(
                    chart_type="bar",
                    title="Financial Health Factors",
                    data={
                        "labels": [k.replace('_', ' ').title() for k in factor_scores.keys()],
                        "values": list(factor_scores.values()),
                        "colors": ["#10b981" if v >= 60 else "#f59e0b" if v >= 40 else "#ef4444"
                                   for v in factor_scores.values()]
                    }
                )
            )

        return visualizations

    def _build_signals_risks(
        self,
        metrics: RAGMetrics,
        factor_scores: Dict[str, float],
        analysis: Dict[str, Any],
    ) -> tuple[List[str], List[str], List[str]]:
        """Build signals, risks, warnings from RAG analysis."""
        signals: List[str] = []
        risks: List[str] = []
        warnings: List[str] = []

        explanation = analysis.get('explanation', '').lower()

        if 'strong' in explanation and 'health' in explanation:
            signals.append("LLM assessment: strong financial health.")
        if 'weak' in explanation or 'concern' in explanation:
            risks.append("LLM assessment: financial concerns identified.")
        if 'risk' in explanation:
            risks.append("Risk factors mentioned in LLM analysis.")

        if metrics.risk_factors_count > 2:
            risks.append(f"{metrics.risk_factors_count} risk factor(s) identified in filing analysis.")

        if not metrics.financial_health_indicators:
            warnings.append("Limited financial health indicators available — analysis quality reduced.")

        return signals, risks, warnings


# Global instance
rag_filing_agent = RAGFilingAgent()
