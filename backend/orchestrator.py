"""
Multi-agent orchestrator for coordinating analysis workflow.

Key changes from v1:
- Failed agents produce score=None, status="failed" — they are EXCLUDED from aggregation
- Final score is computed only from agents that returned a valid (non-null) score
- Confidence is weighted by the fraction of agents that succeeded
- SystemDebugAudit is generated automatically after every run
"""
import asyncio
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
import logging

from models.schemas import (
    AnalysisRequest, FinalReport, AgentScore,
    SystemDebugAudit, BrokenAgentInfo, DataGap, AggregationIssue, FinalDecision
)
from agents.fundamental_agent import fundamental_agent
from agents.technical_agent import technical_agent
from agents.sentiment_agent import sentiment_agent
from config.settings import settings

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates execution of all analysis agents."""

    def __init__(self):
        self.logger = logging.getLogger("orchestrator")

    async def analyze(self, request: AnalysisRequest) -> FinalReport:
        """
        Orchestrate complete stock analysis.

        Workflow:
        1. Execute horizontal agents in parallel
        2. Execute Risk Agent (vertical leader)
        3. Calculate final score — excluding failed agents
        4. Generate XAI explanations
        5. Generate SystemDebugAudit
        6. Return final report
        """
        start_time = datetime.utcnow()
        self.logger.info(f"Starting analysis for {request.ticker}")

        try:
            # Phase 1: Execute all horizontal agents in parallel
            self.logger.info("Phase 1: Executing all horizontal agents in parallel...")

            from agents.governance_agent import governance_agent
            from agents.pead_agent import pead_agent
            from agents.rag_filing_agent import rag_filing_agent
            from agents.macro_agent import macro_agent
            from agents.insider_agent import insider_agent

            results = await asyncio.gather(
                fundamental_agent.analyze(ticker=request.ticker, timeframe=request.timeframe, region=request.region),
                technical_agent.analyze(ticker=request.ticker, timeframe=request.timeframe),
                sentiment_agent.analyze(ticker=request.ticker),
                governance_agent.analyze(ticker=request.ticker),
                pead_agent.analyze(ticker=request.ticker),
                rag_filing_agent.analyze(ticker=request.ticker),
                macro_agent.analyze(ticker=request.ticker, data={}),
                insider_agent.analyze(ticker=request.ticker, data={}),
                return_exceptions=True
            )

            (fundamental_score, technical_score, sentiment_score,
             governance_score, pead_score, financial_health_score,
             macro_score, insider_score) = results

            # Convert any unhandled Python exceptions → proper failed AgentScore
            def _guard(result: Any, agent_name: str) -> AgentScore:
                if isinstance(result, Exception):
                    self.logger.error(f"{agent_name} raised exception: {result}")
                    return self._create_failed_score(agent_name, str(result))
                if isinstance(result, AgentScore):
                    return result
                return self._create_failed_score(agent_name, f"Unexpected return type: {type(result)}")

            fundamental_score = _guard(fundamental_score, "Fundamental Analyst")
            technical_score = _guard(technical_score, "Technical Analyst")
            sentiment_score = _guard(sentiment_score, "Sentiment Analyst")
            governance_score = _guard(governance_score, "Governance & Fraud")
            pead_score = _guard(pead_score, "PEAD Analyst")
            financial_health_score = _guard(financial_health_score, "RAG Filing & Financial Health")
            macro_score = _guard(macro_score, "Macro Economic Agent")
            insider_score = _guard(insider_score, "Insider Trading Agent")

            # Phase 2: Risk Agent (receives all scores including failed ones — for conflict detection)
            self.logger.info("Phase 2: Executing Risk Agent...")

            from agents.risk_agent import risk_agent

            agent_scores = {
                "Fundamental Analyst": fundamental_score,
                "Technical Analyst": technical_score,
                "Sentiment Analyst": sentiment_score,
                "Governance & Fraud": governance_score,
                "PEAD Analyst": pead_score,
                "RAG Filing & Financial Health": financial_health_score,
                "Macro Economic Agent": macro_score,
                "Insider Trading Agent": insider_score,
            }

            try:
                risk_score_result = await risk_agent.analyze(
                    ticker=request.ticker,
                    agent_scores=agent_scores
                )
                risk_score = _guard(risk_score_result, "Risk Analyst")
            except Exception as e:
                self.logger.error(f"Risk agent failed: {e}")
                risk_score = self._create_failed_score("Risk Analyst", str(e))

            # Phase 3: Calculate final score — EXCLUDING failed/null-score agents
            self.logger.info("Phase 3: Calculating final score (excluding failed agents)...")

            all_agent_scores = {**agent_scores, "Risk Analyst": risk_score}

            final_score, confidence, excluded_from_score = self._calculate_final_score_safe(
                fundamental_score, technical_score, sentiment_score,
                governance_score, pead_score, financial_health_score,
                risk_score, macro_score, insider_score
            )

            recommendation = self._determine_recommendation(final_score, confidence)
            company_name = await self._get_company_name(request.ticker)

            # Phase 4: XAI explanation
            self.logger.info("Phase 4: Generating XAI explanations...")

            from agents.xai_agent import xai_agent

            try:
                xai_score = await xai_agent.analyze(
                    ticker=request.ticker,
                    company_name=company_name,
                    agent_scores=all_agent_scores,
                    final_score=final_score,
                    recommendation=recommendation
                )
            except Exception as e:
                self.logger.error(f"XAI agent failed: {e}")
                from models.schemas import AgentScore as AS
                xai_score = AS(
                    agent_name="XAI Agent",
                    status="failed",
                    score=None,
                    confidence=0.0,
                    factors={},
                    metrics={"error": str(e)},
                    visualizations=[],
                    explanation="XAI explanation unavailable.",
                )

            # Phase 5: Executive Summary
            self.logger.info("Phase 5: Generating executive summary...")

            end_time = datetime.utcnow()
            latency = (end_time - start_time).total_seconds()

            error_count = sum(
                1 for s in [
                    fundamental_score, technical_score, sentiment_score,
                    governance_score, pead_score, financial_health_score,
                    macro_score, insider_score, risk_score
                ] if s.status == "failed"
            )

            preliminary_report = FinalReport(
                ticker=request.ticker,
                company_name=company_name,
                analysis_date=end_time,
                fundamental_score=fundamental_score,
                technical_score=technical_score,
                sentiment_score=sentiment_score,
                governance_score=governance_score,
                pead_score=pead_score,
                financial_health_score=financial_health_score,
                risk_score=risk_score,
                macro_score=macro_score,
                insider_score=insider_score,
                xai_explanation=xai_score.explanation or "Analysis complete.",
                xai_visualizations=xai_score.visualizations,
                final_score=final_score,
                recommendation=recommendation,
                confidence=confidence,
                latency_seconds=latency,
                data_freshness_hours=0.0,
                error_count=error_count,
                system_debug_audit=None,  # filled below
            )

            # Phase 6: Executive Summary wrapper
            try:
                from agents.report_writer import report_writer
                executive_summary = await report_writer.generate_executive_summary(preliminary_report)
                preliminary_report.xai_explanation = (
                    f"**Executive Summary**\n\n{executive_summary}\n\n---\n\n{xai_score.explanation or ''}"
                )
            except Exception as e:
                self.logger.warning(f"Report writer failed: {e}")

            # Phase 7: System Debug Audit
            self.logger.info("Phase 7: Generating System Debug Audit...")
            audit = self._generate_debug_audit(
                agent_scores=all_agent_scores,
                final_score=final_score,
                excluded_from_score=excluded_from_score,
                recommendation=recommendation,
            )
            preliminary_report.system_debug_audit = audit
            preliminary_report.final_decision = self._build_final_decision(
                agent_scores=all_agent_scores,
                audit=audit,
                final_score=final_score,
                recommendation=recommendation,
            )

            self.logger.info(
                f"Analysis complete: {recommendation} (score={final_score:.2f}, "
                f"confidence={confidence:.2f}, latency={latency:.2f}s, "
                f"reliability={audit.reliability_score:.0f})"
            )

            return preliminary_report

        except Exception as e:
            self.logger.error(f"Orchestration failed: {str(e)}")
            raise

    # ──────────────────────────────────────────────────────────────────────
    # SCORE AGGREGATION — CRITICAL FIX
    # Only agents with a non-null score are included in the weighted average.
    # Failed agents (score=None) are excluded entirely.
    # ──────────────────────────────────────────────────────────────────────

    def _calculate_final_score_safe(
        self,
        fundamental: AgentScore,
        technical: AgentScore,
        sentiment: AgentScore,
        governance: AgentScore,
        pead: AgentScore,
        financial_health: AgentScore,
        risk: AgentScore,
        macro: AgentScore,
        insider: AgentScore,
    ) -> tuple[float, float, List[str]]:
        """
        Calculate weighted final score using only agents with valid (non-null) scores.

        Returns:
            (final_score, confidence, excluded_agent_names)
        """
        # Map agent → weight
        weighted_agents = [
            (fundamental, settings.fundamental_weight, "Fundamental Analyst"),
            (technical, settings.technical_weight, "Technical Analyst"),
            (sentiment, settings.sentiment_weight, "Sentiment Analyst"),
            (governance, settings.governance_weight, "Governance & Fraud"),
            (pead, settings.pead_weight, "PEAD Analyst"),
            (financial_health, settings.financial_health_weight, "RAG Filing & Financial Health"),
            (risk, settings.risk_weight, "Risk Analyst"),
            (macro, settings.macro_weight, "Macro Economic Agent"),
            # Insider data currently comes from limited yfinance fields, not a reliable
            # SEC Form 4 feed. Keep it visible in reports but exclude it from scoring.
            (insider, 0.0, "Insider Trading Agent (experimental, excluded)"),
        ]

        valid: List[tuple[float, float, float]] = []   # (score, confidence, weight)
        excluded: List[str] = []

        for agent, weight, name in weighted_agents:
            if agent.score is not None and agent.status != "failed" and weight > 0:
                valid.append((agent.score, agent.confidence, weight))
            else:
                excluded.append(name)

        if not valid:
            # All agents failed — cannot produce a meaningful score
            return 50.0, 0.0, [n for _, _, n in weighted_agents]

        # Normalise weights to sum to 1.0
        total_weight = sum(w for _, _, w in valid)
        if total_weight == 0:
            return 50.0, 0.0, excluded

        final_score = sum(score * (w / total_weight) for score, _, w in valid)

        # Confidence: weighted average of agent confidences × fraction of valid agents
        raw_confidence = sum(conf * (w / total_weight) for _, conf, w in valid)
        valid_fraction = len(valid) / len(weighted_agents)
        confidence = raw_confidence * valid_fraction

        return round(final_score, 2), round(min(0.95, confidence), 2), excluded

    def _determine_recommendation(self, score: float, confidence: float) -> str:
        """Determine BUY/HOLD/SELL recommendation, gating BUY calls on confidence."""
        if score >= 61:
            if confidence < 0.45:
                return "HOLD"
            return "BUY"
        elif score >= 41:
            return "HOLD"
        else:
            return "SELL"

    # ──────────────────────────────────────────────────────────────────────
    # SYSTEM DEBUG AUDIT GENERATION
    # ──────────────────────────────────────────────────────────────────────

    def _generate_debug_audit(
        self,
        agent_scores: Dict[str, AgentScore],
        final_score: float,
        excluded_from_score: List[str],
        recommendation: str,
    ) -> SystemDebugAudit:
        """
        Generate a comprehensive SystemDebugAudit after every analysis run.
        Brutally honest — flags every issue.
        """
        broken_agents: List[BrokenAgentInfo] = []
        data_gaps: List[DataGap] = []
        invalid_outputs: List[str] = []
        aggregation_issues: List[AggregationIssue] = []
        recommendations: List[str] = []

        total = len(agent_scores)
        successful = sum(1 for s in agent_scores.values() if s.status == "success")
        partial = sum(1 for s in agent_scores.values() if s.status == "partial")
        failed = sum(1 for s in agent_scores.values() if s.status == "failed")

        # A. Identify broken agents
        for name, score in agent_scores.items():
            if score.status == "failed":
                reason = score.metrics.get("error", score.explanation or "Unknown failure")
                broken_agents.append(BrokenAgentInfo(
                    agent_name=name,
                    status="failed",
                    reason=str(reason)[:200],
                ))
            elif score.status == "partial":
                broken_agents.append(BrokenAgentInfo(
                    agent_name=name,
                    status="partial",
                    reason="; ".join(score.warnings) if score.warnings else "Partial data",
                ))

        # B. Identify data gaps
        fund = agent_scores.get("Fundamental Analyst")
        if fund and (fund.status == "failed" or fund.score is None):
            data_gaps.append(DataGap(
                category="financial_metrics",
                description="No financial ratios (ROE, ROA, P/E, D/E) available",
                affected_agents=["Fundamental Analyst"],
                severity="high",
            ))

        tech = agent_scores.get("Technical Analyst")
        if tech and (tech.status == "failed" or tech.score is None):
            data_gaps.append(DataGap(
                category="price_data",
                description="No historical price data available for technical indicators",
                affected_agents=["Technical Analyst"],
                severity="high",
            ))

        sent = agent_scores.get("Sentiment Analyst")
        if sent and sent.metrics.get("article_count", 1) == 0:
            data_gaps.append(DataGap(
                category="news_data",
                description="No news articles found for sentiment analysis",
                affected_agents=["Sentiment Analyst"],
                severity="medium",
            ))

        pead = agent_scores.get("PEAD Analyst")
        if pead and (pead.status == "failed" or pead.score is None):
            data_gaps.append(DataGap(
                category="earnings_data",
                description="No earnings/EPS data available for PEAD analysis",
                affected_agents=["PEAD Analyst"],
                severity="medium",
            ))

        insider = agent_scores.get("Insider Trading Agent")
        if insider and insider.score is None:
            data_gaps.append(DataGap(
                category="insider_data",
                description="No real insider trading data available (no SEC Form 4 feed connected)",
                affected_agents=["Insider Trading Agent"],
                severity="low",
            ))

        macro = agent_scores.get("Macro Economic Agent")
        if macro and macro.score is None:
            data_gaps.append(DataGap(
                category="macro_data",
                description="No macro indicator data fetched",
                affected_agents=["Macro Economic Agent"],
                severity="low",
            ))

        # C. Invalid / Misleading Outputs
        for name, score in agent_scores.items():
            # Flag agents that explain failure but still produced a score (legacy behaviour)
            if score.score is not None and score.explanation and (
                "Analysis failed" in score.explanation or
                "Unable to generate" in score.explanation
            ):
                invalid_outputs.append(
                    f"{name}: explanation indicates failure but score={score.score:.1f} was still produced"
                )

            # Flag agents with score exactly 50 and low confidence (likely placeholder)
            if score.score == 50.0 and score.confidence <= 0.15 and score.status != "failed":
                invalid_outputs.append(
                    f"{name}: score=50.0 with confidence={score.confidence:.2f} — "
                    f"possible default/placeholder value; treat as unreliable"
                )

        # D. Aggregation Issues
        if excluded_from_score:
            aggregation_issues.append(AggregationIssue(
                issue_type="excluded_agents",
                description=f"{len(excluded_from_score)} agent(s) excluded from final score due to null/failed status: {', '.join(excluded_from_score)}",
                recommendation="Add fallback data sources so these agents can produce at least partial scores",
            ))

        active_agents_count = total - failed
        if active_agents_count < 4:
            aggregation_issues.append(AggregationIssue(
                issue_type="insufficient_active_agents",
                description=f"Only {active_agents_count}/{total} agents produced scores. Final score is based on sparse data.",
                recommendation="Resolve API failures to increase coverage before acting on this recommendation",
            ))

        # E. Reliability Score (0–100)
        # Based on: agent success ratio (60%) + data quality of working agents (40%)
        success_ratio = (successful + partial * 0.5) / total if total > 0 else 0
        avg_conf = (
            sum(s.confidence for s in agent_scores.values() if s.score is not None) /
            max(1, sum(1 for s in agent_scores.values() if s.score is not None))
        )
        reliability_score = round(success_ratio * 60 + avg_conf * 40, 1)

        # F. Improvement Recommendations
        if failed > 0:
            recommendations.append(
                f"Fix {failed} failed agent(s) — they are excluded from scoring. "
                "Check API keys and network connectivity."
            )
        if partial > 0:
            recommendations.append(
                f"{partial} agent(s) ran in partial mode. Add primary data source integrations "
                "(e.g., Finnhub, Alpha Vantage) to improve data quality."
            )
        if invalid_outputs:
            recommendations.append(
                "Some agents produced score=50.0 with very low confidence — "
                "add null-score handling so these don't enter aggregation."
            )
        recommendations.append(
            "Ensure failed agents are excluded from final score weighting (implemented ✓)."
        )
        recommendations.append(
            "Monitor data_source fields on each agent to audit which APIs are actively contributing."
        )

        # Determine final stance
        if active_agents_count < 3:
            stance: Literal["positive", "neutral", "cautious", "insufficient_data"] = "insufficient_data"
        elif final_score >= 61:
            stance = "positive"
        elif final_score >= 41:
            stance = "neutral"
        else:
            stance = "cautious"

        return SystemDebugAudit(
            broken_agents=broken_agents,
            data_gaps=data_gaps,
            invalid_outputs=invalid_outputs,
            aggregation_issues=aggregation_issues,
            reliability_score=reliability_score,
            recommendations=recommendations,
            total_agents=total,
            successful_agents=successful,
            partial_agents=partial,
            failed_agents=failed,
            excluded_from_score=excluded_from_score,
            final_stance=stance,
        )

    def _build_final_decision(
        self,
        agent_scores: Dict[str, AgentScore],
        audit: SystemDebugAudit,
        final_score: float,
        recommendation: str,
    ) -> FinalDecision:
        """Build the production-facing BUY/HOLD/SELL summary."""
        if audit.reliability_score >= 70:
            reliability_label: Literal["Low", "Medium", "High"] = "High"
        elif audit.reliability_score >= 40:
            reliability_label = "Medium"
        else:
            reliability_label = "Low"

        positive_drivers: List[str] = []
        negative_drivers: List[str] = []
        missing_signals: List[str] = []

        for name, score in agent_scores.items():
            if score.status == "failed" or score.score is None:
                missing_signals.append(name)
                continue

            if score.signals:
                positive_drivers.extend(score.signals[:2])
            elif score.score >= 65:
                positive_drivers.append(f"{name} contributed a constructive score of {score.score:.1f}.")

            if score.risks:
                negative_drivers.extend(score.risks[:2])
            elif score.score <= 40:
                negative_drivers.append(f"{name} flagged pressure with a score of {score.score:.1f}.")

        positive_drivers = positive_drivers[:3]
        negative_drivers = negative_drivers[:3]
        missing_signals = list(dict.fromkeys(missing_signals + audit.excluded_from_score))[:5]

        reason_parts = [
            f"{recommendation} with a {final_score:.1f}/100 score",
            f"{reliability_label.lower()} reliability ({audit.reliability_score:.0f}/100)",
        ]
        if positive_drivers:
            reason_parts.append(f"main support: {positive_drivers[0]}")
        if negative_drivers:
            reason_parts.append(f"main concern: {negative_drivers[0]}")

        return FinalDecision(
            verdict=recommendation,
            score=final_score,
            reliability=audit.reliability_score,
            reliability_label=reliability_label,
            reason="; ".join(reason_parts) + ".",
            positive_drivers=positive_drivers,
            negative_drivers=negative_drivers,
            missing_signals=missing_signals,
        )

    # ──────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────

    def _create_failed_score(self, agent_name: str, error: str) -> AgentScore:
        """Create a properly-formed failed AgentScore (score=None, status='failed')."""
        return AgentScore(
            agent_name=agent_name,
            status="failed",
            score=None,
            confidence=0.0,
            factors={},
            metrics={"error": error},
            visualizations=[],
            explanation=f"Agent failed: {error}",
            signals=[],
            risks=[],
            warnings=[f"Agent '{agent_name}' failed and was excluded from final score: {error}"],
        )

    async def _get_company_name(self, ticker: str) -> str:
        """Get company name for the ticker."""
        try:
            from services.finnhub_service import finnhub_service
            if finnhub_service.is_available():
                profile = finnhub_service.get_company_profile(ticker)
                if profile and 'name' in profile:
                    return profile['name']
        except Exception:
            pass
        return ticker

    def _generate_simple_explanation(
        self,
        fundamental: AgentScore,
        technical: AgentScore,
        sentiment: AgentScore,
        final_score: float,
        recommendation: str
    ) -> str:
        """Generate simple explanation of the analysis."""
        parts = [f"**Recommendation: {recommendation}** (Score: {final_score:.1f}/100)", ""]
        parts.append("**Analysis Summary:**")

        def fmt(s: AgentScore) -> str:
            if s.score is None:
                return f"N/A ({s.status})"
            return f"{s.score:.1f}/100"

        parts.append(f"- Fundamental: {fmt(fundamental)} - {fundamental.explanation or 'No explanation'}")
        parts.append(f"- Technical: {fmt(technical)} - {technical.explanation or 'No explanation'}")
        parts.append(f"- Sentiment: {fmt(sentiment)} - {sentiment.explanation or 'No explanation'}")
        parts.append("")

        if recommendation == "BUY":
            parts.append("Favorable conditions indicated by active agents.")
        elif recommendation == "HOLD":
            parts.append("Mixed signals. Monitor for clearer trends.")
        else:
            parts.append("Caution indicated — weakness across active agents.")

        return "\n".join(parts)


# Global orchestrator instance
orchestrator = Orchestrator()
