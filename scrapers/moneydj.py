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
    # Basic0007B.xdjhtm displays all holdings instead of just the top 10
    url = f"https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid={etf_code}.TW"
    
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
        
        has_name = any('個股名稱' in h for h in headers)
        has_share = any('持有股數' in h for h in headers)
        
        if not has_name or not has_share:
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
        
    nav = get_nav_from_moneydj(etf_code)
    return holdings, nav

def get_nav_from_moneydj(etf_code):
    """
    Fetches the NAV for the given ETF code from MoneyDJ's NAV table page.
    """
    url = f"https://www.moneydj.com/ETF/X/Basic/Basic0003.xdjhtm?etfid={etf_code}.TW"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for td in soup.find_all('td'):
            if '淨值(' in td.text:
                nxt = td.find_next_sibling('td')
                if nxt:
                    m = re.search(r'([0-9.]+)', nxt.text)
                    if m:
                        return float(m.group(1))
    except Exception as e:
        print(f"Error fetching NAV for {etf_code} from MoneyDJ: {e}")
    return None

