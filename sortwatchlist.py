# /// script
# dependencies = [
#   "yfinance==0.2.66",
#   "pandas==2.3.3"
# ]
# ///


import yfinance as yf
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import time

def get_sp500():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    table = pd.read_html(url)[0]
    return table['Symbol'].tolist()

def get_asx200():
    url = 'https://en.wikipedia.org/wiki/S%26P/ASX_200'
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'lxml')
    table = soup.find('table', {'class': 'wikitable'})
    df = pd.read_html(str(table))[0]
    return [f"{code}.AX" for code in df['ASX code']]

def get_nifty50():
    url = 'https://en.wikipedia.org/wiki/NIFTY_50'
    table = pd.read_html(url)[1]
    return [f"{code}.NS" for code in table['Symbol']]

def get_finviz_rs(tickers):
    headers = {'User-Agent': 'Mozilla/5.0'}
    rs_data = {}

    for ticker in tickers:
        try:
            url = f'https://finviz.com/quote.ashx?t={ticker}'
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')

            table = soup.find_all('table', class_='snapshot-table2')

            if not table:
                continue

            for row in table[0].find_all('tr'):
                cells = row.find_all('td')
                for i in range(len(cells)):
                    if cells[i].text == 'RSI (14)':
                        rs_value = cells[i + 1].text.replace('%', '')
                        rs_data[ticker] = float(rs_value)
                        break

            time.sleep(1)  # Polite delay to avoid being blocked

        except Exception as e:
            print(f"Error scraping {ticker}: {e}")
            continue

    return rs_data


# Load tickers
watchlist = pd.read_csv("ILAN_COMBINED.csv")['Ticker'].tolist()

results = []

for ticker in watchlist:
    try:
        data = yf.Ticker(ticker).history(period="6mo")

        if data.empty:
            continue

        # Latest Close
        close = data['Close'].iloc[-1]

        # ATR(14)
        data['H-L'] = data['High'] - data['Low']
        atr = data['H-L'].rolling(14).mean().iloc[-1]
        atr_percent = round((atr / close) * 100, 2)

        # Base Duration: Price stayed in 10% range of max close over last 60 bars
        recent = data['Close'][-60:]
        highest_close = recent.max()
        within_range = recent[recent >= highest_close * 0.90]
        base_duration = len(within_range)

        # Append result (RS_Rating will be manually filled later)
        results.append({
            'Ticker': ticker,
            'Price': round(close, 2),
            'ATR%': atr_percent,
            'Base_Duration_Days': base_duration,
            'RS_Rating': None  # Manual entry or future scraper
        })

    except Exception as e:
        print(f"Error on {ticker}: {e}")

# Create DataFrame
df = pd.DataFrame(results)

# After df is created
rs_values = get_finviz_rs(df['Ticker'].tolist())

# Map RS into DataFrame
df['RS_Rating'] = df['Ticker'].map(rs_values)

# Drop rows without RS value
df = df.dropna(subset=['RS_Rating'])

# Final sort
df = df.sort_values(by='RS_Rating', ascending=False)

# Output final list
df.to_csv('ranked_buy_list_final.csv', index=False)
print(df.head(10))
