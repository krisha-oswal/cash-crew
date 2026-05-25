"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Financial Data APIs
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""
    news_api_key: str = ""

    # LLM APIs
    groq_api_key: str = ""
    google_api_key: str = ""
    huggingface_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Database & Cache
    database_url: str = "postgresql://user:pass@localhost:5432/cashcrew"
    redis_url: str = "redis://localhost:6379"

    # Application Settings
    app_env: Literal["development", "production", "test"] = "development"
    debug: bool = True
    demo_mode: Literal["live", "hybrid", "offline"] = "live"
    enable_caching: bool = True
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    # ──────────────────────────────────────────────────────────────
    # DATA_MODE — Controls how agents behave when APIs are unavailable
    #
    # live     → Use real APIs first. On any failure, fallback gracefully.
    #            System NEVER crashes due to API issues.
    # fallback → Try APIs, tolerate missing data, return partial analysis
    #            with warnings. Status = "partial" if data is incomplete.
    # offline  → Use mock/static data only. All agents marked "partial".
    #            Useful for demo/testing without any API keys.
    # ──────────────────────────────────────────────────────────────
    data_mode: Literal["live", "fallback", "offline"] = "live"

    # Rate Limiting
    rate_limit_per_minute: int = 30

    # Agent Weights for Final Score
    fundamental_weight: float = 0.20
    technical_weight: float = 0.15
    sentiment_weight: float = 0.10
    governance_weight: float = 0.10
    pead_weight: float = 0.10
    financial_health_weight: float = 0.15
    risk_weight: float = 0.10
    macro_weight: float = 0.05
    insider_weight: float = 0.05

    class Config:
        env_file = (".env.local", ".env")
        case_sensitive = False


# Global settings instance
settings = Settings()


# LLM Routing Configuration
LLM_ROUTING = {
    "xai_agent": ["groq_llama3_70b", "ollama_llama3"],
    "rag_filing_agent": ["gemini_1.5_pro", "groq_llama3_70b", "ollama_mixtral"],
    "report_writer": ["groq_mixtral", "ollama_mistral"],
    "sentiment_agent": ["huggingface_mixtral", "ollama_mixtral"]
}


# Score Thresholds
SCORE_THRESHOLDS = {
    "SELL": (0, 40),
    "HOLD": (41, 60),
    "BUY": (61, 100)
}
