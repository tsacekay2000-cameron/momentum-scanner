"""Test script to check yfinance news functionality"""
import yfinance as yf
from datetime import datetime, timedelta

# Test with a few common tickers
test_tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'AMZN']

print("Testing yfinance news functionality...\n")

for ticker in test_tickers:
    print(f"\n{'='*60}")
    print(f"Testing {ticker}:")
    print('='*60)
    
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        
        print(f"News type: {type(news)}")
        print(f"News count: {len(news) if news else 0}")
        
        if news:
            print(f"\nFirst news item:")
            item = news[0]
            print(f"  Keys: {item.keys()}")
            
            # Check if content has nested structure
            if 'content' in item:
                content = item['content']
                print(f"  Content type: {type(content)}")
                if isinstance(content, dict):
                    print(f"  Content keys: {content.keys()}")
                    print(f"  Title: {content.get('title', 'N/A')}")
                    print(f"  Publisher: {content.get('publisher', 'N/A')}")
                    
                    # Try different timestamp keys
                    timestamp = content.get('providerPublishTime') or content.get('pubDate') or content.get('published')
                    print(f"  Timestamp: {timestamp}")
                    
                    if timestamp:
                        news_time = datetime.fromtimestamp(timestamp) if isinstance(timestamp, (int, float)) else datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
                        print(f"  Date: {news_time}")
                        print(f"  Age: {(datetime.now() - news_time.replace(tzinfo=None)).days} days ago")
            
            print(f"  Raw item: {item}")
        else:
            print("  No news found")
            
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*60)
print("Test complete")
