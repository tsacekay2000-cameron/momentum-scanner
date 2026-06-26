"""
Web-based Momentum Scanner with Dark Theme and Grid Layout
"""
from flask import Flask, render_template, jsonify
import time
from momentum_scanner import (
    run_scan, get_universe, MIN_PRICE, MAX_PRICE, MIN_PCT_CHANGE, 
    MIN_RVOL, MAX_FLOAT
)
from threading import Thread, Lock

app = Flask(__name__)

# Global state
scanner_data = {
    'stocks': [],
    'last_update': None,
    'is_scanning': False
}
data_lock = Lock()

def scan_stocks():
    """Background scanner that updates data"""
    while True:
        try:
            with data_lock:
                scanner_data['is_scanning'] = True
            
            print(f"\n{'='*50}")
            print(f"Starting scan at {time.strftime('%H:%M:%S')}")
            print(f"{'='*50}")
            
            # Use the new run_scan() function which handles Finviz hybrid mode
            scan_results = run_scan()
            
            # Convert to web format
            results = []
            for item in scan_results:
                ticker = item['ticker']
                kpis = item['kpis']
                score = item['score']
                
                results.append({
                    'ticker': ticker,
                    'score': round(score, 1),
                    'price': round(kpis['price'], 2),
                    'pct_change': round(kpis['pct_change'], 2),
                    'rvol': round(kpis['relative_volume'], 2),
                    'float': round(kpis['float_shares'] / 1_000_000, 1),
                    'volume': kpis['volume'],
                    'avg_volume_20d': kpis['avg_volume_20d'],
                    'dollar_volume': round(kpis['dollar_volume'], 2),
                    'sma_50_delta': round(kpis.get('sma_50_delta', 0), 2),
                    'above_vwap': kpis['above_vwap'],
                    'has_news': kpis['has_news'],
                    'passes_filter': True,  # Already filtered by run_scan()
                    'halt_risk': kpis['halt_risk'],
                    'top_gainer': False  # Can add this back if needed
                })

            print(f"Scan complete: {len(results)} stocks qualified")
            print(f"DEBUG: results list has {len(results)} items")
            print(f"DEBUG: First few tickers: {[r['ticker'] for r in results[:3]]}")
            print(f"{'='*50}\n")
            
            with data_lock:
                scanner_data['stocks'] = results
                scanner_data['last_update'] = time.strftime('%Y-%m-%d %H:%M:%S')
                scanner_data['is_scanning'] = False
                print(f"DEBUG: Stored {len(scanner_data['stocks'])} stocks in scanner_data")
            
        except Exception as e:
            print(f"Scanner error: {e}")
            import traceback
            traceback.print_exc()
            with data_lock:
                scanner_data['is_scanning'] = False
        
        # Scan every 15 minutes
        print(f"Sleeping for 15 minutes...")
        time.sleep(900)

@app.route('/')
def index():
    import time
    return render_template('index.html', 
                         min_price=MIN_PRICE,
                         max_price=MAX_PRICE,
                         min_pct_change=MIN_PCT_CHANGE,
                         min_rvol=MIN_RVOL,
                         max_float=MAX_FLOAT/1_000_000,
                         cache_bust=int(time.time()))

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/test_simple')
def test_simple():
    return render_template('test_simple.html')

@app.route('/api/stocks')
def get_stocks():
    print(f"[API] /api/stocks called at {time.strftime('%H:%M:%S')}")
    with data_lock:
        data = {
            'stocks': scanner_data.get('stocks', []),
            'last_update': scanner_data.get('last_update'),
            'is_scanning': scanner_data.get('is_scanning', False)
        }
        print(f"[API] Returning {len(data['stocks'])} stocks, last_update={data['last_update']}, is_scanning={data['is_scanning']}")
        return jsonify(data)

@app.route('/api/news')
def get_news():
    """Get news for scanner universe + popular stocks"""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        
        # Start with scanner universe
        tickers = set(get_universe())
        
        # Add top 50 most popular stocks
        popular_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK.B', 'V', 'JNJ',
            'WMT', 'JPM', 'MA', 'PG', 'UNH', 'HD', 'DIS', 'BAC', 'ADBE', 'CRM',
            'NFLX', 'CSCO', 'PFE', 'TMO', 'MRK', 'ABBV', 'KO', 'AVGO', 'PEP', 'COST',
            'CVX', 'MCD', 'ABT', 'WFC', 'DHR', 'ACN', 'LLY', 'NKE', 'NEE', 'TXN',
            'AMD', 'QCOM', 'UPS', 'PM', 'RTX', 'HON', 'ORCL', 'INTC', 'IBM', 'AMGN'
        ]
        tickers.update(popular_stocks)
        
        print(f"Fetching news for {len(tickers)} stocks...")
        all_news = []
        rate_limited = False
        
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                news = stock.news
                
                if news:
                    for item in news[:3]:  # Get top 3 news per stock (reduced from 5 since more stocks)
                        # yfinance changed structure - news is now nested in 'content'
                        content = item.get('content', {})
                        if not content:
                            continue
                            
                        # Get timestamp from pubDate (ISO string format)
                        pub_date = content.get('pubDate')
                        if not pub_date:
                            continue
                            
                        # Parse ISO date string (e.g., "2026-01-16T14:17:50Z")
                        news_time = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        # Remove timezone info for comparison
                        news_time_naive = news_time.replace(tzinfo=None)
                        
                        # Check if news is within last 7 days
                        if datetime.now() - news_time_naive <= timedelta(days=7):
                            provider = content.get('provider', {})
                            click_url = content.get('clickThroughUrl', {})
                            
                            all_news.append({
                                'ticker': ticker,
                                'title': content.get('title', 'No title'),
                                'publisher': provider.get('displayName', 'Unknown'),
                                'link': click_url.get('url', '#'),
                                'timestamp': news_time_naive.strftime('%Y-%m-%d %H:%M'),
                                'ago': format_time_ago(news_time_naive)
                            })
            except Exception as e:
                # Check for rate limiting
                if 'Rate limit' in str(e) or 'Too Many Requests' in str(e):
                    print(f"Rate limited by Yahoo Finance. Try again in 15-30 minutes.")
                    rate_limited = True
                    break
                # Silent fail for individual stocks to keep moving
                continue
        
        # Sort by timestamp, newest first
        all_news.sort(key=lambda x: x['timestamp'], reverse=True)
        
        response = {'news': all_news[:50]}
        if rate_limited:
            response['warning'] = 'Rate limited by Yahoo Finance. Showing cached/partial results. Try again in 15-30 minutes.'
        
        return jsonify(response)
    except Exception as e:
        print(f"Error in news endpoint: {e}")
        return jsonify({'news': [], 'error': str(e)})

def format_time_ago(news_time):
    """Format time difference in human-readable format"""
    from datetime import datetime
    diff = datetime.now() - news_time
    
    if diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds >= 3600:
        return f"{diff.seconds // 3600}h ago"
    elif diff.seconds >= 60:
        return f"{diff.seconds // 60}m ago"
    else:
        return "Just now"

if __name__ == '__main__':
    # Start background scanner
    scanner_thread = Thread(target=scan_stocks, daemon=True)
    scanner_thread.start()
    
    print("=" * 80)
    print("Momentum Scanner Web Interface Starting...")
    print("Open your browser to: http://localhost:5000")
    print("=" * 80)
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
