from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from db.database import get_db
from db.models import PortfolioItem, AnalysisHistory
from models.schemas import PortfolioItemCreate, PortfolioItemResponse
from db.cache import cache_service
from services.price_service import price_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("/", response_model=List[PortfolioItemResponse])
def get_portfolio(db: Session = Depends(get_db)):
    """Get all items in the user's portfolio, with cached analysis if available."""
    items = db.query(PortfolioItem).all()
    
    response_items = []
    for item in items:
        resp = PortfolioItemResponse.model_validate(item)
        
        # Try to get the latest cached analysis for this ticker
        # Specifically targeting 1y/balanced which is the default in the UI
        cache_key = f"analysis:{item.ticker}:1y:balanced"
        cached_analysis = cache_service.get(cache_key)
        
        if cached_analysis:
            resp.latest_analysis = cached_analysis
        else:
            # Fallback to checking the database if it's not in cache
            db_history = db.query(AnalysisHistory).filter(AnalysisHistory.ticker == item.ticker).order_by(AnalysisHistory.analysis_date.desc()).first()
            if db_history:
                # Reconstruct a partial dict of what the UI needs from the DB record
                resp.latest_analysis = {
                    "final_score": db_history.final_score,
                    "recommendation": db_history.recommendation,
                    "confidence": db_history.confidence,
                    "company_name": db_history.company_name
                }
                
        response_items.append(resp)
        
    return response_items

@router.post("/", response_model=PortfolioItemResponse)
def add_portfolio_item(item: PortfolioItemCreate, db: Session = Depends(get_db)):
    """Add a new stock to the portfolio."""
    # Check if already exists
    existing = db.query(PortfolioItem).filter(PortfolioItem.ticker == item.ticker.upper()).first()
    if existing:
        existing.shares += item.shares
        # Simple moving average for price might be more complex, but we'll do simple override here for brevity
        if item.avg_price > 0:
            existing.avg_price = item.avg_price
        db.commit()
        db.refresh(existing)
        return existing
        
    db_item = PortfolioItem(
        ticker=item.ticker.upper(),
        shares=item.shares,
        avg_price=item.avg_price
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.delete("/{ticker}")
def remove_portfolio_item(ticker: str, db: Session = Depends(get_db)):
    """Remove a stock from the portfolio."""
    item = db.query(PortfolioItem).filter(PortfolioItem.ticker == ticker.upper()).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in portfolio")
    
    db.delete(item)
    db.commit()
    return {"message": f"Successfully removed {ticker} from portfolio"}


@router.get("/prices", response_model=Dict[str, Any])
def get_portfolio_prices(db: Session = Depends(get_db)):
    """
    Get live stock prices for all tickers in the portfolio.
    Returns price, change%, currency, P&L per holding.
    """
    items = db.query(PortfolioItem).all()
    if not items:
        return {"prices": {}, "total_value": 0, "total_cost": 0, "total_gain_loss": 0}

    tickers = [item.ticker for item in items]
    live_prices = price_service.get_batch_prices(tickers)

    prices_out = {}
    total_value = 0.0
    total_cost = 0.0

    for item in items:
        ticker = item.ticker.upper()
        price_data = live_prices.get(ticker)
        
        if price_data:
            current_price = price_data["price"]
            cost_basis = float(item.avg_price or 0) * float(item.shares or 0)
            current_value = current_price * float(item.shares or 0)
            gain_loss = current_value - cost_basis
            gain_loss_pct = ((current_value - cost_basis) / cost_basis * 100) if cost_basis > 0 else 0

            total_value += current_value
            total_cost += cost_basis

            prices_out[ticker] = {
                **price_data,
                "shares": float(item.shares or 0),
                "avg_price": float(item.avg_price or 0),
                "cost_basis": round(cost_basis, 2),
                "current_value": round(current_value, 2),
                "gain_loss": round(gain_loss, 2),
                "gain_loss_pct": round(gain_loss_pct, 2),
            }
        else:
            prices_out[ticker] = {
                "ticker": ticker,
                "price": None,
                "shares": float(item.shares or 0),
                "avg_price": float(item.avg_price or 0),
                "error": "Price unavailable",
            }

    total_gain_loss = total_value - total_cost
    total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0

    return {
        "prices": prices_out,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_gain_loss": round(total_gain_loss, 2),
        "total_gain_loss_pct": round(total_gain_loss_pct, 2),
    }

