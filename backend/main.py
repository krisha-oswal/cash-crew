"""
FastAPI main application entry point.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
import logging
import redis

from config.settings import settings
from models.schemas import AnalysisRequest, FinalReport, SystemMetrics
from services.llm_service import llm_router, LLMProvider
from services.groq_service import groq_llama3_70b, groq_mixtral
from services.gemini_service import gemini_1_5_pro
from services.huggingface_service import huggingface_mixtral
from services.ollama_service import ollama_llama3, ollama_mixtral, ollama_mistral
from db.database import engine, Base
import db.models
from routers import portfolio_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    configured = [
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ]
    origins = [settings.frontend_url, "http://localhost:3000", *configured]
    return list(dict.fromkeys(origins))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Cash Crew API...")
    logger.info(f"Demo Mode: {settings.demo_mode}")
    
    # Initialize DB schema
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized.")
    
    # Register LLM providers
    logger.info("Registering LLM providers...")
    llm_router.register_provider(LLMProvider.GROQ_LLAMA3_70B, groq_llama3_70b)
    llm_router.register_provider(LLMProvider.GROQ_MIXTRAL, groq_mixtral)
    llm_router.register_provider(LLMProvider.GEMINI_1_5_PRO, gemini_1_5_pro)
    llm_router.register_provider(LLMProvider.HUGGINGFACE_MIXTRAL, huggingface_mixtral)
    llm_router.register_provider(LLMProvider.OLLAMA_LLAMA3, ollama_llama3)
    llm_router.register_provider(LLMProvider.OLLAMA_MIXTRAL, ollama_mixtral)
    llm_router.register_provider(LLMProvider.OLLAMA_MISTRAL, ollama_mistral)
    
    logger.info("Cash Crew API started successfully!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Cash Crew API...")


# Create FastAPI app
app = FastAPI(
    title="Cash Crew API",
    description="Multi-Agent AI Equity Research System",
    version="1.0.0",
    lifespan=lifespan
)

# Setup Rate Limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(portfolio_router.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Cash Crew API - Multi-Agent Equity Research System",
        "version": "1.0.0",
        "demo_mode": settings.demo_mode,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/ready")
async def readiness_check():
    """Readiness check for database and Redis dependencies."""
    db_ready = False
    redis_ready = False

    try:
        with engine.connect():
            db_ready = True
    except Exception as e:
        logger.warning(f"Readiness database check failed: {e}")

    try:
        redis.Redis.from_url(settings.redis_url, decode_responses=True).ping()
        redis_ready = True
    except Exception as e:
        logger.warning(f"Readiness Redis check failed: {e}")

    status = "ready" if db_ready and redis_ready else "degraded"
    return {
        "status": status,
        "demo_mode": settings.demo_mode,
        "database": "ok" if db_ready else "unavailable",
        "redis": "ok" if redis_ready else "unavailable",
        "llm_providers": {
            provider.value: service.is_available()
            for provider, service in llm_router.providers.items()
        }
    }


@app.post("/analyze", response_model=FinalReport)
@limiter.limit("5/minute")
async def analyze_stock(payload: AnalysisRequest, request: Request):
    """
    Analyze a stock and generate comprehensive equity research report.
    
    This endpoint orchestrates all AI agents to perform:
    - Fundamental analysis (financial ratios, metrics)
    - Technical analysis (indicators, price patterns)
    - Sentiment analysis (news, social media)
    - Risk assessment and final recommendation
    
    Returns a complete report with BUY/HOLD/SELL recommendation.
    """
    logger.info(f"Received analysis request for {payload.ticker}")
    
    try:
        # Import orchestrator
        from orchestrator import orchestrator
        from db.cache import cache_service
        from db.database import SessionLocal
        from db.models import AnalysisHistory
        
        # Check cache
        cache_key = f"analysis:{payload.ticker}:{payload.timeframe}:{payload.risk_preference}"
        cached_data = cache_service.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached analysis for {payload.ticker}")
            return FinalReport(**cached_data)
        
        # Run analysis
        report = await orchestrator.analyze(payload)
        
        # Save to cache
        cache_service.set(cache_key, report.model_dump(mode='json'), expire_seconds=3600)
        
        # Save to database
        try:
            db = SessionLocal()
            history = AnalysisHistory(
                ticker=report.ticker,
                timeframe=payload.timeframe,
                risk_preference=payload.risk_preference,
                company_name=report.company_name,
                analysis_date=report.analysis_date,
                final_score=report.final_score,
                recommendation=report.recommendation,
                confidence=report.confidence,
                fundamental_score=report.fundamental_score.model_dump(mode='json'),
                technical_score=report.technical_score.model_dump(mode='json'),
                sentiment_score=report.sentiment_score.model_dump(mode='json'),
                governance_score=report.governance_score.model_dump(mode='json'),
                pead_score=report.pead_score.model_dump(mode='json'),
                financial_health_score=report.financial_health_score.model_dump(mode='json'),
                risk_score=report.risk_score.model_dump(mode='json'),
                xai_explanation=report.xai_explanation,
                xai_visualizations=[v.model_dump(mode='json') for v in report.xai_visualizations],
                latency_seconds=report.latency_seconds
            )
            db.add(history)
            db.commit()
            db.close()
        except Exception as db_err:
            logger.error(f"Failed to save analysis to database: {db_err}")
            
        logger.info(f"Analysis complete for {payload.ticker}: {report.recommendation}")
        return report
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics", response_model=SystemMetrics)
async def get_system_metrics():
    """Get system-wide performance metrics."""
    llm_stats = llm_router.get_stats()
    
    # Calculate aggregate metrics
    total_requests = sum(stats["requests"] for stats in llm_stats.values())
    total_successes = sum(stats["successes"] for stats in llm_stats.values())
    total_failures = sum(stats["failures"] for stats in llm_stats.values())
    
    error_rate = total_failures / total_requests if total_requests > 0 else 0
    
    return SystemMetrics(
        overall_accuracy=None,  # TODO: Implement accuracy tracking
        average_latency=0.0,  # TODO: Implement latency tracking
        confidence_weighted_reliability=0.0,  # TODO: Implement
        data_freshness_hours=0.0,  # TODO: Implement
        error_rate=error_rate,
        backtesting_success_rate=None,  # TODO: Implement
        conflict_rate=0.0,  # TODO: Implement
        total_analyses=0  # TODO: Implement
    )


@app.get("/llm-stats")
async def get_llm_stats():
    """Get LLM provider usage statistics."""
    return llm_router.get_stats()


@app.post("/report/text")
@limiter.limit("5/minute")
async def generate_text_report(payload: AnalysisRequest, request: Request):
    """
    Generate and download text report for a stock analysis.
    
    Returns a formatted text report that can be saved as .txt file.
    """
    logger.info(f"Generating text report for {payload.ticker}")
    
    try:
        from orchestrator import orchestrator
        from agents.report_writer import report_writer
        from db.cache import cache_service
        from models.schemas import FinalReport
        
        # Check cache
        cache_key = f"analysis:{payload.ticker}:{payload.timeframe}:{payload.risk_preference}"
        cached_data = cache_service.get(cache_key)
        if cached_data:
            logger.info(f"Using cached analysis for text report format of {payload.ticker}")
            report = FinalReport(**cached_data)
        else:
            # Run analysis
            report = await orchestrator.analyze(payload)
        
        # Generate text report
        text_report = report_writer.generate_text_report(report)
        
        # Return as plain text
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=text_report,
            headers={
                "Content-Disposition": f"attachment; filename={payload.ticker}_report.txt"
            }
        )
        
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report/pdf")
@limiter.limit("5/minute")
async def generate_pdf_report(payload: AnalysisRequest, request: Request):
    """
    Generate and download PDF report for a stock analysis.
    
    Returns a professionally formatted PDF report.
    """
    logger.info(f"Generating PDF report for {payload.ticker}")
    
    try:
        from orchestrator import orchestrator
        from utils.pdf_generator import pdf_generator
        from db.cache import cache_service
        from models.schemas import FinalReport
        import tempfile
        import os
        
        # Check cache
        cache_key = f"analysis:{payload.ticker}:{payload.timeframe}:{payload.risk_preference}"
        cached_data = cache_service.get(cache_key)
        if cached_data:
            logger.info(f"Using cached analysis for PDF generation of {payload.ticker}")
            report = FinalReport(**cached_data)
        else:
            # Run analysis
            report = await orchestrator.analyze(payload)
        
        # Generate PDF in temp directory
        temp_dir = tempfile.gettempdir()
        pdf_path = os.path.join(temp_dir, f"{payload.ticker}_report.pdf")
        pdf_generator.generate_pdf(report, pdf_path)
        
        # Return PDF file
        from fastapi.responses import FileResponse
        return FileResponse(
            path=pdf_path,
            filename=f"{payload.ticker}_report.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
