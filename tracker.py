import os
import json
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
HEADERS = {"User-Agent": "Mozilla/5.0"}
DB_PATH = "tracker.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_nav (
            date TEXT,
            etf_code TEXT,
            nav REAL,
            PRIMARY KEY (date, etf_code)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_holdings (
            date TEXT,
            etf_code TEXT,
            stock_code TEXT,
            name TEXT,
            share REAL,
            weight REAL,
            amount REAL,
            price REAL,
            PRIMARY KEY (date, etf_code, stock_code)
        )
    ''')
    
    cursor.execute("PRAGMA table_info(daily_holdings)")
    columns = [col[1] for col in cursor.fetchall()]
    if "avg_price" not in columns:
        cursor.execute("ALTER TABLE daily_holdings ADD COLUMN avg_price REAL DEFAULT 0.0")

    conn.commit()
    return conn

def fetch_yahoo_price(stock_id):
    import time
    for suffix in ['.TW', '.TWO']:
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

def fetch_00981A_data():
    url = "https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW"
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    data_div = soup.find("div", id="DataAsset")
    if not data_div:
        raise ValueError("Could not find div#DataAsset in HTML")
    
    raw_data = data_div.get("data-content")
    if not raw_data:
        raise ValueError("div#DataAsset does not have 'data-content' attribute")
        
    data = json.loads(raw_data)
    
    nav = None
    for item in data:
        if item.get("AssetName") == "每單位淨值":
            nav = float(item.get("Value", 0.0))
def fetch_ezmoney_data(fund_code):
    url = f"https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode={fund_code}"
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    data_div = soup.find("div", id="DataAsset")
    if not data_div:
        raise ValueError("Could not find div#DataAsset in HTML")
    
    raw_data = data_div.get("data-content")
    if not raw_data:
        raise ValueError("div#DataAsset does not have 'data-content' attribute")
        
    data = json.loads(raw_data)
    
    nav = None
    for item in data:
        if item.get("AssetName") == "每單位淨值":
            nav = float(item.get("Value", 0.0))
            break
            
    stock_group = next((item for item in data if item.get("AssetCode") == "ST"), None)
    if not stock_group or "Details" not in stock_group:
        raise ValueError("Could not find stock details in data")
        
    stocks = stock_group["Details"]
    holdings = {}
    for st in stocks:
        code = st.get("DetailCode")
        if not code:
            continue
        share = float(st.get("Share", 0))
        amount = float(st.get("Amount", 0))
        price = amount / share if share > 0 else 0.0
        holdings[code] = {
            "name": st.get("DetailName", ""),
            "share": share,
            "weight": float(st.get("NavRate", 0.0)),
            "amount": amount,
            "price": price
        }
    return holdings, nav

def fetch_00400A_data():
    from datetime import timedelta
    result = None
    target_date_str = ""
    
    for i in range(10):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://cwapi.cathaysite.com.tw/api/ETF/GetETFDetailStockList?FundCode=EA&SearchDate={d}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("result"):
                result = data["result"]
                target_date_str = d
                break
                
    if not result:
        raise ValueError("No data returned for 00400A in the past 10 days.")
        
    holdings = {}
    for st in result:
        code = st.get("stockCode")
        if not code:
            continue
        share_str = st.get("volumn", "0").replace(",", "")
        weight_str = st.get("weights", "0.0")
        
        share = float(share_str)
        weight = float(weight_str)
        price = fetch_yahoo_price(code)
        amount = share * price
        
        holdings[code] = {
            "name": st.get("stockName", ""),
            "share": share,
            "weight": weight,
            "price": price,
            "amount": amount
        }
    return holdings, None

def load_previous_data(conn, etf_code, today_str):
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT date FROM daily_holdings WHERE etf_code = ? AND date < ? ORDER BY date DESC LIMIT 1', (etf_code, today_str))
    row = cursor.fetchone()
    if not row:
        return None
    
    prev_date = row[0]
    
    cursor.execute('SELECT stock_code, name, share, weight, amount, price, avg_price FROM daily_holdings WHERE etf_code = ? AND date = ?', (etf_code, prev_date))
    holdings = {}
    for r in cursor.fetchall():
        holdings[r[0]] = {
            "name": r[1],
            "share": r[2],
            "weight": r[3],
            "amount": r[4],
            "price": r[5],
            "avg_price": r[6]
        }
        
    cursor.execute('SELECT nav FROM daily_nav WHERE etf_code = ? AND date = ?', (etf_code, prev_date))
    nav_row = cursor.fetchone()
    prev_nav = nav_row[0] if nav_row else None
    
    return {
        "date": prev_date,
        "current": holdings,
        "current_nav": prev_nav
    }

def save_to_db(conn, etf_code, date_str, holdings, nav):
    cursor = conn.cursor()
    if nav is not None:
        cursor.execute('INSERT OR REPLACE INTO daily_nav (date, etf_code, nav) VALUES (?, ?, ?)', (date_str, etf_code, nav))
    
    for code, data in holdings.items():
        cursor.execute('''
            INSERT OR REPLACE INTO daily_holdings 
            (date, etf_code, stock_code, name, share, weight, amount, price, avg_price) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date_str, etf_code, code, data.get("name"), data.get("share"), data.get("weight"), data.get("amount", 0.0), data.get("price", 0.0), data.get("avg_price", 0.0)))
    conn.commit()

def save_json_data(file_name, data):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def compare_data(prev, curr):
    changes = {
        "added": [],
        "removed": [],
        "changed": []
    }
    
    if not prev:
        for k, c in curr.items():
            c["avg_price"] = c.get("price", 0.0)
        return changes
        
    prev_keys = set(prev.keys())
    curr_keys = set(curr.keys())
    
    for k in curr_keys - prev_keys:
        c = curr[k]
        c["avg_price"] = c.get("price", 0.0)
        changes["added"].append(c)
        
    for k in prev_keys - curr_keys:
        p = prev[k]
        changes["removed"].append(p)
        
    for k in curr_keys.intersection(prev_keys):
        p = prev[k]
        c = curr[k]
        
        old_avg_price = p.get("avg_price", p.get("price", c.get("price", 0.0)))
        curr_price = c.get("price", 0.0)
        
        share_diff = c["share"] - p["share"]
        weight_diff = c["weight"] - p["weight"]
        
        if share_diff > 0:
            if c["share"] > 0:
                new_avg_price = (p["share"] * old_avg_price + share_diff * curr_price) / c["share"]
            else:
                new_avg_price = curr_price
        else:
            new_avg_price = old_avg_price
            
        c["avg_price"] = new_avg_price
        
        if share_diff != 0:
            trade_value = share_diff * curr_price
            price_diff = 0.0
            if "price" in p and p["price"] > 0:
                price_diff = curr_price - p["price"]
                
            realized_pnl = 0.0
            if share_diff < 0:
                realized_pnl = abs(share_diff) * (curr_price - old_avg_price)
                
            changes["changed"].append({
                "code": k,
                "name": c["name"],
                "prev_share": p["share"],
                "curr_share": c["share"],
                "share_diff": share_diff,
                "prev_weight": p["weight"],
                "curr_weight": c["weight"],
                "weight_diff": weight_diff,
                "price": curr_price,
                "trade_value": trade_value,
                "price_diff": price_diff,
                "avg_price": new_avg_price,
                "old_avg_price": old_avg_price,
                "realized_pnl": realized_pnl
            })
            
    changes["changed"] = sorted(changes["changed"], key=lambda x: x["weight_diff"], reverse=True)
    return changes

def send_discord_notification(etf_name, curr_holdings, changes, is_first_run=False, curr_nav=None, prev_nav=None):
    if not WEBHOOK_URL:
        print("Warning: No webhook URL configured. Skipping Discord notification.")
        return
        
    now = datetime.now()
    if now.hour < 8:
        print(f"Time is before 8 AM ({now.strftime('%H:%M')}). Skipping Discord notification for {etf_name}.")
        return

    today_str = now.strftime("%Y-%m-%d")
    msg = ""
    
    nav_str = ""
    if curr_nav is not None:
        if prev_nav is not None and prev_nav != curr_nav:
            nav_diff = curr_nav - prev_nav
            sign = "+" if nav_diff > 0 else ""
            nav_str = f" | 最新淨值: {curr_nav:.4f} ({sign}{nav_diff:.4f})"
        else:
            nav_str = f" | 最新淨值: {curr_nav:.4f}"
            
    if is_first_run:
        msg = f"🎉 **【{etf_name}】** 首次建立資料庫 ({today_str}){nav_str}\n"
        msg += f"目前共有 {len(curr_holdings)} 檔成分股。\n"
    else:
        if not changes["added"] and not changes["removed"] and not changes["changed"]:
            msg = f"📊 **【{etf_name}】** 今日 ({today_str}) 持股無變動。{nav_str}\n"
        else:
            msg = f"📊 **【{etf_name}】** 今日 ({today_str}) 持股變動報告{nav_str}\n"
            
            if changes["added"]:
                msg += "\n🟢 **【新增成分股】**\n"
                for st in changes["added"]:
                    price_str = f" | 買進價格: {st.get('price', 0):.2f}" if st.get('price', 0) > 0 else ""
                    msg += f"+ {st['name']} (權重: {st['weight']}%, {st['share']:,.0f} 股){price_str}\n"
                    
            if changes["removed"]:
                msg += "\n🔴 **【剔除成分股】**\n"
                for st in changes["removed"]:
                    old_avg = st.get('avg_price', st.get('price', 0.0))
                    sell_price = st.get('price', 0.0)
                    pnl = 0.0
                    pnl_str = ""
                    if old_avg > 0 and sell_price > 0:
                        pnl = st['share'] * (sell_price - old_avg)
                        pnl_sign = "獲利" if pnl >= 0 else "虧損"
                        pnl_str = f" (估計{pnl_sign}約 {abs(pnl)/10000:,.0f} 萬)"
                        
                    msg += f"- {st['name']} (原權重: {st['weight']}%, 原股數: {st['share']:,.0f} 股){pnl_str}\n"
                    
            if changes["changed"]:
                msg += "\n🔄 **【持股異動】** (依權重變化排序)\n"
                total_buy = 0
                total_sell = 0
                total_pnl = 0
                for st in changes["changed"]:
                    share_diff = st['share_diff']
                    w_diff = st['weight_diff']
                    sign = "+" if share_diff > 0 else ""
                    
                    trade_val_str = ""
                    if 'trade_value' in st and st['trade_value'] != 0:
                        trade_val = st['trade_value']
                        if trade_val > 0:
                            total_buy += trade_val
                            avg_p = st.get('avg_price', 0)
                            trade_val_str = f" | 買進約 {trade_val/10000:,.0f} 萬 (均價來到 {avg_p:.2f})" if avg_p > 0 else f" | 買進約 {trade_val/10000:,.0f} 萬"
                        else:
                            total_sell += abs(trade_val)
                            pnl = st.get('realized_pnl', 0)
                            total_pnl += pnl
                            pnl_sign = "獲利" if pnl >= 0 else "虧損"
                            trade_val_str = f" | 賣出約 {abs(trade_val)/10000:,.0f} 萬 ({pnl_sign}約 {abs(pnl)/10000:,.0f} 萬)" if pnl != 0 else f" | 賣出約 {abs(trade_val)/10000:,.0f} 萬"
                            
                    price_str = ""
                    if 'price' in st and st['price'] > 0:
                        price_str = f" | 收盤價 {st['price']:.2f}"
                        if 'price_diff' in st and st['price_diff'] != 0:
                            p_sign = "+" if st['price_diff'] > 0 else ""
                            price_str += f" ({p_sign}{st['price_diff']:.2f})"
                            
                    msg += f"• **{st['name']}**: 股數 {sign}{share_diff:,.0f} 股 | 權重 {st['prev_weight']:.2f}% ➔ {st['curr_weight']:.2f}% ({w_diff:+.2f}%){price_str}{trade_val_str}\n"

                if total_buy > 0 or total_sell > 0:
                    net_trade = total_buy - total_sell
                    net_sign = "+" if net_trade > 0 else ""
                    msg += f"\n💰 **【今日異動估算金額】**\n"
                    msg += f"- 總買進金額: 約 {total_buy/10000:,.0f} 萬\n"
                    msg += f"- 總賣出金額: 約 {total_sell/10000:,.0f} 萬\n"
                    if total_sell > 0:
                        pnl_sign_total = "獲利" if total_pnl >= 0 else "虧損"
                        msg += f"- 賣出總損益: {pnl_sign_total}約 {abs(total_pnl)/10000:,.0f} 萬\n"
                    msg += f"- 淨買賣金額: 約 {net_sign}{net_trade/10000:,.0f} 萬\n"

    msg += "\n🌐 **查看完整持股與詳細資訊：**\n"
    msg += "👉 https://andyhsu0717.github.io/etf-tracker/\n"

    chunks = []
    curr_chunk = ""
    for line in msg.split('\n'):
        if len(curr_chunk) + len(line) + 1 > 1900:
            chunks.append(curr_chunk)
            curr_chunk = line + "\n"
        else:
            curr_chunk += line + "\n"
            
    if curr_chunk.strip():
        chunks.append(curr_chunk)

    for chunk in chunks:
        payload = {
            "content": chunk,
            "username": "ETF 追蹤機器人"
        }
        res = requests.post(WEBHOOK_URL, json=payload)
        if res.status_code not in (200, 204):
            print(f"Failed to send to discord for {etf_name}: {res.status_code} - {res.text}")
        else:
            print(f"Successfully sent Discord notification chunk for {etf_name}!")

def process_etf(conn, etf_code, etf_name, fetch_func, json_file_name):
    print(f"\n--- Processing {etf_name} ---")
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        print("Fetching current data...")
        curr_holdings, curr_nav = fetch_func()
        
        print("Loading previous data from DB...")
        prev_data = load_previous_data(conn, etf_code, today_str)
        
        is_first_run = (prev_data is None)
        prev_nav = None
        
        if is_first_run:
            changes = compare_data(None, curr_holdings)
            json_export = {
                "date": today_str,
                "current": curr_holdings,
                "previous": curr_holdings,
                "current_nav": curr_nav,
                "previous_nav": curr_nav
            }
        else:
            baseline = prev_data["current"]
            prev_nav = prev_data.get("current_nav")
            print("Comparing data...")
            changes = compare_data(baseline, curr_holdings)
            
            json_export = {
                "date": today_str,
                "current": curr_holdings,
                "previous": baseline,
                "current_nav": curr_nav,
                "previous_nav": prev_nav
            }
            
        print("Sending Discord notification...")
        send_discord_notification(etf_name, curr_holdings, changes, is_first_run, curr_nav, prev_nav)
        
        print("Saving current data to DB...")
        save_to_db(conn, etf_code, today_str, curr_holdings, curr_nav)
        
        print("Exporting to JSON for Web UI...")
        save_json_data(json_file_name, json_export)
        
        print(f"{etf_name} processed successfully.")
    except Exception as e:
        print(f"An error occurred while processing {etf_name}: {e}")

def main():
    conn = init_db()
    
    import importlib
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            etfs = json.load(f)
    except FileNotFoundError:
        print("config.json not found")
        return
        
    for etf in etfs:
        code = etf['code']
        name = f"{code} {etf['name']}"
        scraper_name = etf['scraper']
        json_file_name = f"{code}_holdings.json"
        
        try:
            module = importlib.import_module(f"scrapers.{scraper_name}")
            fetch_func = lambda etf=etf, module=module: module.fetch_holdings(etf, fetch_yahoo_price)
            process_etf(conn, code, name, fetch_func, json_file_name)
        except Exception as e:
            print(f"Failed to process {name}: {e}")
    
    conn.close()
    print("\nAll tasks completed.")

if __name__ == "__main__":
    main()
