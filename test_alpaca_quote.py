"""
Test Alpaca quote data structure to debug percent change
"""
import alpaca_data

test_symbols = ['T', 'AAPL', 'VALE']

print("Testing Alpaca quote data structure...")
print("=" * 60)

for symbol in test_symbols:
    print(f"\n{symbol}:")
    quote = alpaca_data.get_quote(symbol)
    if quote:
        print(f"  Price: {quote.get('price')}")
        print(f"  Volume: {quote.get('volume')}")
        print(f"  High: {quote.get('high')}")
        print(f"  Low: {quote.get('low')}")
        print(f"  Prev Close: {quote.get('prev_close')}")
        
        # Calculate pct change if we have prev_close
        if quote.get('price') and quote.get('prev_close'):
            pct_change = ((quote['price'] - quote['prev_close']) / quote['prev_close']) * 100
            print(f"  % Change: {pct_change:.2f}%")
        else:
            print(f"  % Change: CANNOT CALCULATE (missing prev_close)")
    else:
        print(f"  ERROR: Could not get quote")

print("\n" + "=" * 60)
