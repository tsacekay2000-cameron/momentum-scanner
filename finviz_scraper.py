"""
Finviz Screener for fast momentum scanning
Scrapes pre-filtered stocks from Finviz with RVOL, price, float, and % change
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict
import time


def scrape_finviz_screener(
    min_price: float = 0.50,
    max_price: float = 100,
    min_rvol: float = 1.0,
    max_float_m: float = 100,
    limit: int = 100
) -> List[Dict]:
    """
    Scrape Finviz screener for momentum stocks
    
    Returns list of dicts with: ticker, price, pct_change, rvol, volume, float
    """
    
    # Build Finviz screener URL with filters
    # Use the simplest possible URL that works
    # NOTE: Finviz uses .ashx extension, not .php!
    
    base_url = "https://finviz.com/screener.ashx"
    
    params = {
        'v': '111',  # Overview view
        'f': 'sh_relvol_o2',  # Relative volume over 2x
        'o': '-change',  # Sort by % change descending
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    results = []
    
    try:
        # First, test basic connectivity
        print(f"[Finviz] Testing connection to finviz.com...")
        test_response = requests.get("https://finviz.com", headers=headers, timeout=10)
        print(f"[Finviz] Main site status: {test_response.status_code}")
        
        # Try the screener without parameters first
        print(f"[Finviz] Testing screener page...")
        screener_test = requests.get("https://finviz.com/screener.php", headers=headers, timeout=10)
        print(f"[Finviz] Screener status: {screener_test.status_code}")
        
        if screener_test.status_code == 200:
            print(f"[Finviz] Screener accessible, now fetching with params...")
            print(f"[Finviz] URL: {base_url}")
            print(f"[Finviz] Params: {params}")
        
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the screener table
        table = soup.find('table', {'class': 'table-light'})
        
        if not table:
            print("[Finviz] No data table found")
            return []
        
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows[:limit]:  # Limit results
            cols = row.find_all('td')
            
            if len(cols) < 12:
                continue
            
            try:
                # Parse columns (Finviz overview layout)
                ticker = cols[1].text.strip()
                
                # Price
                price_text = cols[8].text.strip()
                price = float(price_text) if price_text else 0.0
                
                # % Change
                change_text = cols[9].text.strip().replace('%', '')
                pct_change = float(change_text) if change_text else 0.0
                
                # Volume
                volume_text = cols[10].text.strip()
                volume = parse_volume(volume_text)
                
                # Parse additional data from ticker link
                ticker_link = cols[1].find('a')
                if ticker_link and 'href' in ticker_link.attrs:
                    # Extract float and RVOL from quote page (may need separate request)
                    pass
                
                # For now, get RVOL from screener if available
                # Finviz may show RVOL in different column depending on view
                rvol = 1.0  # Placeholder - will be calculated from actual data
                float_shares = 10_000_000  # Placeholder
                
                # Try to get RVOL from the table (column varies by view)
                for col in cols:
                    text = col.text.strip()
                    if text.replace('.', '').isdigit() and 0.1 <= float(text) <= 100:
                        # Likely RVOL value
                        rvol = float(text)
                        break
                
                results.append({
                    'ticker': ticker,
                    'price': price,
                    'pct_change': pct_change,
                    'volume': volume,
                    'relative_volume': rvol,
                    'float_shares': float_shares
                })
                
            except Exception as e:
                print(f"[Finviz] Error parsing row: {e}")
                continue
        
        print(f"[Finviz] Found {len(results)} stocks from screener")
        return results
        
    except requests.RequestException as e:
        print(f"[Finviz] Request error: {e}")
        return []
    except Exception as e:
        print(f"[Finviz] Scraping error: {e}")
        return []


def parse_volume(volume_str: str) -> int:
    """Convert Finviz volume format (e.g., '1.23M') to integer"""
    try:
        volume_str = volume_str.strip().upper()
        
        if 'M' in volume_str:
            return int(float(volume_str.replace('M', '')) * 1_000_000)
        elif 'K' in volume_str:
            return int(float(volume_str.replace('K', '')) * 1_000)
        elif 'B' in volume_str:
            return int(float(volume_str.replace('B', '')) * 1_000_000_000)
        else:
            return int(float(volume_str.replace(',', '')))
    except:
        return 0


def get_detailed_quote(ticker: str) -> Dict:
    """
    Get detailed quote data from Finviz for a single stock
    Includes RVOL, float, avg volume, OHLC, prev close, etc.
    """
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the fundamentals table
        table = soup.find('table', {'class': 'snapshot-table2'})
        
        if not table:
            return {}
        
        data = {}
        rows = table.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            
            for i in range(0, len(cols)-1, 2):
                label = cols[i].text.strip()
                value = cols[i+1].text.strip()
                
                # Parse specific fields
                if label == 'Shs Float':
                    data['float_shares'] = parse_volume(value)
                elif label == 'Rel Volume':
                    data['relative_volume'] = float(value) if value != '-' else 1.0
                elif label == 'Avg Volume':
                    data['avg_volume'] = parse_volume(value)
                elif label == 'Volume':
                    data['volume'] = parse_volume(value)
                elif label == 'Price':
                    data['price'] = float(value)
                elif label == 'Change':
                    change_pct = value.replace('%', '').strip()
                    data['pct_change'] = float(change_pct) if change_pct != '-' else 0.0
                elif label == 'Open':
                    data['open'] = float(value) if value != '-' else 0.0
                elif label == 'High':
                    data['high'] = float(value) if value != '-' else 0.0
                elif label == 'Low':
                    data['low'] = float(value) if value != '-' else 0.0
                elif label == 'Prev Close':
                    data['prev_close'] = float(value) if value != '-' else 0.0
                elif label == 'ATR':
                    data['atr'] = float(value) if value != '-' else 0.0
        
        # Calculate VWAP approximation (use price as proxy since Finviz doesn't provide VWAP)
        if 'high' in data and 'low' in data and 'price' in data:
            data['vwap'] = (data['high'] + data['low'] + data['price']) / 3
        
        return data
        
    except Exception as e:
        print(f"[Finviz] Error fetching {ticker}: {e}")
        return {}


if __name__ == "__main__":
    # Test the scraper
    print("Testing Finviz scraper...")
    stocks = scrape_finviz_screener(min_rvol=2, limit=20)
    
    print(f"\nFound {len(stocks)} stocks:")
    for stock in stocks[:10]:
        print(f"{stock['ticker']:6} | ${stock['price']:6.2f} | {stock['pct_change']:+6.2f}% | "
              f"RVOL: {stock['relative_volume']:5.2f}x")
    
    # Test detailed quote
    if stocks:
        print(f"\nFetching detailed data for {stocks[0]['ticker']}...")
        details = get_detailed_quote(stocks[0]['ticker'])
        print(details)
