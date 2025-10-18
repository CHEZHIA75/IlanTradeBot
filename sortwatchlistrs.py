import yfinance as yf
import pandas as pd
from datetime import datetime,timedelta
import requests
from bs4 import BeautifulSoup
import time
from io import StringIO

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

def get_sp500():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    res = requests.get(url, headers=headers)

    # Load all tables and find one with a Symbol column
    tables = pd.read_html(res.text)

    symbol_col = None
    target_table = None

    for table in tables:
        for col in table.columns:
            if 'symbol' in str(col).lower():
                symbol_col = col
                target_table = table
                break
        if target_table is not None:
            break

    if target_table is None:
        raise ValueError("Couldn't find a table with a 'Symbol' column on SP500 page.")

    return [f"{code}" for code in target_table[symbol_col]]

def get_asx200():
    url = 'https://en.wikipedia.org/wiki/S%26P/ASX_200'
    res = requests.get(url, headers=headers)
    return [f"{code}.AX" for code in pd.read_html(res.text)[0]['Code']]

def get_nifty50():
    url = 'https://en.wikipedia.org/wiki/NIFTY_50'
    res = requests.get(url, headers=headers)

    tables = pd.read_html(StringIO(res.text))
    symbol_col = None
    target_table = None

    for table in tables:
        for col in table.columns:
            if 'symbol' in str(col).lower():
                symbol_col = col
                target_table = table
                break
        if target_table is not None:
            break

    if target_table is None:
        raise ValueError("No table with a 'Symbol' column found")

    return [f"{code}.NS" for code in target_table[symbol_col]]


# === Step 1: Define Benchmark Universes ===
benchmark_universes = {
    'SPY': get_sp500(),
    #'ASX200': get_asx200(),
    'NIFTY50': get_nifty50()
}

# === Step 2: Define Time Windows ===
today = datetime.today()
windows = {
    '1M': today - timedelta(days=21),
    '3M': today - timedelta(days=63),
    '6M': today - timedelta(days=126)
}

# === Step 3: Function to Get Returns ===
def get_returns(tickers):
    returns = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="6mo")
            if len(hist) < 126:
                continue

            close_today = hist['Close'][-1]
            close_1m = hist.loc[hist.index >= windows['1M']]['Close'].iloc[0]
            close_3m = hist.loc[hist.index >= windows['3M']]['Close'].iloc[0]
            close_6m = hist['Close'].iloc[0]

            r1m = (close_today - close_1m) / close_1m * 100
            r3m = (close_today - close_3m) / close_3m * 100
            r6m = (close_today - close_6m) / close_6m * 100

            returns.append({
                'Ticker': ticker,
                'Price': round(close_today, 2),
                'Return_1M_%': round(r1m, 2),
                'Return_3M_%': round(r3m, 2),
                'Return_6M_%': round(r6m, 2)
            })
        except:
            continue
    return pd.DataFrame(returns)

# === Step 4: Build RS Rank for Each Ticker vs Benchmark ===
watchlist_df = pd.read_csv("ILAN_COMBINED_BENCHMARK.csv", sep=",", engine="python")
watchlist_df.columns = watchlist_df.columns.str.strip().str.lower()
watchlist = watchlist_df.to_dict("records")
#if 'ticker' not in watchlist_df.columns or 'benchmark' not in watchlist_df.columns:
#    raise ValueError(
#        f"❌ Invalid CSV headers. Found: {list(watchlist_df.columns)} — Expected: ['ticker','benchmark']"
#    )
#print("📄 Parsed watchlist:", watchlist)

final = []

for entry in watchlist:
    #print("🔁 Entry:", entry)
    ticker = entry['ticker']
    benchmark = entry['benchmark']
    universe = benchmark_universes[benchmark]

    # Get returns for benchmark + target ticker
    tickers_to_pull = list(set(universe + [ticker]))
    df = get_returns(tickers_to_pull)

    print("🔍 DataFrame columns:", df.columns)
    print("🧪 Sample rows:\n", df.head())

    df.columns = df.columns.str.strip().str.lower()
    print("✅ Normalized columns:", df.columns)

    target_row = df[df['ticker'] == ticker]
    if target_row.empty:
        continue

    # RS Rank: Percentile of target vs universe
    for window in ['1M', '3M', '6M']:
        rank_col = f'Return_{window}_%'
        df[f'{window}_Rank'] = df[rank_col].rank(pct=True) * 100

    # Weighted Score
    df['RS_Score'] = round(df['1M_Rank']*0.2 + df['3M_Rank']*0.3 + df['6M_Rank']*0.5, 2)

    # Extract just the target
    target_rs = df[df['ticker'] == ticker].iloc[0].to_dict()
    final.append(target_rs)

# === Step 5: Export ===
final_df = pd.DataFrame(final)
final_df = final_df.sort_values(by='RS_Score', ascending=False)
final_df.to_csv("benchmark_rs_ranked.csv", index=False)
print(final_df[['Ticker', 'Price', 'RS_Score']])
