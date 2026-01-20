"""
High-Momentum Small-Cap Breakout Scanner with KPI Scoring Engine
Using FREE Yahoo Finance data (yfinance)

Features:
- Intraday quote data
- Float and news filtering
- KPI scoring engine (0-100)
- Ranked output by momentum score

Note: Currently uses yfinance (FREE). For real-time data, upgrade to Polygon.io
"""

import time
import yfinance as yf
import pandas as pd
from typing import Dict, List
from datetime import datetime, timedelta

MIN_PRICE = 2
MAX_PRICE = 50  # Relaxed to see more stocks
MIN_PCT_CHANGE = 2  # Relaxed to see stocks with any positive momentum
MIN_RVOL = 1.5  # Relaxed to see stocks with above-average volume
MAX_FLOAT = 100_000_000  # Relaxed to see more stocks

# Cache for universe to avoid rate limiting
_universe_cache = None
_universe_cache_time = None
UNIVERSE_CACHE_DURATION = 1800  # 30 minutes in seconds


# ========== DATA LAYER (YFINANCE - FREE) ==========

def get_universe() -> List[str]:
    """
    Return a list of tickers to scan.
    Dynamically pulls top gainers, losers, and most active stocks daily.
    Cached for 30 minutes to avoid rate limiting.
    """
    global _universe_cache, _universe_cache_time
    
    # Check if we have a valid cache
    if _universe_cache is not None and _universe_cache_time is not None:
        age = time.time() - _universe_cache_time
        if age < UNIVERSE_CACHE_DURATION:
            print(f"Using cached universe ({len(_universe_cache)} stocks, {int(age/60)}min old)")
            return _universe_cache
    
    print("Refreshing universe from Yahoo Finance screeners...")
    tickers = set()
    
    # Base watchlist - popular volatile stocks
    base_watchlist = ["GME", "AMC", "PLTR", "SOFI", "RIVN", "LCID", "NIO", "TLRY", "SNDL"]
    tickers.update(base_watchlist)
    
    # Try to get daily movers from Yahoo Finance screener
    try:
        import pandas as pd
        
        # Add delay between requests to avoid rate limiting
        def fetch_with_delay(url, name):
            try:
                time.sleep(2)  # 2 second delay between requests
                tables = pd.read_html(url)
                if tables and len(tables) > 0:
                    df = tables[0]
                    if 'Symbol' in df.columns:
                        symbols = df['Symbol'].head(30).tolist()
                        tickers.update(symbols)
                        print(f"✓ Added {len(symbols)} {name}")
                        return True
            except Exception as e:
                print(f"✗ Could not fetch {name}: {e}")
                return False
        
        # Fetch each screener with delays
        fetch_with_delay("https://finance.yahoo.com/screener/predefined/day_gainers", "top gainers")
        fetch_with_delay("https://finance.yahoo.com/screener/predefined/day_losers", "top losers")
        fetch_with_delay("https://finance.yahoo.com/screener/predefined/most_actives", "most active")
            
    except Exception as e:
        print(f"Error fetching daily movers: {e}")
        print("Falling back to base watchlist only")
    
    ticker_list = list(tickers)
    print(f"Total universe: {len(ticker_list)} stocks (cached for 30 min)")
    
    # Update cache
    _universe_cache = ticker_list
    _universe_cache_time = time.time()
    
    return ticker_list


def get_intraday_quote(ticker: str) -> Dict:
    """Get current day's quote using yfinance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
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
        print(f"Error getting quote for {ticker}: {e}")
        return {}


def get_prev_close(ticker: str) -> float:
    """Get previous day's close"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if len(hist) < 2:
            return 0.0
        return float(hist['Close'].iloc[-2])
    except:
        return 0.0


def get_avg_volume(ticker: str, lookback: int = 20) -> int:
    """Get average volume over lookback period"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{lookback+5}d")
        if hist.empty:
            return 0
        return int(hist['Volume'].tail(lookback).mean())
    except:
        return 0


def get_float_shares(ticker: str) -> int:
    """Get float shares from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Try to get float shares (shares outstanding - closely held)
        float_shares = info.get('floatShares')
        if float_shares:
            return int(float_shares)
        
        # Fallback to shares outstanding
        shares = info.get('sharesOutstanding')
        if shares:
            return int(shares)
        
        return 0
    except:
        return 0


def has_breaking_news(ticker: str, lookback_minutes: int = 1440) -> bool:
    """Check if ticker has recent news (Yahoo Finance doesn't provide timestamps, so simplified)"""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        # If there's any news, consider it as having news (Yahoo doesn't give precise timestamps)
        return len(news) > 0 if news else False
    except:
        return False


def get_sector_moving(ticker: str) -> bool:
    """Simple stub: always False for now or map ticker→sector ETF and check its % change"""
    return False


def get_atr_values(ticker: str) -> Dict[str, float]:
    """Calculate ATR using daily candles"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="30d")
        
        if len(hist) < 20:
            return {"atr_today": 1.0, "atr_20": 1.0}
        
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


# ========== KPI + SCORING ==========

def calc_pct_change(price: float, open_price: float) -> float:
    return (price - open_price) / open_price * 100 if open_price else 0


def calc_gap_pct(open_price: float, prev_close: float) -> float:
    return (open_price - prev_close) / prev_close * 100 if prev_close else 0


def calc_relative_volume(volume: int, avg_volume: int) -> float:
    if avg_volume == 0:
        return 0
    return volume / avg_volume


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

    pct_change = calc_pct_change(price, open_price)
    gap_pct = calc_gap_pct(open_price, prev_close)
    rvol = calc_relative_volume(volume, avg_vol)
    turnover = calc_turnover(volume, float_shares)
    dollar_vol = calc_dollar_volume(price, volume)
    wick_ratio = calc_wick_ratio(high, low, open_price, price)
    atr_expansion = calc_atr_expansion(atr_vals["atr_today"], atr_vals["atr_20"])

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


def passes_base_filters(kpis: Dict) -> bool:
    if not (MIN_PRICE <= kpis["price"] <= MAX_PRICE):
        return False
    if kpis["pct_change"] < MIN_PCT_CHANGE:
        return False
    if kpis["relative_volume"] < MIN_RVOL:
        return False
    if kpis["float_shares"] >= MAX_FLOAT:
        return False
    # Temporarily removed news requirement to see all qualifying stocks
    # if not kpis["has_news"]:
    #     return False
    return True


def run_scan() -> List[Dict]:
    universe = get_universe()
    results = []

    for ticker in universe:
        try:
            kpis = compute_kpis(ticker)
            if not kpis:
                continue
            if not passes_base_filters(kpis):
                continue
            score = total_score(kpis)
            results.append({"ticker": ticker, "score": score, "kpis": kpis})
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


if __name__ == "__main__":
    print("Starting momentum scanner with Yahoo Finance (FREE)...")
    print(f"Filters: Price ${MIN_PRICE}-${MAX_PRICE}, %Change >{MIN_PCT_CHANGE}%, RVOL >{MIN_RVOL}x, Float <{MAX_FLOAT/1_000_000}M")
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
