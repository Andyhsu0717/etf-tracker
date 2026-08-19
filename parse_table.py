import requests
from bs4 import BeautifulSoup
import re

url = "https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# find text
element = soup.find(string=re.compile("台積電"))
if element:
    print("Found text in tag:", element.parent.name)
    print("Content preview:", str(element.parent)[:500])
else:
    print("Not found.")
