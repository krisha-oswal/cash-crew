"""
XAI (Explainable AI) Agent - Generates detailed explanations using Groq LLaMA-3-70B.
"""
from typing import Dict, Any, List
import logging
import json

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, VisualizationData
from services.llm_service import llm_router, LLMProvider

logger = logging.getLogger(__name__)


class XAIAgent(BaseAgent):
    """Generates explainable AI insights using Groq LLaMA-3-70B."""
    
    def __init__(self):
        super().__init__("XAI Reasoning Agent")
    
    async def analyze(
        self,
        ticker: str,
        company_name: str,
        agent_scores: Dict[str, AgentScore],
        final_score: float,
        recommendation: str,
        **kwargs
    ) -> AgentScore:
        """
        Generate XAI explanations for the analysis.
        
        Args:
            ticker: Stock ticker
            company_name: Company name
            agent_scores: All agent scores
            final_score: Final aggregated score
            recommendation: BUY/HOLD/SELL
        
        Returns:
            AgentScore with detailed explanations and factor contributions
        """
        self.log_info(f"Generating XAI explanations for {ticker}")
        
        try:
            # Calculate factor contributions
            factor_contributions = self._calculate_factor_contributions(agent_scores, final_score)
            
            # Generate detailed explanation using LLM
            explanation = await self._generate_llm_explanation(
                ticker,
                company_name,
                agent_scores,
                final_score,
                recommendation,
                factor_contributions
            )
            
            # Create visualizations
            visualizations = self._create_visualizations(factor_contributions, agent_scores)
            
            self.log_info("XAI explanation generated successfully")
            
            return self.create_score(
                score=final_score,  # Pass through final score
                confidence=0.9,  # High confidence in explanation
                factors=factor_contributions,
                metrics={
                    "explanation_length": len(explanation),
                    "factors_analyzed": len(factor_contributions)
                },
                visualizations=visualizations,
                explanation=explanation
            )
            
        except Exception as e:
            self.log_error(f"XAI generation failed: {str(e)}")
            # Return simple explanation on error
            simple_explanation = self._generate_simple_explanation(
                agent_scores, final_score, recommendation
            )
            return self.create_score(
                score=final_score,
                confidence=0.5,
                factors={},
                metrics={"error": str(e)},
                visualizations=[],
                explanation=simple_explanation
            )
    
    def _calculate_factor_contributions(
        self,
        agent_scores: Dict[str, AgentScore],
        final_score: float
    ) -> Dict[str, float]:
        """Calculate how much each factor contributed to the final score."""
        contributions = {}
        
        for agent_name, score in agent_scores.items():
            if score.score is not None:
                # Calculate contribution as deviation from neutral (50)
                deviation = score.score - 50
                # Weight by confidence
                weighted_contribution = deviation * score.confidence
                contributions[agent_name] = weighted_contribution
        
        return contributions
    
    async def _generate_llm_explanation(
        self,
        ticker: str,
        company_name: str,
        agent_scores: Dict[str, AgentScore],
        final_score: float,
        recommendation: str,
        factor_contributions: Dict[str, float]
    ) -> str:
        """Generate detailed explanation using Groq LLaMA-3-70B."""
        
        # Prepare agent summaries
        agent_summaries = []
        for agent_name, score in agent_scores.items():
            if score.score is not None:
                agent_summaries.append(
                    f"- {agent_name}: {score.score:.1f}/100 (confidence: {score.confidence:.0%})\n"
                    f"  {score.explanation or 'No explanation provided'}"
                )
        
        agents_text = "\n".join(agent_summaries)
        
        # Create prompt for LLM
        prompt = f"""You are a financial analyst explaining an AI-powered stock analysis to investors.

Company: {company_name} ({ticker})
Final Score: {final_score:.1f}/100
Recommendation: {recommendation}

Agent Analysis Results:
{agents_text}

Generate a clear, professional explanation that:
1. Summarizes the overall recommendation and reasoning
2. Highlights the key factors driving the recommendation
3. Explains any conflicting signals between agents
4. Provides actionable insights for investors
5. Mentions important risks or caveats

Keep it concise (3-4 paragraphs) and investor-friendly. Use clear language without jargon."""

        system_prompt = """You are a senior financial analyst with expertise in equity research. 
Provide clear, actionable explanations that help investors make informed decisions."""
        
        try:
            # Use Groq LLaMA-3-70B for fast, high-quality explanations
            explanation, provider = await llm_router.generate(
                prompt=prompt,
                provider_priority=[
                    LLMProvider.GROQ_LLAMA3_70B,
                    LLMProvider.OLLAMA_LLAMA3
                ],
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=800
            )
            
            self.log_info(f"Generated explanation using {provider.value}")
            return explanation.strip()
            
        except Exception as e:
            self.log_error(f"LLM explanation failed: {str(e)}")
            return self._generate_simple_explanation(agent_scores, final_score, recommendation)
    
    def _generate_simple_explanation(
        self,
        agent_scores: Dict[str, AgentScore],
        final_score: float,
        recommendation: str
    ) -> str:
        """Generate simple fallback explanation."""
        parts = []
        
        parts.append(f"**{recommendation} Recommendation** (Score: {final_score:.1f}/100)")
        parts.append("")
        
        # Summarize each agent
        for agent_name, score in agent_scores.items():
            if score.score is not None:
                parts.append(f"**{agent_name}**: {score.score:.1f}/100")
                if score.explanation:
                    parts.append(f"  {score.explanation}")
        
        parts.append("")
        parts.append("This analysis combines multiple AI agents to provide a comprehensive view of the investment opportunity.")
        
        return "\n".join(parts)
    
    def _create_visualizations(
        self,
        factor_contributions: Dict[str, float],
        agent_scores: Dict[str, AgentScore]
    ) -> List[VisualizationData]:
        """Create visualizations for XAI."""
        visualizations = []
        
        # Factor contribution waterfall chart
        if factor_contributions:
            # Sort by absolute contribution
            sorted_factors = sorted(
                factor_contributions.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )
            
            visualizations.append(
                self.create_visualization(
                    chart_type="bar",
                    title="Factor Contributions to Final Score",
                    data={
                        "labels": [f[0] for f in sorted_factors],
                        "values": [f[1] for f in sorted_factors],
                        "colors": ["#10b981" if v > 0 else "#ef4444" for _, v in sorted_factors]
                    },
                    config={
                        "description": "Positive values increase the score, negative values decrease it"
                    }
                )
            )
        
        # Confidence comparison
        agent_names = []
        confidence_values = []
        
        for name, score in agent_scores.items():
            if score.confidence is not None:
                agent_names.append(name)
                confidence_values.append(score.confidence * 100)
        
        if agent_names:
            visualizations.append(
                self.create_visualization(
                    chart_type="bar",
                    title="Agent Confidence Levels",
                    data={
                        "labels": agent_names,
                        "values": confidence_values,
                        "colors": ["#10b981" if v >= 70 else "#f59e0b" if v >= 50 else "#ef4444" 
                                   for v in confidence_values]
                    }
                )
            )
        
        return visualizations


# Global instance
xai_agent = XAIAgent()
