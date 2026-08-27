import requests
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
}

def fetch_holdings(config, fetch_yahoo_price_func):
    """
    Fetches data from Cathay (國泰投信)
    """
    fund_code = config.get("fund_code")
    result = None
    target_date_str = ""
    
    for i in range(10):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://cwapi.cathaysite.com.tw/api/ETF/GetETFDetailStockList?FundCode={fund_code}&SearchDate={d}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("result"):
                result = data["result"]
                target_date_str = d
                break
                
    if not result:
        raise ValueError(f"No data returned for {config['code']} in the past 10 days.")
        
    holdings = {}
    for st in result:
        code = st.get("stockCode")
        if not code:
            continue
        share_str = st.get("volumn", "0").replace(",", "")
        weight_str = st.get("weights", "0.0")
        
        share = float(share_str)
        weight = float(weight_str)
        price = fetch_yahoo_price_func(code) if fetch_yahoo_price_func else 0.0
        amount = share * price
        
        holdings[code] = {
            "name": st.get("stockName", ""),
            "share": share,
            "weight": weight,
            "price": price,
            "amount": amount
        }
        
    try:
        from scrapers.moneydj import get_nav_from_moneydj
        nav = get_nav_from_moneydj(config.get("code"))
    except ImportError:
        nav = None
        
    return holdings, nav
