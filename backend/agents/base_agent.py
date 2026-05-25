"""
Abstract base class for all analysis agents.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
import logging

from models.schemas import AgentScore, VisualizationData

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all analysis agents."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"agent.{agent_name}")

    @property
    def name(self) -> str:
        """Alias for agent_name — prevents AttributeError in subclasses that use self.name."""
        return self.agent_name

    @abstractmethod
    async def analyze(self, ticker: str, **kwargs) -> AgentScore:
        """
        Perform analysis and return score.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters (timeframe, region, etc.)

        Returns:
            AgentScore with status, score (or None), confidence, signals, risks, warnings
        """
        pass

    def create_score(
        self,
        score: Optional[float],
        confidence: float,
        factors: Dict[str, float],
        metrics: Dict[str, Any],
        visualizations: List[VisualizationData],
        explanation: Optional[str] = None,
        status: Literal["success", "partial", "failed"] = "success",
        signals: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        data_source: Optional[str] = None,
    ) -> AgentScore:
        """
        Helper method to create AgentScore object.

        Args:
            score: Score from 0-100, or None for fully failed agents
            confidence: Confidence level 0-1
            factors: Factor contributions to the score
            metrics: Agent-specific metrics
            visualizations: List of visualization data
            explanation: Optional explanation text
            status: "success" | "partial" | "failed"
            signals: Bullish/bearish signals observed
            risks: Key risks identified
            warnings: Data quality or reliability warnings
            data_source: Primary data source used

        Returns:
            AgentScore object
        """
        # Clamp score only if it's not None
        clamped_score = None
        if score is not None:
            clamped_score = max(0.0, min(100.0, float(score)))

        return AgentScore(
            agent_name=self.agent_name,
            status=status,
            score=clamped_score,
            confidence=max(0.0, min(1.0, confidence)),
            factors=factors,
            metrics=metrics,
            visualizations=visualizations,
            explanation=explanation,
            timestamp=datetime.utcnow(),
            signals=signals or [],
            risks=risks or [],
            warnings=warnings or [],
            data_source=data_source,
        )

    def create_failed_score(
        self,
        reason: str,
        warnings: Optional[List[str]] = None,
    ) -> AgentScore:
        """
        Shortcut to create a properly-formed failed agent score.
        score=None, status="failed", confidence=0.0
        Does NOT emit a fake score of 50.
        """
        return AgentScore(
            agent_name=self.agent_name,
            status="failed",
            score=None,
            confidence=0.0,
            factors={},
            metrics={"error": reason},
            visualizations=[],
            explanation=f"Agent failed: {reason}",
            timestamp=datetime.utcnow(),
            signals=[],
            risks=[],
            warnings=warnings or [f"Agent failed: {reason}"],
            data_source=None,
        )

    def create_visualization(
        self,
        chart_type: str,
        title: str,
        data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> VisualizationData:
        """
        Helper method to create visualization data.

        Args:
            chart_type: Type of chart (bar, line, pie, spider, heatmap, waterfall)
            title: Chart title
            data: Chart data
            config: Optional chart configuration

        Returns:
            VisualizationData object
        """
        return VisualizationData(
            chart_type=chart_type,
            title=title,
            data=data,
            config=config or {}
        )

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get agent-specific performance metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "agent_name": self.agent_name,
            "last_run": datetime.utcnow().isoformat()
        }

    def log_info(self, message: str):
        """Log info message."""
        self.logger.info(f"[{self.agent_name}] {message}")

    def log_error(self, message: str):
        """Log error message."""
        self.logger.error(f"[{self.agent_name}] {message}")

    def log_warning(self, message: str):
        """Log warning message."""
        self.logger.warning(f"[{self.agent_name}] {message}")
