import requests
from bs4 import BeautifulSoup
import json
import logging

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
}

def fetch_holdings(config, fetch_yahoo_price_func=None):
    """
    Fetches data from ezmoney (統一投信)
    """
    fund_code = config.get("fund_code")
    url = f"https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode={fund_code}"
    
    res = requests.get(url, headers=HEADERS, timeout=10)
    if res.status_code != 200:
        raise ValueError(f"Failed to fetch data for {config['code']}: HTTP {res.status_code}")
        
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # get nav
    nav = 0.0
    nav_div = soup.find('div', class_='Net-num')
    if nav_div:
        nav_str = nav_div.text.strip().replace(",", "")
        try:
            nav = float(nav_str)
        except:
            pass
            
    # get holdings
    data_div = soup.find('div', id='DataAsset')
    if not data_div:
        raise ValueError("Could not find DataAsset div in HTML. Structure might have changed.")
        
    data_content = data_div.get('data-content')
    if not data_content:
        raise ValueError("No data-content attribute found.")
        
    data = json.loads(data_content)
    stock_group = next((item for item in data if item.get('AssetCode') == 'ST'), None)
    
    if not stock_group or 'Details' not in stock_group:
        raise ValueError("No stock details found in data.")
        
    holdings = {}
    for st in stock_group['Details']:
        code = st.get('DetailCode')
        if not code:
            continue
            
        share = float(st.get("Share", 0))
        weight = float(st.get("NavRate", 0))
        amount = float(st.get("Amount", 0))
        price = 0.0
        if share > 0:
            price = amount / share
            
        holdings[code] = {
            "name": st.get("DetailName", ""),
            "share": share,
            "weight": weight,
            "amount": amount,
            "price": price
        }
        
    return holdings, nav
