"""
Governance & Fraud Detection Agent - Identifies red flags and governance issues.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, VisualizationData, GovernanceMetrics
from services.finnhub_service import finnhub_service
from services.news_service import news_service

logger = logging.getLogger(__name__)


class GovernanceAgent(BaseAgent):
    """Analyzes corporate governance and detects potential fraud indicators."""
    
    def __init__(self):
        super().__init__("Governance & Fraud Analyst")
    
    async def analyze(self, ticker: str, **kwargs) -> AgentScore:
        """
        Analyze governance and fraud indicators.
        
        Checks for:
        - Insider trading patterns
        - Executive compensation issues
        - Auditor changes
        - Restatements
        - Legal issues from news
        
        Returns:
            AgentScore with governance assessment (0-100, higher is better)
        """
        self.log_info(f"Starting governance analysis for {ticker}")
        
        try:
            # Fetch governance data
            metrics = await self._fetch_governance_data(ticker)
            
            # Detect red flags
            red_flags = self._detect_red_flags(metrics)
            
            # Calculate factor scores
            factor_scores = self._calculate_factor_scores(metrics, red_flags)
            
            # Calculate overall score (100 = clean, 0 = major issues)
            overall_score = self._calculate_overall_score(factor_scores, red_flags)
            
            # Calculate confidence
            confidence = self._calculate_confidence(metrics)
            
            # Generate visualizations
            visualizations = self._create_visualizations(red_flags, factor_scores)
            
            # Create explanation
            explanation = self._generate_explanation(red_flags, overall_score)
            
            signals, risks, warnings = self._extract_signals_risks(red_flags, metrics)
            status = "success" if metrics.recent_news_count > 0 else "partial"
            if status == "partial":
                warnings.append("No news data found — governance score is based on absence of red flags only.")

            self.log_info(f"Governance analysis complete: Score={overall_score:.2f}, Red flags={len(red_flags)}")

            return self.create_score(
                score=overall_score,
                confidence=confidence,
                factors=factor_scores,
                metrics={
                    "red_flag_count": len(red_flags),
                    "red_flags": red_flags,
                    **metrics.__dict__
                },
                visualizations=visualizations,
                explanation=explanation,
                status=status,
                signals=signals,
                risks=risks,
                warnings=warnings,
                data_source="Finnhub + NewsAPI",
            )

        except Exception as e:
            self.log_error(f"Governance analysis failed: {str(e)}")
            return self.create_failed_score(str(e))
    
    async def _fetch_governance_data(self, ticker: str) -> GovernanceMetrics:
        """Fetch governance-related data."""
        metrics = GovernanceMetrics()
        
        try:
            # Get company profile for basic info
            if finnhub_service.is_available():
                profile = finnhub_service.get_company_profile(ticker)
                if profile:
                    metrics.company_name = profile.get('name', '')
                    metrics.country = profile.get('country', '')
                    metrics.exchange = profile.get('exchange', '')
        except Exception as e:
            self.log_warning(f"Failed to fetch profile: {str(e)}")
        
        # Get recent news for legal/governance issues
        try:
            if news_service.is_available():
                news_articles = news_service.get_company_news(
                    company_name=metrics.company_name or ticker,
                    ticker=ticker,
                    days_back=90
                )
                metrics.recent_news_count = len(news_articles)
                
                # Scan for governance keywords
                governance_keywords = [
                    'lawsuit', 'fraud', 'investigation', 'sec', 'regulatory',
                    'scandal', 'misconduct', 'violation', 'fine', 'penalty',
                    'insider trading', 'accounting', 'restatement', 'auditor'
                ]
                
                legal_articles = []
                for article in news_articles:
                    title = article.get('title', '').lower()
                    description = article.get('description', '').lower()
                    content = f"{title} {description}"
                    
                    if any(keyword in content for keyword in governance_keywords):
                        legal_articles.append({
                            'title': article.get('title', ''),
                            'date': article.get('publishedAt', '')
                        })
                
                metrics.legal_issues = legal_articles[:5]  # Top 5
        except Exception as e:
            self.log_warning(f"Failed to fetch news: {str(e)}")
        
        return metrics
    
    def _detect_red_flags(self, metrics: GovernanceMetrics) -> List[Dict[str, Any]]:
        """Detect governance red flags."""
        red_flags = []
        
        # Check for legal issues in news
        if metrics.legal_issues:
            for issue in metrics.legal_issues:
                severity = "high" if any(word in issue['title'].lower() 
                                        for word in ['fraud', 'investigation', 'sec']) else "medium"
                red_flags.append({
                    "type": "legal_issue",
                    "severity": severity,
                    "description": issue['title'],
                    "date": issue.get('date', '')
                })
        
        # If no data available, assume clean
        if not metrics.legal_issues and metrics.recent_news_count == 0:
            # No news could mean either clean or lack of coverage
            pass
        
        return red_flags
    
    def _calculate_factor_scores(
        self,
        metrics: GovernanceMetrics,
        red_flags: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate governance factor scores."""
        scores = {}
        
        # Legal compliance score
        high_severity_flags = [f for f in red_flags if f.get('severity') == 'high']
        medium_severity_flags = [f for f in red_flags if f.get('severity') == 'medium']
        
        if not red_flags:
            scores['legal_compliance'] = 100
        elif high_severity_flags:
            scores['legal_compliance'] = max(20, 100 - len(high_severity_flags) * 30)
        elif medium_severity_flags:
            scores['legal_compliance'] = max(50, 100 - len(medium_severity_flags) * 15)
        else:
            scores['legal_compliance'] = 80
        
        # Transparency score (based on news coverage)
        if metrics.recent_news_count >= 10:
            scores['transparency'] = 90
        elif metrics.recent_news_count >= 5:
            scores['transparency'] = 75
        elif metrics.recent_news_count > 0:
            scores['transparency'] = 60
        else:
            scores['transparency'] = 50  # Low coverage = uncertain
        
        # Overall governance score
        if not red_flags and metrics.recent_news_count > 0:
            scores['overall_governance'] = 95
        elif not red_flags:
            scores['overall_governance'] = 80  # No news, assume okay
        else:
            scores['overall_governance'] = scores['legal_compliance']
        
        return scores
    
    def _calculate_overall_score(
        self,
        factor_scores: Dict[str, float],
        red_flags: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall governance score."""
        if not factor_scores:
            return 75.0  # Neutral-positive default
        
        # Weighted average
        weights = {
            'legal_compliance': 0.50,
            'transparency': 0.20,
            'overall_governance': 0.30
        }
        
        weighted_sum = sum(
            factor_scores.get(factor, 75) * weight
            for factor, weight in weights.items()
        )
        
        # Severe penalty for high-severity red flags
        high_severity_count = len([f for f in red_flags if f.get('severity') == 'high'])
        if high_severity_count > 0:
            weighted_sum = min(weighted_sum, 40)  # Cap at 40 for serious issues
        
        return weighted_sum
    
    def _calculate_confidence(self, metrics: GovernanceMetrics) -> float:
        """Calculate confidence based on data availability."""
        # Higher confidence with more news coverage
        if metrics.recent_news_count >= 10:
            return 0.85
        elif metrics.recent_news_count >= 5:
            return 0.70
        elif metrics.recent_news_count > 0:
            return 0.55
        else:
            return 0.40  # Low confidence with no data
    
    def _create_visualizations(
        self,
        red_flags: List[Dict[str, Any]],
        factor_scores: Dict[str, float]
    ) -> List[VisualizationData]:
        """Create visualizations."""
        visualizations = []
        
        # Red flag severity distribution
        if red_flags:
            severity_counts = {
                'high': len([f for f in red_flags if f.get('severity') == 'high']),
                'medium': len([f for f in red_flags if f.get('severity') == 'medium']),
                'low': len([f for f in red_flags if f.get('severity') == 'low'])
            }
            
            visualizations.append(
                self.create_visualization(
                    chart_type="pie",
                    title="Red Flag Severity Distribution",
                    data={
                        "labels": ["High", "Medium", "Low"],
                        "values": [severity_counts['high'], severity_counts['medium'], severity_counts['low']],
                        "colors": ["#ef4444", "#f59e0b", "#fbbf24"]
                    }
                )
            )
        
        # Factor scores
        if factor_scores:
            visualizations.append(
                self.create_visualization(
                    chart_type="bar",
                    title="Governance Factor Scores",
                    data={
                        "labels": [k.replace('_', ' ').title() for k in factor_scores.keys()],
                        "values": list(factor_scores.values()),
                        "colors": ["#10b981" if v >= 70 else "#f59e0b" if v >= 50 else "#ef4444" 
                                   for v in factor_scores.values()]
                    }
                )
            )
        
        return visualizations
    
    def _generate_explanation(
        self,
        red_flags: List[Dict[str, Any]],
        overall_score: float
    ) -> str:
        """Generate explanation."""
        parts = []

        if overall_score >= 80:
            parts.append("Strong governance profile with no major red flags detected.")
        elif overall_score >= 60:
            parts.append("Acceptable governance with minor concerns.")
        else:
            parts.append("Governance concerns detected that warrant investigation.")

        if red_flags:
            high_severity = [f for f in red_flags if f.get('severity') == 'high']
            if high_severity:
                parts.append(f"⚠️ {len(high_severity)} high-severity issues: {high_severity[0]['description'][:100]}")
            else:
                parts.append(f"{len(red_flags)} governance-related news items detected.")
        else:
            parts.append("No significant legal or regulatory issues found in recent news.")

        return " ".join(parts)

    def _extract_signals_risks(
        self,
        red_flags: List[Dict[str, Any]],
        metrics: GovernanceMetrics,
    ) -> tuple[List[str], List[str], List[str]]:
        """Build signals, risks, warnings from governance data."""
        signals: List[str] = []
        risks: List[str] = []
        warnings: List[str] = []

        if not red_flags:
            signals.append("No legal, regulatory, or governance red flags found in recent news.")
        else:
            high = [f for f in red_flags if f.get('severity') == 'high']
            medium = [f for f in red_flags if f.get('severity') == 'medium']
            if high:
                risks.append(f"{len(high)} high-severity governance issue(s) detected.")
            if medium:
                risks.append(f"{len(medium)} medium-severity governance concern(s) in news.")

        if metrics.recent_news_count == 0:
            warnings.append("No news coverage found — governance score is assumption-based.")
        elif metrics.recent_news_count < 5:
            warnings.append(f"Low news coverage ({metrics.recent_news_count} articles) — limited governance signal.")

        return signals, risks, warnings


# Global instance
governance_agent = GovernanceAgent()
