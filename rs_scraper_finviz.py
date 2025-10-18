# /// script
# dependencies = [
#   "yfinance==0.2.66",
#   "pandas==2.3.3"
# ]
# ///


import requests
import pandas as pd
from bs4 import BeautifulSoup
import time

def get_finviz_rs(tickers):
    headers = {'User-Agent': 'Mozilla/5.0'}
    rs_data = {}

    for ticker in tickers:
        try:
            url = f'https://finviz.com/quote.ashx?t={ticker}'
            page = requests.get(url, headers=headers)
            soup = BeautifulSoup(page.content, 'html.parser')
            table = soup.find_all('table', class_='snapshot-table2')

            if not table:
                continue

            for row in table[0].find_all('tr'):
                cells = row.find_all('td')
                for i in range(len(cells)):
                    if cells[i].text == 'RSI (14)':
                        rs_value = cells[i + 1].text
                        rs_data[ticker] = float(rs_value)
                        break

            time.sleep(1)  # polite delay

        except Exception as e:
            print(f"Error scraping {ticker}: {e}")
            continue

    return rs_data

