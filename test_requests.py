import requests

url = "https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
try:
    response = requests.get(url, headers=headers, timeout=10)
    print("Status Code:", response.status_code)
    print("Contains 台積電:", "台積電" in response.text)
    print("Contains json endpoint?:", "/ETF/Fund/Portfolio" in response.text)
except Exception as e:
    print("Error:", e)
