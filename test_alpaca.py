"""
Test Alpaca integration
"""
import alpaca_data

print("Testing Alpaca API integration...")
print("-" * 50)

# Check if Alpaca is available
if alpaca_data.is_alpaca_available():
    print("✅ Alpaca API is configured and ready!")
    
    # Test getting most active stocks
    print("\nTesting most active stocks...")
    active = alpaca_data.get_most_active_stocks(limit=10)
    print(f"Found {len(active)} active stocks: {active[:5]}...")
    
    # Test getting a quote
    if active:
        test_symbol = active[0]
        print(f"\nTesting quote for {test_symbol}...")
        quote = alpaca_data.get_quote(test_symbol)
        if quote:
            print(f"  Price: ${quote.get('price', 'N/A')}")
            print(f"  Volume: {quote.get('volume', 'N/A'):,}")
            print("  ✅ Quote data working!")
        else:
            print("  ❌ Could not get quote")
    
    # Test market movers
    print("\nTesting market movers...")
    movers = alpaca_data.get_market_movers(limit=5)
    print(f"  Gainers: {movers.get('gainers', [])[:5]}")
    print(f"  Losers: {movers.get('losers', [])[:5]}")
    
else:
    print("❌ Alpaca API not configured")
    print("\nTo set up Alpaca:")
    print("1. Go to https://alpaca.markets/docs/dashboard/overview/")
    print("2. Get your API Key and Secret Key")
    print("3. Add them to .env file:")
    print("   ALPACA_API_KEY=your_key_here")
    print("   ALPACA_SECRET_KEY=your_secret_here")

print("\n" + "-" * 50)
print("Test complete!")
