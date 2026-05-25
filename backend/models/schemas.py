"""
Pydantic models for request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class AnalysisRequest(BaseModel):
    """Request model for equity analysis."""
    ticker: str = Field(..., description="Stock ticker symbol (e.g., TCS.NS, AAPL)")
    sector: Optional[str] = Field(None, description="Sector/Industry")
    timeframe: Optional[str] = Field("1y", description="Timeframe for analysis (1m, 3m, 6m, 1y, 5y)")
    region: Optional[Literal["US", "India"]] = Field(None, description="Region-specific rules")
    risk_preference: Optional[Literal["risk-averse", "balanced", "aggressive"]] = Field(
        "balanced",
        description="User risk preference"
    )


class VisualizationData(BaseModel):
    """Visualization data for charts."""
    chart_type: Literal["bar", "line", "pie", "spider", "heatmap", "waterfall"]
    title: str
    data: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None


class AgentScore(BaseModel):
    """Score output from an individual agent."""
    agent_name: str

    # --- Status (REQUIRED) ---
    # "success"  → agent ran fully with real data
    # "partial"  → agent ran but data was incomplete / using proxies
    # "failed"   → agent crashed or returned no usable data
    status: Literal["success", "partial", "failed"] = "success"

    # score is Optional so that failed agents can return None instead of a fake 50
    score: Optional[float] = Field(None, ge=0, le=100, description="Score from 0-100, or null if failed")
    confidence: float = Field(0.0, ge=0, le=1, description="Confidence level 0-1")

    factors: Dict[str, float] = Field(default_factory=dict, description="Factor contributions")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Agent-specific metrics")
    visualizations: List[VisualizationData] = Field(default_factory=list)
    explanation: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # --- Structured output fields (per spec) ---
    signals: List[str] = Field(default_factory=list, description="Key bullish/bearish signals observed")
    risks: List[str] = Field(default_factory=list, description="Key risks identified")
    warnings: List[str] = Field(default_factory=list, description="Data quality or reliability warnings")

    # Data source transparency
    data_source: Optional[str] = Field(None, description="Primary data source used (e.g., 'Finnhub', 'yfinance', 'simulated')")


class FundamentalMetrics(BaseModel):
    """Fundamental analysis metrics."""
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_to_equity: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    fcf_yield: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None


class TechnicalIndicators(BaseModel):
    """Technical analysis indicators."""
    ma_50: Optional[float] = None
    ma_200: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None


class SentimentMetrics(BaseModel):
    """Sentiment analysis metrics."""
    overall_sentiment: float = Field(..., ge=-1, le=1)
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    sources: List[str] = Field(default_factory=list)
    top_articles: List[Dict[str, str]] = Field(default_factory=list)


class GovernanceMetrics(BaseModel):
    """Corporate governance metrics."""
    company_name: str = ""
    country: str = ""
    exchange: str = ""
    recent_news_count: int = 0
    legal_issues: List[Dict[str, Any]] = []


class PEADMetrics(BaseModel):
    """Post-Earnings Announcement Drift metrics."""
    last_eps_actual: Optional[float] = None
    last_eps_estimate: Optional[float] = None
    last_surprise_percent: Optional[float] = None
    consecutive_beats: int = 0
    consecutive_misses: int = 0
    avg_surprise_4q: Optional[float] = None


class RAGMetrics(BaseModel):
    """RAG Filing metrics."""
    filing_type: str = ""
    filing_date: Optional[str] = None
    key_findings: List[str] = []
    risk_factors_count: int = 0
    financial_health_indicators: Dict[str, Any] = {}


class FinancialHealthMetrics(BaseModel):
    """Financial health metrics from RAG filing analysis."""
    profitability_score: float = Field(..., ge=0, le=100)
    leverage_score: float = Field(..., ge=0, le=100)
    efficiency_score: float = Field(..., ge=0, le=100)
    key_insights: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# SYSTEM DEBUG AUDIT MODEL
# ──────────────────────────────────────────────

class BrokenAgentInfo(BaseModel):
    """Info about a broken/failed agent."""
    agent_name: str
    status: Literal["failed", "partial"]
    reason: str


class DataGap(BaseModel):
    """A specific data gap identified in the system."""
    category: str       # e.g. "earnings_data", "financial_metrics"
    description: str
    affected_agents: List[str]
    severity: Literal["high", "medium", "low"]


class AggregationIssue(BaseModel):
    """Issue with how scores were aggregated."""
    issue_type: str
    description: str
    recommendation: str


class SystemDebugAudit(BaseModel):
    """
    Full debug audit of the multi-agent system.
    Generated automatically after every analysis run.
    """
    # A. Broken Agents
    broken_agents: List[BrokenAgentInfo] = Field(default_factory=list)

    # B. Data Gaps
    data_gaps: List[DataGap] = Field(default_factory=list)

    # C. Invalid / Misleading Outputs
    invalid_outputs: List[str] = Field(default_factory=list,
        description="List of specific invalid or misleading output flags")

    # D. Aggregation Issues
    aggregation_issues: List[AggregationIssue] = Field(default_factory=list)

    # E. Reliability Score
    reliability_score: float = Field(..., ge=0, le=100,
        description="0-100 overall system reliability for this run")

    # F. Improvement Recommendations
    recommendations: List[str] = Field(default_factory=list)

    # Summary numbers
    total_agents: int = 0
    successful_agents: int = 0
    partial_agents: int = 0
    failed_agents: int = 0

    # Which agents were excluded from final score
    excluded_from_score: List[str] = Field(default_factory=list,
        description="Agents excluded from final score due to failed/null status")

    final_stance: Literal["positive", "neutral", "cautious", "insufficient_data"] = "insufficient_data"
    audit_timestamp: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────

class FinalDecision(BaseModel):
    """User-facing decision summary from the final decision engine."""
    verdict: Literal["BUY", "HOLD", "SELL"]
    score: float = Field(..., ge=0, le=100)
    reliability: float = Field(..., ge=0, le=100)
    reliability_label: Literal["Low", "Medium", "High"]
    reason: str
    positive_drivers: List[str] = Field(default_factory=list)
    negative_drivers: List[str] = Field(default_factory=list)
    missing_signals: List[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    """Complete equity research report."""
    ticker: str
    company_name: Optional[str] = None
    analysis_date: datetime = Field(default_factory=datetime.utcnow)

    # Agent Scores
    fundamental_score: AgentScore
    technical_score: AgentScore
    sentiment_score: AgentScore
    governance_score: AgentScore
    pead_score: AgentScore
    financial_health_score: AgentScore
    risk_score: AgentScore
    macro_score: Optional[AgentScore] = None
    insider_score: Optional[AgentScore] = None

    # XAI Explanations
    xai_explanation: str
    xai_visualizations: List[VisualizationData] = Field(default_factory=list)

    # Final Recommendation
    final_score: float = Field(..., ge=0, le=100)
    recommendation: Literal["BUY", "HOLD", "SELL"]
    confidence: float = Field(..., ge=0, le=1)
    final_decision: Optional[FinalDecision] = None

    # Debug Audit (always present)
    system_debug_audit: Optional[SystemDebugAudit] = None

    # System Metrics
    latency_seconds: float
    data_freshness_hours: float
    error_count: int = 0

    # Report URLs
    pdf_url: Optional[str] = None
    dashboard_url: Optional[str] = None


class SystemMetrics(BaseModel):
    """System-wide performance metrics."""
    overall_accuracy: Optional[float] = None
    average_latency: float
    confidence_weighted_reliability: float
    data_freshness_hours: float
    error_rate: float
    backtesting_success_rate: Optional[float] = None
    conflict_rate: float
    total_analyses: int


class PortfolioItemBase(BaseModel):
    """Base schema for a portfolio item."""
    ticker: str = Field(..., description="Stock ticker symbol")
    shares: float = Field(0.0, description="Number of shares owned")
    avg_price: float = Field(0.0, description="Average purchase price")


class PortfolioItemCreate(PortfolioItemBase):
    """Schema for adding a new item to the portfolio."""
    pass


class PortfolioItemResponse(PortfolioItemBase):
    """Schema for returning a portfolio item."""
    id: int
    added_at: datetime

    # We can optionally include the latest cached analysis data
    latest_analysis: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
