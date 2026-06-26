"""
High-Momentum Small-Cap Breakout Scanner with KPI Scoring Engine
Now using Alpaca Markets API (unlimited, rate-free) with yfinance fallback

Features:
- Real-time quote data via Alpaca
- Intraday volume and RVOL calculations
- Float and news filtering
- KPI scoring engine (0-100)
- Ranked output by momentum score
- No rate limiting!
"""

import time
import yfinance as yf
import pandas as pd
from typing import Dict, List
from datetime import datetime, timedelta
import alpaca_data
import finviz_scraper

# Use Finviz for fast initial scan, then detailed data for top candidates
USE_FINVIZ = False  # Finviz blocks scraping with 429 rate limiting, use Alpaca/yfinance instead
UNIVERSE_SIZE = 1000

MIN_PRICE = 0.50
MAX_PRICE = 100  # Expanded to see more stocks
MIN_PCT_CHANGE = 0.5  # Just need positive momentum
MIN_RVOL = 1  # Require at least average volume (projected to EOD)
MAX_RVOL = 20  # Cap at 20x to avoid panic selling / halts
MAX_FLOAT = 100_000_000  # Increased to 100M

# Cache for universe (with Alpaca, no rate limits!)
_universe_cache = None
_universe_cache_time = None
UNIVERSE_CACHE_DURATION = 60  # 1 minute with Alpaca (no rate limits!)


# ========== DATA LAYER (ALPACA + YFINANCE FALLBACK) ==========

def get_universe() -> List[str]:
    """
    Return a list of tickers to scan.
    Uses Alpaca API if available, falls back to Yahoo Finance screeners.
    Cached for 1 minute (Alpaca has no rate limits!).
    """
    global _universe_cache, _universe_cache_time
    
    # Check if we have a valid cache
    if _universe_cache is not None and _universe_cache_time is not None:
        age = time.time() - _universe_cache_time
        if age < UNIVERSE_CACHE_DURATION:
            print(f"Using cached universe ({len(_universe_cache)} stocks, {int(age)}s old)")
            return _universe_cache
    
    tickers = set()
    

    # Use only Alpaca for universe
    base_watchlist = ["GME", "AMC", "PLTR", "SOFI", "RIVN", "LCID", "NIO", "TLRY", "SNDL"]
    tickers.update(base_watchlist)

    if alpaca_data.is_alpaca_available():
        print("Refreshing universe from Alpaca API (no rate limits)...")
        try:
            active = alpaca_data.get_most_active_stocks(limit=UNIVERSE_SIZE)
            tickers.update(active)
            print(f"✓ Added {len(active)} most active stocks from Alpaca")

            movers = alpaca_data.get_market_movers(limit=50)
            tickers.update(movers.get('gainers', []))
            tickers.update(movers.get('losers', []))
            print(f"✓ Added {len(movers.get('gainers', []))} gainers and {len(movers.get('losers', []))} losers")
        except Exception as e:
            print(f"Error fetching from Alpaca: {e}")

    ticker_list = list(tickers)[:UNIVERSE_SIZE]
    print(f"Total universe: {len(ticker_list)} stocks (target: {UNIVERSE_SIZE}, cached for 1 min)")
    print(f"Tickers being scanned: {ticker_list}")

    _universe_cache = ticker_list
    _universe_cache_time = time.time()

    return ticker_list
    
    ticker_list = list(tickers)
    print(f"Total universe: {len(ticker_list)} stocks (cached for 1 min)")
    print(f"Tickers being scanned: {ticker_list}")

    # Update cache
    _universe_cache = ticker_list
    _universe_cache_time = time.time()

    return ticker_list


def get_intraday_quote(ticker: str) -> Dict:
    """Get current day's quote - uses yfinance as primary source for better volume data"""
    # Use yfinance as primary source (Alpaca volume data is often incomplete)
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d", interval="1m")
        
        if hist.empty:
            # Try daily data if intraday not available
            hist = stock.history(period="2d")
            if hist.empty:
                return {}
        
        # Get today's data
        latest = hist.iloc[-1]
        today_open = hist.iloc[0]['Open'] if len(hist) > 0 else latest['Open']
        
        # Calculate VWAP approximation (price * volume weighted average)
        if 'Volume' in hist.columns and len(hist) > 0:
            vwap = (hist['Close'] * hist['Volume']).sum() / hist['Volume'].sum()
        else:
            vwap = latest['Close']
        
        return {
            "price": float(latest['Close']),
            "open": float(today_open),
            "high": float(hist['High'].max()),
            "low": float(hist['Low'].min()),
            "volume": int(hist['Volume'].sum()),
            "vwap": float(vwap),
        }
    except Exception as e:
        print(f"yfinance error for {ticker}: {e}")
        
        # Fallback to Alpaca only if yfinance fails
        if alpaca_data.is_alpaca_available():
            try:
                quote_data = alpaca_data.get_quote(ticker)
                if quote_data and quote_data.get('price'):
                    # Calculate VWAP from intraday bars
                    bars_df = alpaca_data.get_intraday_bars(ticker, minutes=60)
                    vwap = quote_data['price']  # Default to current price
                    
                    if bars_df is not None and not bars_df.empty and 'volume' in bars_df.columns:
                        total_volume = bars_df['volume'].sum()
                        if total_volume > 0:
                            vwap = (bars_df['close'] * bars_df['volume']).sum() / total_volume
                    
                    return {
                        "price": float(quote_data['price']),
                        "open": float(quote_data['open']) if quote_data.get('open') else float(quote_data['price']),
                        "high": float(quote_data['high']) if quote_data.get('high') else float(quote_data['price']),
                        "low": float(quote_data['low']) if quote_data.get('low') else float(quote_data['price']),
                        "volume": int(quote_data['volume']),
                        "vwap": float(vwap),
                    }
            except Exception as e2:
                print(f"Alpaca fallback error for {ticker}: {e2}")
        
        return {}


def get_prev_close(ticker: str) -> float:
    """Get previous day's close - uses Alpaca if available, falls back to yfinance"""
    # Try Alpaca first
    if alpaca_data.is_alpaca_available():
        try:
            quote_data = alpaca_data.get_quote(ticker)
            if quote_data and quote_data.get('prev_close'):
                return float(quote_data['prev_close'])
        except Exception as e:
            print(f"Alpaca error for {ticker} prev_close: {e}")
    
    # Fallback to yfinance
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if len(hist) < 2:
            return 0.0
        return float(hist['Close'].iloc[-2])
    except:
        return 0.0


def get_avg_volume(ticker: str, lookback: int = 20) -> int:
    """Get average volume over lookback period - uses Alpaca if available"""
    # Try Alpaca first
    if alpaca_data.is_alpaca_available():
        try:
            return alpaca_data.get_avg_volume(ticker, lookback)
        except Exception as e:
            print(f"Alpaca avg_volume error for {ticker}: {e}")
    
    # Fallback to yfinance (slower)
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{lookback+5}d")
        if hist.empty:
            return 0
        return int(hist['Volume'].tail(lookback).mean())
    except:
        return 0


def get_float_shares(ticker: str) -> int:
    """Get float shares - simplified to reduce API calls"""
    # Try to fetch float from yahooquery first
    try:
        from yahooquery import Ticker
        yq = Ticker(ticker)
        info = yq.asset_profile
        if ticker in info and 'floatShares' in info[ticker] and info[ticker]['floatShares']:
            return int(info[ticker]['floatShares'])
    except Exception as e:
        print(f"Error fetching float from yahooquery for {ticker}: {e}")

    # Fallback to yFinance
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        if 'floatShares' in info and info['floatShares']:
            return int(info['floatShares'])
    except Exception as e:
        print(f"Error fetching float from yfinance for {ticker}: {e}")

    # Fallback to default if not available
    return 10_000_000


def has_breaking_news(ticker: str, lookback_minutes: int = 1440) -> bool:
    """Check if ticker has recent news - disabled to improve speed"""
    # News checking is slow and not critical for momentum scanning
    # Can be re-enabled later with caching or async fetching
    return False


def get_sector_moving(ticker: str) -> bool:
    """Simple stub: always False for now or map ticker→sector ETF and check its % change"""
    return False


def get_atr_values(ticker: str) -> Dict[str, float]:
    """Calculate ATR using daily candles - uses Alpaca if available"""
    hist = None
    
    # Try Alpaca first
    if alpaca_data.is_alpaca_available():
        try:
            hist = alpaca_data.get_daily_bars(ticker, days=30)
            if hist is not None and not hist.empty:
                # Rename columns to match yfinance format
                hist = hist.rename(columns={'high': 'High', 'low': 'Low', 'close': 'Close'})
        except Exception as e:
            print(f"Alpaca ATR error for {ticker}: {e}")
    
    # Fallback to yfinance if needed
    if hist is None or hist.empty:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="30d")
        except:
            return {"atr_today": 1.0, "atr_20": 1.0}
    
    if len(hist) < 20:
        return {"atr_today": 1.0, "atr_20": 1.0}
    
    try:
        # Calculate True Range
        high = hist['High']
        low = hist['Low']
        close_prev = hist['Close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr_20 = tr.tail(20).mean()
        atr_today = tr.iloc[-1]
        
        return {"atr_today": float(atr_today), "atr_20": float(atr_20)}
    except:
        return {"atr_today": 1.0, "atr_20": 1.0}


def get_sma_50(ticker: str) -> float:
    """Get 50-day EMA (kept function name for backward compatibility)."""
    hist = None
    
    # Try Alpaca first
    if alpaca_data.is_alpaca_available():
        try:
            hist = alpaca_data.get_daily_bars(ticker, days=60)
            if hist is not None and not hist.empty:
                # Rename columns to match yfinance format
                hist = hist.rename(columns={'close': 'Close'})
        except Exception as e:
            print(f"Alpaca SMA error for {ticker}: {e}")
    
    # Fallback to yfinance if needed
    if hist is None or hist.empty:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="60d")
        except:
            return 0.0
    
    if len(hist) < 50:
        return 0.0
    
    try:
        ema_50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
        return float(ema_50)
    except:
        return 0.0


# ========== KPI + SCORING ==========

def calc_pct_change(price: float, open_price: float) -> float:
    return (price - open_price) / open_price * 100 if open_price else 0


def calc_gap_pct(open_price: float, prev_close: float) -> float:
    return (open_price - prev_close) / prev_close * 100 if prev_close else 0


def calc_relative_volume(volume: int, avg_volume: int) -> float:
    if avg_volume == 0:
        return 0
    
    # Project current volume to end-of-day using Intraday Distribution Curve (U-shaped)
    now = datetime.now()
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # If before market open or after close, use current volume as-is (no projection needed)
    if now < market_open or now >= market_close:
        return volume / avg_volume
    
    # Calculate minutes since market open
    elapsed_minutes = (now - market_open).total_seconds() / 60
    
    if elapsed_minutes <= 0:
        return volume / avg_volume
    
    # Intraday Distribution Curve - typical % of daily volume by time period
    # Based on U-shaped pattern: high at open, low mid-day, high at close
    # Format: (minutes_from_open, cumulative_pct_of_daily_volume)
    volume_curve = [
        (0, 0.00),      # Market open
        (30, 0.12),     # 10:00 AM: 12% cumulative
        (60, 0.20),     # 10:30 AM: 20% cumulative
        (90, 0.27),     # 11:00 AM: 27% cumulative
        (120, 0.35),    # 11:30 AM: 35% cumulative
        (150, 0.42),    # 12:00 PM: 42% cumulative
        (180, 0.48),    # 12:30 PM: 48% cumulative
        (210, 0.54),    # 1:00 PM: 54% cumulative
        (240, 0.60),    # 1:30 PM: 60% cumulative
        (270, 0.66),    # 2:00 PM: 66% cumulative
        (300, 0.72),    # 2:30 PM: 72% cumulative
        (330, 0.78),    # 3:00 PM: 78% cumulative
        (360, 0.88),    # 3:30 PM: 88% cumulative
        (390, 1.00),    # 4:00 PM: 100% (market close)
    ]
    
    # Find expected percentage of volume accumulated by now
    expected_pct_so_far = 0.0
    
    for i in range(len(volume_curve) - 1):
        time_start, pct_start = volume_curve[i]
        time_end, pct_end = volume_curve[i + 1]
        
        if elapsed_minutes <= time_end:
            # Interpolate between this period's start and end
            if elapsed_minutes <= time_start:
                expected_pct_so_far = pct_start
            else:
                period_duration = time_end - time_start
                time_into_period = elapsed_minutes - time_start
                pct_of_period = time_into_period / period_duration if period_duration > 0 else 0
                expected_pct_so_far = pct_start + (pct_end - pct_start) * pct_of_period
            break
    else:
        # If we're past all periods, use 100%
        expected_pct_so_far = 1.0
    
    # Prevent division by zero
    if expected_pct_so_far <= 0:
        expected_pct_so_far = 0.01  # Assume at least 1% should have traded
    
    # Project to full day volume based on distribution curve
    projected_volume = volume / expected_pct_so_far
    
    return projected_volume / avg_volume


def calc_turnover(volume: int, float_shares: int) -> float:
    if float_shares == 0:
        return 0
    return volume / float_shares


def calc_dollar_volume(price: float, volume: int) -> float:
    return price * volume


def calc_wick_ratio(high: float, low: float, open_price: float, close: float) -> float:
    body = abs(close - open_price)
    total_range = high - low
    if total_range == 0:
        return 1
    return body / total_range if body > 0 else 0


def calc_atr_expansion(atr_today: float, atr_20: float) -> float:
    if atr_20 == 0:
        return 0
    return atr_today / atr_20


def compute_kpis(ticker: str) -> Dict:
    q = get_intraday_quote(ticker)
    if not q:
        return {}

    price = q["price"]
    open_price = q["open"]
    high = q["high"]
    low = q["low"]
    volume = q["volume"]
    vwap = q["vwap"]

    prev_close = get_prev_close(ticker)
    avg_vol = get_avg_volume(ticker)
    float_shares = get_float_shares(ticker)
    news = has_breaking_news(ticker)
    sector_sympathy = get_sector_moving(ticker)
    atr_vals = get_atr_values(ticker)
    sma_50 = get_sma_50(ticker)

    pct_change = calc_pct_change(price, open_price)
    gap_pct = calc_gap_pct(open_price, prev_close)
    rvol = calc_relative_volume(volume, avg_vol)
    # Debug RVOL calculation
    now = datetime.now()
    market_status = "CLOSED" if now.hour < 9 or now.hour >= 16 else "OPEN"
    print(f"[RVOL DEBUG] {ticker}: volume={volume:,}, avg_vol={avg_vol:,}, rvol={rvol:.3f}, market={market_status}")
    turnover = calc_turnover(volume, float_shares)
    dollar_vol = calc_dollar_volume(price, volume)
    wick_ratio = calc_wick_ratio(high, low, open_price, price)
    atr_expansion = calc_atr_expansion(atr_vals["atr_today"], atr_vals["atr_20"])
    
    # Calculate SMA 50 delta percentage
    sma_50_delta = ((price - sma_50) / sma_50 * 100) if sma_50 > 0 else 0

    above_vwap = price >= vwap
    hod_break_clean = price >= high  # simple version
    spread_stable = True  # could be wired from NBBO
    halt_risk = (rvol >= 5 and float_shares <= 20_000_000)
    trend_alignment = True  # placeholder for MTF logic
    key_level_break = True  # placeholder for PMH/PDH logic
    base_duration = 30
    news_impact = 10 if news else 0

    return {
        "price": price,
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,
        "vwap": vwap,
        "prev_close": prev_close,

        "pct_change": pct_change,
        "gap_pct": gap_pct,
        "relative_volume": rvol,
        "turnover": turnover,
        "dollar_volume": dollar_vol,
        "wick_ratio": wick_ratio,
        "atr_expansion": atr_expansion,
        "sma_50": sma_50,
        "sma_50_delta": sma_50_delta,

        "above_vwap": above_vwap,
        "hod_break_clean": hod_break_clean,
        "spread_stable": spread_stable,
        "halt_risk": halt_risk,
        "trend_alignment": trend_alignment,
        "key_level_break": key_level_break,
        "base_duration": base_duration,

        "news_impact": news_impact,
        "sector_sympathy": sector_sympathy,
        "float_shares": float_shares,
        "has_news": news,
        "avg_volume_20d": avg_vol,
    }


def score_momentum(kpis: Dict) -> float:
    score = 0
    score += min(max((kpis["pct_change"] / 20) * 10, 0), 10)
    score += min(max((kpis["relative_volume"] / 10) * 10, 0), 10)
    score += 5 if kpis["above_vwap"] else 0
    score += 5 if kpis["hod_break_clean"] else 0
    return score


def score_liquidity(kpis: Dict) -> float:
    score = 0
    score += min(max((kpis["turnover"] / 5) * 10, 0), 10)
    score += 5 if kpis["dollar_volume"] >= 20_000_000 else 0
    score += 5 if kpis["spread_stable"] else 0
    return score


def score_volatility(kpis: Dict) -> float:
    score = 0
    score += min(max((kpis["atr_expansion"] / 3) * 10, 0), 10)
    score += 5 if kpis["wick_ratio"] >= 0.5 else 0
    score += 5 if kpis["halt_risk"] else 0
    return score


def score_structure(kpis: Dict) -> float:
    score = 0
    score += 5 if kpis["trend_alignment"] else 0
    score += 5 if kpis["key_level_break"] else 0
    score += 5 if kpis["base_duration"] >= 30 else 0
    return score


def score_catalyst(kpis: Dict) -> float:
    score = 0
    score += kpis["news_impact"]
    score += 5 if kpis["sector_sympathy"] else 0
    return score


def total_score(kpis: Dict) -> float:
    return (
        score_momentum(kpis)
        + score_liquidity(kpis)
        + score_volatility(kpis)
        + score_structure(kpis)
        + score_catalyst(kpis)
    )


def passes_base_filters(kpis: Dict, ticker: str = "", verbose: bool = True) -> bool:
    """Check if stock passes all base filters. Returns tuple of (passed, reason)"""
    
    if not (MIN_PRICE <= kpis["price"] <= MAX_PRICE):
        if verbose:
            print(f"[FILTER] ❌ {ticker}: Price ${kpis['price']:.2f} outside range ${MIN_PRICE}-${MAX_PRICE}")
        return False
    
    if kpis["pct_change"] < MIN_PCT_CHANGE:
        if verbose:
            print(f"[FILTER] ❌ {ticker}: %Change {kpis['pct_change']:.2f}% < {MIN_PCT_CHANGE}%")
        return False
    
    if MIN_RVOL > 0 and kpis["relative_volume"] < MIN_RVOL:
        if verbose:
            print(f"[FILTER] ❌ {ticker}: RVOL {kpis['relative_volume']:.2f}x < {MIN_RVOL}x")
        return False
    
    if MAX_RVOL > 0 and kpis["relative_volume"] > MAX_RVOL:
        if verbose:
            print(f"[FILTER] ❌ {ticker}: RVOL {kpis['relative_volume']:.2f}x > {MAX_RVOL}x (extreme outlier)")
        return False
    
    if kpis["float_shares"] >= MAX_FLOAT:
        if verbose:
            print(f"[FILTER] ❌ {ticker}: Float {kpis['float_shares']/1_000_000:.1f}M >= {MAX_FLOAT/1_000_000}M")
        return False

    if kpis["sma_50_delta"] <= 0:
        if verbose:
            print(f"[FILTER] ❌ {ticker}: Price below/at 50 EMA ({kpis['sma_50_delta']:.2f}%)")
        return False
    
    # Quality check: high RVOL should indicate accumulation, not panic selling
    # For RVOL > 5x, require minimum price movement to avoid halt/crash scenarios
    rvol = kpis["relative_volume"]
    pct_change = kpis["pct_change"]
    if rvol > 5 and pct_change < 1.0:
        if verbose:
            print(f"[FILTER] ❌ {ticker}: High RVOL {rvol:.1f}x but weak move +{pct_change:.2f}% (distribution/panic)")
        return False
    
    # Temporarily removed news requirement to see all qualifying stocks
    # if not kpis["has_news"]:
    #     return False
    
    if verbose:
        print(f"[FILTER] ✅ {ticker}: PASSED all filters (${kpis['price']:.2f}, +{pct_change:.2f}%, {rvol:.2f}x RVOL)")
    return True


def run_scan_finviz() -> List[Dict]:
    """
    Hybrid approach: Use Finviz for fast pre-filtered scan,
    then fetch detailed data only for qualifying stocks
    """
    print("[Scanner] Using Finviz hybrid mode for faster scanning...")
    
    # Step 1: Get pre-filtered stocks from Finviz (1-2 seconds for 100+ stocks)
    finviz_stocks = finviz_scraper.scrape_finviz_screener(
        min_price=MIN_PRICE,
        max_price=MAX_PRICE,
        min_rvol=MIN_RVOL,
        max_float_m=MAX_FLOAT / 1_000_000,
        limit=200  # Get top 200 by RVOL
    )
    
    if not finviz_stocks:
        print("[Scanner] No stocks found on Finviz, falling back to standard scan")
        return run_scan_standard()
    
    print(f"[Scanner] Finviz returned {len(finviz_stocks)} pre-filtered stocks")
    print("\n[FINVIZ DATA] Raw data from Finviz screener:")
    print("=" * 100)
    for stock in finviz_stocks:
        print(f"  {stock['ticker']:6} | Price: ${stock['price']:6.2f} | "
              f"%Chg: {stock['pct_change']:6.2f}% | RVOL: {stock.get('relative_volume', 0):5.2f}x | "
              f"Vol: {stock.get('volume', 0):>12,} | Float: {stock.get('float_shares', 0)/1_000_000:5.1f}M")
    print("=" * 100)
    print()
    
    results = []
    qualified_count = 0
    
    # Step 2: Apply our filters to Finviz data (fast, no API calls)
    for stock in finviz_stocks:
        ticker = stock['ticker']
        
        # Quick filter on Finviz data alone
        if stock['pct_change'] < MIN_PCT_CHANGE:
            print(f"[FILTER] ❌ {ticker}: %Change {stock['pct_change']:.2f}% < {MIN_PCT_CHANGE}%")
            continue
        
        if stock['relative_volume'] > MAX_RVOL:
            print(f"[FILTER] ❌ {ticker}: RVOL {stock['relative_volume']:.2f}x > {MAX_RVOL}x (extreme outlier)")
            continue
        
        # Quality check: high RVOL needs good price movement
        if stock['relative_volume'] > 5 and stock['pct_change'] < 1.0:
            print(f"[FILTER] ❌ {ticker}: High RVOL {stock['relative_volume']:.1f}x but weak move +{stock['pct_change']:.2f}%")
            continue
        
        print(f"[FILTER] ✅ {ticker}: PASSED Finviz filters (${stock['price']:.2f}, +{stock['pct_change']:.2f}%, {stock['relative_volume']:.2f}x RVOL)")
        
        # Step 3: Fetch detailed data from Finviz for complete OHLC and fundamentals
        detailed = finviz_scraper.get_detailed_quote(ticker)
        if detailed:
            stock.update(detailed)
        
        # Build KPIs from Finviz data (using actual Finviz values)
        open_price = stock.get('open', stock['price'])
        high = stock.get('high', stock['price'])
        low = stock.get('low', stock['price'])
        prev_close = stock.get('prev_close', stock['price'] / (1 + stock['pct_change']/100))
        vwap = stock.get('vwap', stock['price'])
        
        # Calculate gap % from Finviz data
        gap_pct = ((open_price - prev_close) / prev_close * 100) if prev_close else 0.0
        
        # Calculate wick ratio from actual OHLC
        body = abs(stock['price'] - open_price)
        total_range = high - low
        wick_ratio = (body / total_range) if total_range > 0 else 0.5
        
        # Determine if above VWAP
        above_vwap = stock['price'] >= vwap
        
        # Determine if breaking HOD
        hod_break_clean = stock['price'] >= high
        
        # Halt risk check
        halt_risk = (stock.get('relative_volume', 1.0) >= 5 and stock.get('float_shares', 10_000_000) <= 20_000_000)
        
        # Get SMA 50 and calculate delta
        sma_50 = get_sma_50(ticker)
        sma_50_delta = ((stock['price'] - sma_50) / sma_50 * 100) if sma_50 > 0 else 0
        if sma_50_delta <= 0:
            print(f"[FILTER] ❌ {ticker}: Price below/at 50 EMA ({sma_50_delta:.2f}%)")
            continue
        
        kpis = {
            "ticker": ticker,
            "price": stock['price'],
            "pct_change": stock['pct_change'],
            "relative_volume": stock.get('relative_volume', 1.0),
            "float_shares": stock.get('float_shares', 10_000_000),
            "volume": stock.get('volume', 0),
            "avg_volume_20d": stock.get('avg_volume', 1_000_000),
            
            # Use actual Finviz OHLC data
            "open": open_price,
            "high": high,
            "low": low,
            "vwap": vwap,
            "prev_close": prev_close,
            "gap_pct": gap_pct,
            "turnover": stock.get('volume', 0) / stock.get('float_shares', 10_000_000),
            "dollar_volume": stock['price'] * stock.get('volume', 0),
            "wick_ratio": wick_ratio,
            "atr_expansion": 1.0,  # Finviz doesn't provide ATR history
            "sma_50": sma_50,
            "sma_50_delta": sma_50_delta,
            "above_vwap": above_vwap,
            "hod_break_clean": hod_break_clean,
            "spread_stable": True,
            "halt_risk": halt_risk,
            "trend_alignment": True,
            "key_level_break": True,
            "base_duration": 30,
            "news_impact": 0,
            "sector_sympathy": False,
            "has_news": False,
        }
        
        score = total_score(kpis)
        results.append({"ticker": ticker, "score": score, "kpis": kpis})
        qualified_count += 1
        print(f"[Scanner] ⭐ {ticker} QUALIFIED! Score: {score:.1f}")
        
        # Rate limit: small delay every 5 stocks when fetching detailed data
        if qualified_count % 5 == 0:
            time.sleep(0.3)
    
    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"[Scanner] Found {len(results)} stocks matching criteria")
    return results


def run_scan_standard() -> List[Dict]:
    """
    Standard approach: Scan universe using Alpaca/yfinance
    """
    universe = get_universe()
    results = []
    
    print(f"[Scanner] Scanning {len(universe)} stocks (standard mode)...")

    for i, ticker in enumerate(universe):
        try:
            kpis = compute_kpis(ticker)
            if not kpis:
                continue
            if not passes_base_filters(kpis, ticker=ticker, verbose=True):
                continue
            score = total_score(kpis)
            results.append({"ticker": ticker, "score": score, "kpis": kpis})
            print(f"[Scanner] ⭐ {ticker} QUALIFIED! Score: {score:.1f}")
        except Exception as e:
            print(f"[ERROR] {ticker}: {e}")
            continue
        
        # Add small delay every 10 stocks to avoid rate limits
        if (i + 1) % 10 == 0:
            time.sleep(0.5)
            print(f"  Progress: {i+1}/{len(universe)} stocks")

    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"[Scanner] Found {len(results)} stocks matching criteria")
    return results


def run_scan() -> List[Dict]:
    """
    Main scan function - uses Finviz hybrid or standard based on config
    """
    if USE_FINVIZ:
        try:
            return run_scan_finviz()
        except Exception as e:
            print(f"[Scanner] Finviz error: {e}, falling back to standard scan")
            import traceback
            traceback.print_exc()
            return run_scan_standard()
    else:
        return run_scan_standard()


if __name__ == "__main__":
    scan_mode = "Finviz Hybrid (FAST)" if USE_FINVIZ else "Alpaca/yfinance (SLOW)"
    print(f"Starting momentum scanner - Mode: {scan_mode}")
    print(f"Filters: Price ${MIN_PRICE}-${MAX_PRICE}, %Change >{MIN_PCT_CHANGE}%, RVOL {MIN_RVOL}-{MAX_RVOL}x, Float <{MAX_FLOAT/1_000_000}M")
    print("Note: High RVOL (>5x) requires +1% minimum move to ensure rally vs panic")
    if USE_FINVIZ:
        print("Note: Finviz mode scans 200+ stocks in ~5 seconds (pre-filtered by RVOL)")
    else:
        print("Note: Data may be delayed 15-20 minutes. For real-time, upgrade to Polygon.io")
    print()
    
    while True:
        ranked = run_scan()
        print("=" * 80)
        print(f"Top candidates ({time.strftime('%Y-%m-%d %H:%M:%S')}):")
        print("=" * 80)
        
        if not ranked:
            print("No stocks currently meet all filter criteria.")
        else:
            for r in ranked[:10]:
                kpi = r['kpis']
                print(f"{r['ticker']:6} | Score: {r['score']:5.1f} | "
                      f"Price: ${kpi['price']:6.2f} | %Chg: {kpi['pct_change']:6.1f}% | "
                      f"RVOL: {kpi['relative_volume']:5.1f}x | Float: {kpi['float_shares']/1_000_000:5.1f}M")
        
        print()
        print("Sleeping 60 seconds...")
        time.sleep(60)  # poll every 60 seconds (yfinance is slower)
