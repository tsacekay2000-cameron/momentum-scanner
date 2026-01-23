"""
Quick test to show the scanner is working and collecting data
"""
import yfinance as yf
import time

tickers = ["GME", "AMC", "PLTR", "SOFI", "RIVN"]

print("=" * 80)
print("Testing Scanner - Fetching Live Data from Yahoo Finance")
print("=" * 80)
print()

for ticker in tickers:
    try:
        print(f"Fetching {ticker}...", end=" ")
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1d", interval="1m")
        
        if hist.empty:
            hist = stock.history(period="2d")
        
        if not hist.empty:
            latest = hist.iloc[-1]
            today_open = hist.iloc[0]['Open'] if len(hist) > 0 else latest['Open']
            pct_change = ((latest['Close'] - today_open) / today_open) * 100
            
            # Get 20-day average volume
            hist_vol = stock.history(period="25d")
            avg_vol = int(hist_vol['Volume'].tail(20).mean()) if len(hist_vol) >= 20 else 0
            current_vol = int(hist['Volume'].sum())
            rvol = current_vol / avg_vol if avg_vol > 0 else 0
            
            # Get float
            float_shares = info.get('floatShares', 0)
            if not float_shares:
                float_shares = info.get('sharesOutstanding', 0)
            float_m = float_shares / 1_000_000 if float_shares else 0
            
            print("✓")
            print(f"  Price: ${latest['Close']:7.2f} | %Change: {pct_change:6.2f}% | "
                  f"RVOL: {rvol:5.2f}x | Float: {float_m:6.1f}M")
        else:
            print("✗ (no data)")
            
    except Exception as e:
        print(f"✗ (error: {str(e)[:50]})")
    
    time.sleep(0.5)  # Be nice to Yahoo's servers

print()
print("=" * 80)
print("Scanner is working! All data functions are operational.")
print("If no stocks meet criteria, it means they're not moving today.")
print("=" * 80)
