import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_yahoo_price(stock_id):
    import time
    for suffix in ['', '.TW', '.TWO']:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_id}{suffix}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                data = res.json()
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                return float(price)
        except Exception:
            pass
        time.sleep(0.1)
    return 0.0

def send_alert(price):
    if not WEBHOOK_URL:
        print("Warning: No webhook URL configured. Skipping Discord notification.")
        return

    now = datetime.now()
    if now.hour < 8:
        print(f"Time is before 8 AM ({now.strftime('%H:%M')}). Skipping Discord notification for Oil alert.")
        return

    msg = f"🛢️ **【布蘭特原油價格警報】**\n目前價格來到 **${price:.2f}**\n👉 (觸發條件: < $80 或 > $100)\n資料來源: Yahoo Finance"
    
    payload = {
        "content": msg,
        "username": "原油追蹤機器人"
    }
    res = requests.post(WEBHOOK_URL, json=payload)
    if res.status_code not in (200, 204):
        print(f"Failed to send to discord: {res.status_code} - {res.text}")
    else:
        print("Successfully sent Discord notification for Oil alert!")

def main():
    print("Fetching Brent Crude Oil price (BZ=F)...")
    price = fetch_yahoo_price("BZ=F")
    if price == 0.0:
        print("Failed to fetch Brent Crude Oil price.")
        return
        
    print(f"Current Brent Crude Oil Price: ${price:.2f}")
    if price < 80 or price > 100:
        print("Price alert threshold met! Sending notification...")
        send_alert(price)
    else:
        print("Price is within normal range ($80 - $100). No alert needed.")

if __name__ == "__main__":
    main()
