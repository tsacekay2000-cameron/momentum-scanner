"""Test news fetching directly"""
import yfinance as yf
from datetime import datetime, timedelta

test_tickers = ['AAPL', 'TSLA', 'NVDA']

for ticker in test_tickers:
    print(f"\n{'='*60}")
    print(f"Testing {ticker}")
    print('='*60)
    
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        
        print(f"News type: {type(news)}")
        print(f"News count: {len(news) if news else 0}")
        
        if news and len(news) > 0:
            item = news[0]
            content = item.get('content', {})
            
            if content:
                pub_date = content.get('pubDate')
                print(f"Has content: Yes")
                print(f"Has pubDate: {pub_date is not None}")
                
                if pub_date:
                    news_time = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    news_time_naive = news_time.replace(tzinfo=None)
                    age = datetime.now() - news_time_naive
                    print(f"Age: {age.days} days")
                    print(f"Within 7 days: {age <= timedelta(days=7)}")
                    
                    provider = content.get('provider', {})
                    click_url = content.get('clickThroughUrl', {})
                    
                    print(f"Title: {content.get('title', 'No title')[:50]}")
                    print(f"Publisher: {provider.get('displayName', 'Unknown')}")
                    print(f"Link: {click_url.get('url', '#')[:50]}")
            else:
                print("No content in item")
        else:
            print("No news items")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
