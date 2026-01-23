"""
Alpaca Data Source for Momentum Scanner
Provides unlimited rate-free market data via Alpaca Markets API
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Alpaca clients
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')

# Initialize data client (no auth needed for free data)
data_client = None
trading_client = None

if ALPACA_API_KEY and ALPACA_SECRET_KEY:
    data_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    print("✅ Alpaca API initialized successfully")
else:
    print("⚠️  Alpaca API keys not found. Using fallback data source.")


def get_most_active_stocks(limit: int = 200) -> List[str]:
    """
    Get most active stocks by volume.
    Alpaca doesn't have a direct screener, so we'll use a different approach:
    - Get all US equities
    - Fetch snapshots with volume data
    - Sort by volume
    """
    if not trading_client:
        return []
    
    try:
        # Get tradable US stocks
        search_params = GetAssetsRequest(
            asset_class=AssetClass.US_EQUITY,
            status='active'
        )
        assets = trading_client.get_all_assets(search_params)
        
        # Filter to reasonable price range and exclude certain types
        tickers = [
            asset.symbol for asset in assets 
            if asset.tradable 
            and asset.easy_to_borrow 
            and not asset.symbol.endswith('W')  # Exclude warrants
            and len(asset.symbol) <= 5  # Exclude complex tickers
        ]
        
        # Limit to first 500 for performance
        tickers = tickers[:500]
        
        # Get snapshots to find volume leaders
        if data_client and tickers:
            request = StockSnapshotRequest(symbol_or_symbols=tickers)
            snapshots = data_client.get_stock_snapshot(request)
            
            # Sort by volume
            volume_data = []
            for symbol, snapshot in snapshots.items():
                if snapshot.daily_bar and snapshot.daily_bar.volume:
                    volume_data.append((symbol, snapshot.daily_bar.volume))
            
            volume_data.sort(key=lambda x: x[1], reverse=True)
            return [symbol for symbol, _ in volume_data[:limit]]
        
        return tickers[:limit]
        
    except Exception as e:
        print(f"Error getting most active stocks: {e}")
        return []


def get_market_movers(limit: int = 30) -> Dict[str, List[str]]:
    """
    Get top gainers and losers.
    Since Alpaca doesn't have a direct screener, we'll scan a universe of stocks.
    Returns: {'gainers': [...], 'losers': [...]}
    """
    if not data_client:
        return {'gainers': [], 'losers': []}
    
    try:
        # Get active stocks
        active = get_most_active_stocks(100)
        
        if not active:
            return {'gainers': [], 'losers': []}
        
        # Get daily bars to calculate % change
        request = StockBarsRequest(
            symbol_or_symbols=active,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=5),
            limit=2
        )
        
        bars = data_client.get_stock_bars(request)
        
        # Calculate percent changes
        changes = []
        for symbol in active:
            if symbol in bars:
                symbol_bars = bars[symbol]
                if len(symbol_bars) >= 2:
                    prev_close = symbol_bars[-2].close
                    curr_close = symbol_bars[-1].close
                    pct_change = ((curr_close - prev_close) / prev_close) * 100
                    changes.append((symbol, pct_change))
        
        # Sort by % change
        changes.sort(key=lambda x: x[1], reverse=True)
        
        gainers = [symbol for symbol, _ in changes[:limit]]
        losers = [symbol for symbol, _ in changes[-limit:]]
        
        return {'gainers': gainers, 'losers': losers}
        
    except Exception as e:
        print(f"Error getting market movers: {e}")
        return {'gainers': [], 'losers': []}


def get_quote(symbol: str) -> Optional[Dict]:
    """
    Get latest quote data for a symbol.
    Returns dict with: price, volume, high, low, prev_close
    """
    if not data_client:
        return None
    
    try:
        # Get snapshot which includes latest quote and daily bar
        request = StockSnapshotRequest(symbol_or_symbols=[symbol])
        snapshot = data_client.get_stock_snapshot(request)
        
        if symbol not in snapshot:
            return None
        
        snap = snapshot[symbol]
        
        # Build quote data
        quote_data = {
            'symbol': symbol,
            'price': snap.latest_trade.price if snap.latest_trade else None,
            'open': snap.daily_bar.open if snap.daily_bar else None,
            'volume': snap.daily_bar.volume if snap.daily_bar else 0,
            'high': snap.daily_bar.high if snap.daily_bar else None,
            'low': snap.daily_bar.low if snap.daily_bar else None,
            'prev_close': snap.previous_daily_bar.close if snap.previous_daily_bar else None,
            'timestamp': snap.latest_trade.timestamp if snap.latest_trade else None
        }
        
        return quote_data
        
    except Exception as e:
        print(f"Error getting quote for {symbol}: {e}")
        return None


def get_intraday_bars(symbol: str, minutes: int = 60) -> Optional[pd.DataFrame]:
    """
    Get intraday minute bars for calculating RVOL.
    Returns DataFrame with columns: timestamp, open, high, low, close, volume
    """
    if not data_client:
        return None
    
    try:
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Minute,
            start=datetime.now() - timedelta(minutes=minutes),
            limit=minutes
        )
        
        bars = data_client.get_stock_bars(request)
        
        if symbol not in bars:
            return None
        
        symbol_bars = bars[symbol]
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            }
            for bar in symbol_bars
        ])
        
        return df
        
    except Exception as e:
        print(f"Error getting intraday bars for {symbol}: {e}")
        return None


def get_avg_volume(symbol: str, lookback_days: int = 20) -> int:
    """Get average daily volume over lookback period using Alpaca."""
    import yfinance as yf
    if not data_client:
        print(f"[RVOL DEBUG] No data_client for {symbol}")
        # Fallback to yfinance
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period=f"{lookback_days+5}d")
            if hist.empty:
                print(f"[RVOL DEBUG] yfinance: No history for {symbol}")
                return 0
            avg = int(hist['Volume'].tail(lookback_days).mean())
            print(f"[RVOL DEBUG] yfinance: {symbol} avg_volume={avg}")
            return avg
        except Exception as e:
            print(f"[RVOL DEBUG] yfinance error for {symbol}: {e}")
            return 0

    try:
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=lookback_days + 5),
            limit=lookback_days + 5
        )

        bars = data_client.get_stock_bars(request)

        if symbol not in bars:
            print(f"[RVOL DEBUG] No bars returned for {symbol}, falling back to yfinance")
            # Fallback to yfinance
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period=f"{lookback_days+5}d")
                if hist.empty:
                    print(f"[RVOL DEBUG] yfinance: No history for {symbol}")
                    return 0
                avg = int(hist['Volume'].tail(lookback_days).mean())
                print(f"[RVOL DEBUG] yfinance: {symbol} avg_volume={avg}")
                return avg
            except Exception as e:
                print(f"[RVOL DEBUG] yfinance error for {symbol}: {e}")
                return 0

        symbol_bars = bars[symbol]
        if len(symbol_bars) < lookback_days:
            volumes = [bar.volume for bar in symbol_bars]
        else:
            volumes = [bar.volume for bar in symbol_bars[-lookback_days:]]

        print(f"[RVOL DEBUG] {symbol}: volumes={volumes}")

        if not volumes:
            print(f"[RVOL DEBUG] No volumes for {symbol}, falling back to yfinance")
            # Fallback to yfinance
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period=f"{lookback_days+5}d")
                if hist.empty:
                    print(f"[RVOL DEBUG] yfinance: No history for {symbol}")
                    return 0
                avg = int(hist['Volume'].tail(lookback_days).mean())
                print(f"[RVOL DEBUG] yfinance: {symbol} avg_volume={avg}")
                return avg
            except Exception as e:
                print(f"[RVOL DEBUG] yfinance error for {symbol}: {e}")
                return 0

        avg = int(sum(volumes) / len(volumes))
        print(f"[RVOL DEBUG] {symbol}: avg_volume={avg}")
        return avg

    except Exception as e:
        print(f"Error getting avg volume for {symbol}: {e}")
        # Fallback to yfinance
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period=f"{lookback_days+5}d")
            if hist.empty:
                print(f"[RVOL DEBUG] yfinance: No history for {symbol}")
                return 0
            avg = int(hist['Volume'].tail(lookback_days).mean())
            print(f"[RVOL DEBUG] yfinance: {symbol} avg_volume={avg}")
            return avg
        except Exception as e2:
            print(f"[RVOL DEBUG] yfinance error for {symbol}: {e2}")
            return 0


def get_daily_bars(symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
    """
    Get daily bars for ATR and other calculations.
    Returns DataFrame with columns: timestamp, open, high, low, close, volume
    """
    if not data_client:
        return None
    
    try:
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=days + 5),
            limit=days + 5
        )
        
        bars = data_client.get_stock_bars(request)
        
        if symbol not in bars:
            return None
        
        symbol_bars = bars[symbol]
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            }
            for bar in symbol_bars
        ])
        
        return df
        
    except Exception as e:
        print(f"Error getting daily bars for {symbol}: {e}")
        return None


def is_alpaca_available() -> bool:
    """Check if Alpaca API is properly configured."""
    return data_client is not None and trading_client is not None
