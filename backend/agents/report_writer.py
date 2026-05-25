"""
Report Writer Agent - Generates formatted reports and summaries.
"""
from typing import Dict, Any, List
import logging
from datetime import datetime

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, FinalReport
from services.llm_service import llm_router, LLMProvider

logger = logging.getLogger(__name__)


class ReportWriterAgent(BaseAgent):
    """Generates executive summaries and formatted reports."""
    
    def __init__(self):
        super().__init__("Report Writer")
    
    async def analyze(self, ticker: str, **kwargs) -> AgentScore:
        """Not used directly - use generate_executive_summary instead."""
        raise NotImplementedError("Use generate_executive_summary() instead")
    
    async def generate_executive_summary(
        self,
        report: FinalReport
    ) -> str:
        """
        Generate executive summary using Groq for fast generation.
        
        Args:
            report: Complete analysis report
        
        Returns:
            Executive summary text
        """
        self.log_info(f"Generating executive summary for {report.ticker}")
        
        try:
            # Prepare data for LLM
            summary_data = self._prepare_summary_data(report)
            
            # Generate summary using LLM
            summary = await self._generate_llm_summary(summary_data, report)
            
            return summary
            
        except Exception as e:
            self.log_error(f"Summary generation failed: {str(e)}")
            return self._generate_simple_summary(report)
    
    def _prepare_summary_data(self, report: FinalReport) -> Dict[str, Any]:
        """Prepare data for summary generation."""
        return {
            "ticker": report.ticker,
            "company_name": report.company_name,
            "recommendation": report.recommendation,
            "final_score": report.final_score,
            "confidence": report.confidence,
            "fundamental_score": report.fundamental_score.score if report.fundamental_score else None,
            "technical_score": report.technical_score.score if report.technical_score else None,
            "sentiment_score": report.sentiment_score.score if report.sentiment_score else None,
            "risk_score": report.risk_score.score if report.risk_score else None,
        }
    
    async def _generate_llm_summary(
        self,
        data: Dict[str, Any],
        report: FinalReport
    ) -> str:
        """Generate summary using Groq."""
        
        prompt = f"""Generate a concise executive summary for this stock analysis:

Company: {data['company_name']} ({data['ticker']})
Recommendation: {data['recommendation']}
Overall Score: {data['final_score']:.1f}/100
Confidence: {data['confidence']:.0%}

Agent Scores:
- Fundamental: {data['fundamental_score']:.1f}/100
- Technical: {data['technical_score']:.1f}/100
- Sentiment: {data['sentiment_score']:.1f}/100
- Risk: {data['risk_score']:.1f}/100 if data['risk_score'] else 'N/A'

Write a 2-3 sentence executive summary that:
1. States the recommendation clearly
2. Highlights the key supporting factors
3. Mentions any important risks or caveats

Be concise and professional."""

        system_prompt = "You are a financial analyst writing executive summaries for investment reports."
        
        try:
            summary, provider = await llm_router.generate(
                prompt=prompt,
                provider_priority=[
                    LLMProvider.GROQ_LLAMA3_70B,
                    LLMProvider.GROQ_MIXTRAL,
                    LLMProvider.OLLAMA_LLAMA3
                ],
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=200
            )
            
            return summary.strip()
            
        except Exception as e:
            self.log_error(f"LLM summary failed: {str(e)}")
            return self._generate_simple_summary(report)
    
    def _generate_simple_summary(self, report: FinalReport) -> str:
        """Generate simple fallback summary."""
        parts = []
        
        # Opening statement
        if report.recommendation == "BUY":
            parts.append(f"{report.company_name} ({report.ticker}) shows strong investment potential with a {report.recommendation} recommendation.")
        elif report.recommendation == "HOLD":
            parts.append(f"{report.company_name} ({report.ticker}) presents a mixed outlook with a {report.recommendation} recommendation.")
        else:
            parts.append(f"{report.company_name} ({report.ticker}) shows concerning signals with a {report.recommendation} recommendation.")
        
        # Key factors
        strong_agents = []
        weak_agents = []
        
        for agent_name, score in [
            ("Fundamental", report.fundamental_score),
            ("Technical", report.technical_score),
            ("Sentiment", report.sentiment_score)
        ]:
            if score and score.score:
                if score.score >= 70:
                    strong_agents.append(agent_name.lower())
                elif score.score < 40:
                    weak_agents.append(agent_name.lower())
        
        if strong_agents:
            parts.append(f"The analysis is supported by strong {', '.join(strong_agents)} indicators.")
        
        if weak_agents:
            parts.append(f"However, {', '.join(weak_agents)} analysis shows weakness.")
        
        # Confidence statement
        if report.confidence >= 0.7:
            parts.append(f"This recommendation has high confidence ({report.confidence:.0%}).")
        elif report.confidence < 0.5:
            parts.append(f"Note: This recommendation has lower confidence ({report.confidence:.0%}) due to limited data availability.")
        
        return " ".join(parts)
    
    def generate_text_report(self, report: FinalReport) -> str:
        """Generate full text report."""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append(f"EQUITY RESEARCH REPORT: {report.company_name} ({report.ticker})")
        lines.append("=" * 80)
        lines.append(f"Analysis Date: {report.analysis_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"Generated by: Cash Crew Multi-Agent AI System")
        lines.append("")
        
        # Recommendation
        lines.append("-" * 80)
        lines.append("RECOMMENDATION")
        lines.append("-" * 80)
        lines.append(f"Rating: {report.recommendation}")
        lines.append(f"Score: {report.final_score:.2f}/100")
        lines.append(f"Confidence: {report.confidence:.1%}")
        lines.append("")
        
        # Agent Scores
        lines.append("-" * 80)
        lines.append("AGENT ANALYSIS SUMMARY")
        lines.append("-" * 80)
        
        for agent_name, score in [
            ("Fundamental Analyst", report.fundamental_score),
            ("Technical Analyst", report.technical_score),
            ("Sentiment Analyst", report.sentiment_score),
            ("Risk Analyst", report.risk_score)
        ]:
            if score:
                lines.append(f"\n{agent_name}:")
                lines.append(f"  Score: {score.score:.2f}/100")
                lines.append(f"  Confidence: {score.confidence:.1%}")
                if score.explanation:
                    lines.append(f"  Analysis: {score.explanation}")
        
        lines.append("")
        
        # XAI Explanation
        if report.xai_explanation:
            lines.append("-" * 80)
            lines.append("DETAILED EXPLANATION")
            lines.append("-" * 80)
            lines.append(report.xai_explanation)
            lines.append("")
        
        # Performance Metrics
        lines.append("-" * 80)
        lines.append("SYSTEM METRICS")
        lines.append("-" * 80)
        lines.append(f"Analysis Latency: {report.latency_seconds:.2f} seconds")
        lines.append(f"Error Count: {report.error_count}")
        lines.append("")
        
        # Footer
        lines.append("=" * 80)
        lines.append("Disclaimer: This report is generated by AI and should not be considered")
        lines.append("as financial advice. Please consult with a qualified financial advisor")
        lines.append("before making investment decisions.")
        lines.append("=" * 80)
        
        return "\n".join(lines)


# Global instance
report_writer = ReportWriterAgent()
