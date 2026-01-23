"""Test the news API endpoint"""
import requests
import json

try:
    response = requests.get('http://localhost:5000/api/news', timeout=30)
    data = response.json()
    
    print(f"Status: {response.status_code}")
    print(f"News count: {len(data.get('news', []))}")
    
    if data.get('news'):
        print("\nFirst 3 news items:")
        for i, item in enumerate(data['news'][:3], 1):
            print(f"\n{i}. [{item['ticker']}] {item['title']}")
            print(f"   Publisher: {item['publisher']}")
            print(f"   Time: {item['ago']} ({item['timestamp']})")
    else:
        print("No news found")
        if 'error' in data:
            print(f"Error: {data['error']}")
            
except Exception as e:
    print(f"Error: {e}")
