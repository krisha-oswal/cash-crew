import asyncio
import sys
import os
import yfinance as yf
from datetime import datetime
import tabulate

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import SessionLocal
from db.models import AnalysisHistory

def calculate_accuracy():
    print("Welcome to Cash Crew Backtesting Framework")
    print("Fetching historical analyses from database...")
    
    db = SessionLocal()
    history = db.query(AnalysisHistory).all()
    
    if not history:
        print("No historical analyses found in the database.")
        db.close()
        return

    print(f"Found {len(history)} historical records. Evaluating performance...\n")
    
    results = []
    correct_predictions = 0
    total_evaluated = 0

    for record in history:
        # Get historical price (around the analysis date) and current price
        ticker = record.ticker
        date_str = record.analysis_date.strftime('%Y-%m-%d')
        
        try:
            stock = yf.Ticker(ticker)
            # Fetch price history from analysis date to today
            hist = stock.history(start=date_str)
            
            if hist.empty or len(hist) < 2:
                results.append([ticker, date_str, record.recommendation, "N/A", "N/A", "Insufficient Data"])
                continue
                
            start_price = hist['Close'].iloc[0]
            current_price = hist['Close'].iloc[-1]
            price_change_pct = ((current_price - start_price) / start_price) * 100
            
            # Evaluate Accuracy
            # Assuming BUY is correct if price went up, SELL is correct if price went down
            # HOLD is a bit subjective, we'll say correct if price change is within +/- 5%
            is_correct = False
            rec = record.recommendation.upper()
            
            if rec == "BUY" and price_change_pct > 0:
                is_correct = True
            elif rec == "SELL" and price_change_pct < 0:
                is_correct = True
            elif rec == "HOLD" and abs(price_change_pct) <= 5:
                is_correct = True
                
            if is_correct:
                correct_predictions += 1
            total_evaluated += 1
            
            outcome = "✅ Correct" if is_correct else "❌ Incorrect"
            results.append([
                ticker,
                date_str,
                rec,
                f"${start_price:.2f}",
                f"${current_price:.2f} ({price_change_pct:+.2f}%)",
                outcome
            ])
            
        except Exception as e:
            results.append([ticker, date_str, record.recommendation, "Error", "Error", str(e)])
            
    db.close()
    
    # Print Results
    headers = ["Ticker", "Analysis Date", "Recommendation", "Start Price", "Current Price", "Outcome"]
    print(tabulate.tabulate(results, headers=headers, tablefmt="grid"))
    
    if total_evaluated > 0:
        accuracy = (correct_predictions / total_evaluated) * 100
        print(f"\nOverall System Accuracy: {accuracy:.1f}% ({correct_predictions}/{total_evaluated} correct)")
    else:
        print("\nCould not evaluate any records due to lack of market data.")

if __name__ == "__main__":
    calculate_accuracy()
