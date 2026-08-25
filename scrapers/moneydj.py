import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
}

def fetch_holdings(config, fetch_yahoo_price_func):
    """
    Fetches data from MoneyDJ
    """
    etf_code = config.get("code")
    url = f"https://www.moneydj.com/ETF/X/Basic/Basic0007.xdjhtm?etfid={etf_code}.TW"
    
    res = requests.get(url, headers=HEADERS, timeout=15)
    if res.status_code != 200:
        raise ValueError(f"Failed to fetch data from MoneyDJ for {etf_code}: HTTP {res.status_code}")
        
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    
    holdings = {}
    found_table = False
    
    for table in soup.find_all('table'):
        # Usually MoneyDJ's holding table has class 'datalist'
        if not table.get('class') or 'datalist' not in table.get('class', []):
            continue
            
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue
            
        # Verify it's the right table by checking headers
        headers = [th.text.strip() for th in rows[0].find_all('th')]
        if '個股名稱' not in headers or '持有股數' not in headers:
            continue
            
        found_table = True
        for tr in rows[1:]:
            tds = tr.find_all('td')
            if len(tds) < 3:
                continue
                
            name_code_str = tds[0].text.strip()
            weight_str = tds[1].text.strip()
            share_str = tds[2].text.strip()
            
            # Extract code using regex
            m = re.search(r'\((\d+)\.TW\)', name_code_str)
            if not m:
                continue
                
            code = m.group(1)
            name = name_code_str.split('(')[0].strip()
            
            try:
                weight = float(weight_str)
                share = float(share_str.replace(",", ""))
            except ValueError:
                continue
                
            price = fetch_yahoo_price_func(code) if fetch_yahoo_price_func else 0.0
            amount = share * price
            
            holdings[code] = {
                "name": name,
                "share": share,
                "weight": weight,
                "price": price,
                "amount": amount
            }
        break
            
    if not found_table or not holdings:
        raise ValueError(f"No holding data found on MoneyDJ for {etf_code}. It might not be listed yet.")
        
    # MoneyDJ doesn't provide NAV easily on this exact HTML segment, so we pass None
    return holdings, None
