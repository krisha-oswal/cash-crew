import yfinance as yf
ticker = yf.Ticker("AAPL")
news = ticker.news
print(f"Got {len(news)} news items")
if news:
    print(news[0].keys())
    print(news[0].get('title'))
