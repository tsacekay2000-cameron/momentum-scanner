"""Simple test to run just the Flask app"""
from web_scanner import app, scan_stocks
from threading import Thread

if __name__ == '__main__':
    # Start background scanner
    scanner_thread = Thread(target=scan_stocks, daemon=True)
    scanner_thread.start()
    
    print("Starting simple Flask server...")
    print("Background scanner started...")
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
