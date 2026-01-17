# High-Momentum Small-Cap Breakout Scanner

A KPI-driven momentum scanner for small-cap stocks with explosive potential. Scans for stocks with high relative volume, breaking news, low float, and strong price action.

## 🎯 Core Filters

The scanner identifies stocks meeting these mechanical criteria:

- **Price Range**: $2 - $20
- **Daily Momentum**: ≥ +10% on the day
- **Relative Volume**: ≥ 5x average
- **Float**: < 20 million shares
- **Breaking News**: Fresh catalyst within 24 hours

## 🏆 KPI Scoring System (0-100)

Each stock is scored across 5 weighted categories:

| Category | Weight | Key Metrics |
|----------|--------|-------------|
| **Momentum** | 30% | % Change, RVOL, VWAP Control, HOD Break |
| **Liquidity** | 20% | Turnover Rate, Dollar Volume, Spread Stability |
| **Volatility** | 20% | ATR Expansion, Wick Ratio, Halt Risk |
| **Structure** | 15% | Trend Alignment, Key Level Breaks, Base Duration |
| **Catalyst** | 15% | News Impact, Sector Sympathy |

## 📁 Files

- `momentum_scanner.py` - Full Python scanner with Polygon.io integration
- `kpi_momentum_overlay.pine` - TradingView Pine Script visual overlay
- `requirements.txt` - Python dependencies

## 🚀 Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Data Source

**FREE OPTION (Default)**: The scanner uses **yfinance (Yahoo Finance)** - completely free, no API key needed!

**PREMIUM OPTION**: For real-time data with more features, upgrade to [Polygon.io](https://polygon.io) (Real-Time tier: ~$199/month). See "Upgrading to Polygon.io" section below.

### 3. Customize Your Universe

Edit the `get_universe()` function in `momentum_scanner.py` to add your watchlist:

```python
def get_universe() -> List[str]:
    return ["TSLA", "NVDA", "GME", "AMC"]  # Add your tickers
```

### 4. Run the Scanner

```bash
python momentum_scanner.py
```

The scanner will:
- Poll every 30 seconds
- Display ranked results by KPI score
- Show key metrics for top candidates

## 📊 TradingView Setup

1. Open TradingView
2. Click "Pine Editor" at the bottom
3. Copy/paste the contents of `kpi_momentum_overlay.pine`
4. Click "Add to Chart"
5. Adjust inputs as needed (price range, RVOL threshold, etc.)

The overlay provides:
- Visual KPI score (0-100 scale)
- Green background when conditions are met
- Labels showing score on qualifying bars
- Score threshold line at 60

## 🔧 Customization

### Adjust Filter Thresholds

In `momentum_scanner.py`, modify the constants at the top:

```python
MIN_PRICE = 2           # Minimum stock price
MAX_PRICE = 20          # Maximum stock price
MIN_PCT_CHANGE = 10     # Minimum % change on the day
MIN_RVOL = 5            # Minimum relative volume
MAX_FLOAT = 20_000_000  # Maximum float shares
```

### Adjust Scoring Weights

Modify the individual scoring functions:
- `score_momentum()` - Momentum category (30 points)
- `score_liquidity()` - Liquidity category (20 points)
- `score_volatility()` - Volatility category (20 points)
- `score_structure()` - Structure category (15 points)
- `score_catalyst()` - Catalyst category (15 points)

## 🧠 KPI Definitions

### Momentum KPIs
- **% Change**: Intraday price change from open
- **Relative Volume (RVOL)**: Current volume / 20-day average volume
- **VWAP Control**: Price trading above Volume-Weighted Average Price
- **HOD Break Quality**: Clean break of high-of-day

### Liquidity KPIs
- **Turnover Rate**: Volume / Float (how many times float has rotated)
- **Dollar Volume**: Price × Volume (ensures tradability)
- **Spread Stability**: Tight bid/ask spreads indicate institutional interest

### Volatility KPIs
- **ATR Expansion**: Today's ATR vs 20-day ATR (2-3x indicates breakout)
- **Wick Ratio**: Body size / Total range (small wicks = controlled trend)
- **Halt Risk**: High volatility + low float = potential trading halt

### Structural KPIs
- **Multi-Timeframe Trend Alignment**: 5m, 15m, 1h all trending same direction
- **Key Level Breaks**: Premarket high, previous day high, weekly levels
- **Base Duration**: Longer bases typically lead to stronger breakouts

### Catalyst KPIs
- **News Impact Score**: Weighted by category (FDA > Earnings > PR)
- **Sector Sympathy**: Is the entire sector moving together?

## 📈 Expected Output

```
================================================================================
Top candidates (2026-01-16 09:45:23):
================================================================================
GME    | Score:  78.5 | Price: $  8.45 | %Chg:   14.2% | RVOL:   8.3x | Float:  12.5M
AMC    | Score:  72.1 | Price: $  5.67 | %Chg:   11.8% | RVOL:   6.9x | Float:  15.2M
CVNA   | Score:  65.3 | Price: $ 12.34 | %Chg:   10.5% | RVOL:   5.2x | Float:  18.7M
```

## ⚠️ Important Notes

### Data Source

**Current (Free)**: Yahoo Finance via yfinance
- Delayed quotes (15-20 min delay)
- Basic news detection
- Float data available
- Historical volume for RVOL calculation
- **No cost, no API key required**

**Upgrade Option**: Polygon.io's Real-Time tier (~$199/month) for:
- True real-time quotes
- Timestamped news feed
- Better float data
- Faster updates

### Rate Limits
Polygon has generous rate limits, but consider:
- Using WebSockets instead of REST polling for faster updates
- Caching data where appropriate
- Implementing exponential backoff on errors

### Placeholders to Implement
The scanner has placeholder logic for:
- `get_sector_moving()` - Sector sympathy detection
- `trend_alignment` - Multi-timeframe trend analysis
- `key_level_break` - Premarket/previous day high logic
- `base_duration` - Time spent in consolidation

Implement these for more sophisticated scoring.

## � Upgrading to Polygon.io (Optional)

Once you're ready for real-time data:

1. Sign up at [Polygon.io](https://polygon.io) and get an API key
2. Set environment variable: `$env:POLYGON_API_KEY="your_key"`
3. In `momentum_scanner.py`, replace the yfinance data layer with the Polygon version (commented in the file)
4. Update imports and restart the scanner

## 🚀 Next Steps

1. **Expand Universe Builder**: Auto-pull all low-float stocks from market
2. **Upgrade to Real-Time Data**: Switch to Polygon.io when ready
3. **Add WebSocket Support**: Real-time streaming instead of polling
4. **Build Alert System**: Discord, SMS, or email notifications
5. **Add Execution Layer**: Wire to Alpaca or MT5 for automated trading
6. **Create Dashboard**: Web interface with live updating results
7. **Backtest Engine**: Test strategy on historical data

## 📚 Resources

- [Polygon.io API Docs](https://polygon.io/docs)
- [TradingView Pine Script Reference](https://www.tradingview.com/pine-script-reference/)

## ⚖️ Disclaimer

This scanner is for educational and research purposes only. Trading stocks carries significant risk. Always do your own research and never risk more than you can afford to lose. Past performance does not guarantee future results.

## 📝 License

MIT License - Feel free to modify and use for your own trading systems.
