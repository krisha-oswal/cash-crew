from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from datetime import datetime
from db.database import Base

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    timeframe = Column(String)
    risk_preference = Column(String)
    
    # Final Report Data
    company_name = Column(String, nullable=True)
    analysis_date = Column(DateTime, default=datetime.utcnow)
    final_score = Column(Float)
    recommendation = Column(String)
    confidence = Column(Float)
    
    # Store Agent Scores as JSON
    fundamental_score = Column(JSON)
    technical_score = Column(JSON)
    sentiment_score = Column(JSON)
    governance_score = Column(JSON)
    pead_score = Column(JSON)
    financial_health_score = Column(JSON)
    risk_score = Column(JSON)
    macro_score = Column(JSON, nullable=True)
    insider_score = Column(JSON, nullable=True)
    
    # XAI
    xai_explanation = Column(String)
    xai_visualizations = Column(JSON)
    
    # Metrics
    latency_seconds = Column(Float)
    
    def __repr__(self):
        return f"<AnalysisHistory(ticker='{self.ticker}', date='{self.analysis_date}', recommendation='{self.recommendation}')>"

class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, unique=True)
    shares = Column(Float, default=0.0)
    avg_price = Column(Float, default=0.0)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<PortfolioItem(ticker='{self.ticker}', shares={self.shares})>"

