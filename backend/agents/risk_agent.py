"""
Risk Analyst Agent - Vertical leader that aggregates and resolves conflicts.
"""
from typing import Dict, Any, List
import logging

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, VisualizationData

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """
    Vertical leader agent that performs:
    - Conflict resolution between agents
    - Risk assessment
    - Final score aggregation
    - Spider chart generation
    """
    
    def __init__(self):
        super().__init__("Risk Analyst")
    
    async def analyze(
        self,
        ticker: str,
        agent_scores: Dict[str, AgentScore],
        **kwargs
    ) -> AgentScore:
        """
        Perform risk analysis and conflict resolution.
        
        Args:
            ticker: Stock ticker
            agent_scores: Dictionary of agent scores from horizontal agents
        
        Returns:
            AgentScore with risk assessment and aggregated insights
        """
        self.log_info(f"Starting risk analysis for {ticker}")
        
        try:
            # Detect conflicts between agents
            conflicts = self._detect_conflicts(agent_scores)
            
            # Calculate risk metrics
            risk_metrics = self._calculate_risk_metrics(agent_scores, conflicts)
            
            # Calculate overall risk score
            risk_score = self._calculate_risk_score(risk_metrics, agent_scores)
            
            # Calculate confidence
            confidence = self._calculate_confidence(agent_scores, conflicts)
            
            # Generate visualizations
            visualizations = self._create_visualizations(agent_scores, risk_metrics)
            
            # Create explanation
            explanation = self._generate_explanation(risk_metrics, conflicts, risk_score)

            # Build signals, risks, warnings
            signals: List[str] = []
            risks: List[str] = []
            warnings: List[str] = []

            valid_agent_count = sum(1 for s in agent_scores.values() if s.score is not None)
            total_agent_count = len(agent_scores)
            if valid_agent_count < total_agent_count:
                warnings.append(
                    f"{total_agent_count - valid_agent_count} agent(s) failed and were excluded from risk computation."
                )
            if conflicts:
                high_conf = [c for c in conflicts if c.get('severity') == 'high']
                if high_conf:
                    warnings.append(f"{len(high_conf)} high-severity agent conflict(s) detected — recommendation reliability reduced.")
                    risks.append("Significant agent disagreement — treat recommendation with caution.")

            agreement = risk_metrics.get('agent_agreement', 100)
            if agreement >= 70:
                signals.append(f"Strong agent consensus ({agreement:.0f}% agreement).")
            elif agreement < 50:
                risks.append(f"Low agent consensus ({agreement:.0f}%) — high uncertainty.")

            self.log_info(f"Risk analysis complete: Score={risk_score:.2f}, Conflicts={len(conflicts)}")

            return self.create_score(
                score=risk_score,
                confidence=confidence,
                factors=risk_metrics,
                metrics={
                    "conflict_count": len(conflicts),
                    "conflicts": conflicts,
                    "agent_agreement": risk_metrics.get("agent_agreement", 0.0)
                },
                visualizations=visualizations,
                explanation=explanation,
                status="success" if valid_agent_count >= 4 else "partial",
                signals=signals,
                risks=risks,
                warnings=warnings,
            )

        except Exception as e:
            self.log_error(f"Risk analysis failed: {str(e)}")
            return self.create_failed_score(str(e))
    
    def _detect_conflicts(self, agent_scores: Dict[str, AgentScore]) -> List[Dict[str, Any]]:
        """Detect conflicts between agent recommendations."""
        conflicts = []
        
        # Get scores from available agents
        scores = {name: score.score for name, score in agent_scores.items() if score.score is not None}
        
        if len(scores) < 2:
            return conflicts
        
        # Check for significant disagreements (>30 points difference)
        score_list = list(scores.items())
        for i in range(len(score_list)):
            for j in range(i + 1, len(score_list)):
                agent1_name, score1 = score_list[i]
                agent2_name, score2 = score_list[j]
                
                diff = abs(score1 - score2)
                if diff > 30:
                    conflicts.append({
                        "agent1": agent1_name,
                        "agent2": agent2_name,
                        "score1": score1,
                        "score2": score2,
                        "difference": diff,
                        "severity": "high" if diff > 50 else "medium"
                    })
        
        return conflicts
    
    def _calculate_risk_metrics(
        self,
        agent_scores: Dict[str, AgentScore],
        conflicts: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate risk-related metrics."""
        metrics = {}
        
        # Agent agreement score (0-100, higher is better)
        if len(agent_scores) > 1:
            scores = [s.score for s in agent_scores.values() if s.score is not None]
            if scores:
                # Calculate standard deviation
                mean_score = sum(scores) / len(scores)
                variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
                std_dev = variance ** 0.5
                
                # Convert to agreement score (lower std_dev = higher agreement)
                # Max std_dev is ~50 (when scores are 0 and 100)
                agreement = max(0, 100 - (std_dev * 2))
                metrics["agent_agreement"] = agreement
        
        # Conflict severity score (0-100, lower is better)
        if conflicts:
            avg_conflict_diff = sum(c["difference"] for c in conflicts) / len(conflicts)
            conflict_severity = min(100, avg_conflict_diff)
            metrics["conflict_severity"] = conflict_severity
        else:
            metrics["conflict_severity"] = 0
        
        # Data quality score (based on agent confidence)
        confidences = [s.confidence for s in agent_scores.values() if s.confidence is not None]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            metrics["data_quality"] = avg_confidence * 100
        
        # Volatility risk (based on score spread)
        scores = [s.score for s in agent_scores.values() if s.score is not None]
        if scores:
            score_range = max(scores) - min(scores)
            metrics["volatility_risk"] = min(100, score_range)
        
        return metrics
    
    def _calculate_risk_score(
        self,
        risk_metrics: Dict[str, float],
        agent_scores: Dict[str, AgentScore]
    ) -> float:
        """
        Calculate overall risk score.
        Lower risk = higher score (safer investment)
        """
        # Start with average agent score
        scores = [s.score for s in agent_scores.values() if s.score is not None]
        if not scores:
            return 50.0
        
        base_score = sum(scores) / len(scores)
        
        # Adjust based on risk factors
        adjustments = 0
        
        # Penalize for low agreement
        if "agent_agreement" in risk_metrics:
            agreement = risk_metrics["agent_agreement"]
            if agreement < 50:
                adjustments -= (50 - agreement) * 0.2  # Up to -10 points
        
        # Penalize for high conflict severity
        if "conflict_severity" in risk_metrics:
            severity = risk_metrics["conflict_severity"]
            if severity > 30:
                adjustments -= (severity - 30) * 0.15  # Up to -10.5 points
        
        # Penalize for low data quality
        if "data_quality" in risk_metrics:
            quality = risk_metrics["data_quality"]
            if quality < 60:
                adjustments -= (60 - quality) * 0.1  # Up to -6 points
        
        final_score = max(0, min(100, base_score + adjustments))
        return final_score
    
    def _calculate_confidence(
        self,
        agent_scores: Dict[str, AgentScore],
        conflicts: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence in the risk assessment."""
        # Base confidence on agent confidences
        confidences = [s.confidence for s in agent_scores.values() if s.confidence is not None]
        if not confidences:
            return 0.3
        
        avg_confidence = sum(confidences) / len(confidences)
        
        # Reduce confidence if there are conflicts
        if conflicts:
            conflict_penalty = min(0.3, len(conflicts) * 0.1)
            avg_confidence = max(0.2, avg_confidence - conflict_penalty)
        
        return avg_confidence
    
    def _create_visualizations(
        self,
        agent_scores: Dict[str, AgentScore],
        risk_metrics: Dict[str, float]
    ) -> List[VisualizationData]:
        """Create visualizations including spider chart."""
        visualizations = []
        
        # Spider/Radar chart of agent scores
        agent_names = []
        agent_values = []
        
        for name, score in agent_scores.items():
            if score.score is not None:
                agent_names.append(name)
                agent_values.append(score.score)
        
        if agent_names:
            visualizations.append(
                self.create_visualization(
                    chart_type="spider",
                    title="Multi-Agent Score Comparison",
                    data={
                        "labels": agent_names,
                        "values": agent_values,
                        "max": 100
                    }
                )
            )
        
        # Risk metrics bar chart
        if risk_metrics:
            visualizations.append(
                self.create_visualization(
                    chart_type="bar",
                    title="Risk Assessment Metrics",
                    data={
                        "labels": [k.replace('_', ' ').title() for k in risk_metrics.keys()],
                        "values": list(risk_metrics.values()),
                        "colors": ["#10b981" if v >= 60 else "#f59e0b" if v >= 40 else "#ef4444" 
                                   for v in risk_metrics.values()]
                    }
                )
            )
        
        return visualizations
    
    def _generate_explanation(
        self,
        risk_metrics: Dict[str, float],
        conflicts: List[Dict[str, Any]],
        risk_score: float
    ) -> str:
        """Generate explanation of risk assessment."""
        parts = []
        
        # Overall risk assessment
        if risk_score >= 70:
            parts.append("Low risk profile with strong agent consensus.")
        elif risk_score >= 50:
            parts.append("Moderate risk with some uncertainty.")
        else:
            parts.append("High risk profile with significant concerns.")
        
        # Agent agreement
        if "agent_agreement" in risk_metrics:
            agreement = risk_metrics["agent_agreement"]
            if agreement >= 70:
                parts.append(f"High agent agreement ({agreement:.0f}%).")
            elif agreement < 50:
                parts.append(f"Low agent agreement ({agreement:.0f}%) indicates uncertainty.")
        
        # Conflicts
        if conflicts:
            high_severity = [c for c in conflicts if c["severity"] == "high"]
            if high_severity:
                parts.append(f"Warning: {len(high_severity)} high-severity conflicts detected.")
        
        return " ".join(parts)


# Global instance
risk_agent = RiskAgent()
