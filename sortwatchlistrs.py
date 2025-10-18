import yfinance as yf
import pandas as pd
from datetime import datetime,timedelta
import requests
from bs4 import BeautifulSoup
import time
from io import StringIO
import pytz
import numpy as np

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

def get_sp500():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    res = requests.get(url, headers=headers)

    # Load all tables and find one with a Symbol column
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
        raise ValueError("Couldn't find a table with a 'Symbol' column on SP500 page.")

    return [f"{code}" for code in target_table[symbol_col]]

def get_asx200():
    url = 'https://en.wikipedia.org/wiki/S%26P/ASX_200'
    res = requests.get(url, headers=headers)
    return [f"{code}.AX" for code in pd.read_html(StringIO(res.text))[0]['Code']]

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

def fix_yahoo_ticker(ticker):
    return ticker.replace('.', '-')

# === Step 1: Define Benchmark Universes ===
benchmark_universes = {
    'SPY': get_sp500(),
    #'ASX200': get_asx200(),
    'NIFTY50': get_nifty50()
}

# === Step 2: Define Time Windows ===
nytz = pytz.timezone("America/New_York")
now = datetime.now(nytz)

windows = {
    '1M': now - timedelta(days=21),
    '3M': now - timedelta(days=63),
    '6M': now - timedelta(days=126),
}

# === Step 3: Function to Get Returns ===
def get_returns(tickers):
    returns = []
    for ticker in tickers:
        try:
            yf_ticker = fix_yahoo_ticker(ticker)
            hist = yf.Ticker(yf_ticker).history(period="6mo")
            if len(hist) < 126:
                continue
            
            if hist is None or hist.empty:
                print(f"⚠️ Skipping {ticker}: no data (yf: {yf_ticker})")
                continue

            close_today = hist['Close'].iloc[-1]
            #print("🧪 close_today :\n", close_today)
            # 1M Close
            close_1m_filtered = hist.loc[hist.index >= windows['1M']]['Close']
            if pd.isna(close_1m_filtered):
                print(f"⚠️ No 1M data for {ticker}")
                continue
            close_1m = close_1m_filtered.iloc[0]
            #print("🧪 close_1M:", close_1m)

            # 3M Close
            close_3m_filtered = hist.loc[hist.index >= windows['3M']]['Close']
            if pd.isna(close_3m_filtered):
                print(f"⚠️ No 3M data for {ticker}")
                continue
            close_3m = close_3m_filtered.iloc[0]
            #print("🧪 close_3M:", close_3m)

            # 6M Close (entire history)
            close_6m_filtered = hist['Close'].iloc[0]
            if pd.isna(close_6m_filtered):
                print(f"⚠️ No 6M data for {ticker}")
                continue
            close_6m = close_6m_filtered
            #print("🧪 close_6M:", close_6m)

            if pd.isna(close_today):
                print(f"⚠️ NaN detected in return calc for {ticker} (missing Close today data)")
                continue 
            if pd.isna(close_1m):
                print(f"⚠️ NaN detected in return calc for {ticker} (missing 1M data)")
                continue
            if pd.isna(close_3m):
                print(f"⚠️ NaN detected in return calc for {ticker} (missing 3M data)")
                continue
            if pd.isna(close_6m):
                print(f"⚠️ NaN detected in return calc for {ticker} (missing 6M data)")
                continue            
            

            r1m = (close_today - close_1m) / close_1m * 100
            r3m = (close_today - close_3m) / close_3m * 100
            r6m = (close_today - close_6m) / close_6m * 100

            returns.append({
                'Ticker': ticker,
                'Price': round(close_today, 2),
                'Return_1M_%': round(r1m, 2) if not pd.isna(r1m) else np.nan,
                'Return_3M_%': round(r3m, 2) if not pd.isna(r3m) else np.nan,
                'Return_6M_%': round(r6m, 2) if not pd.isna(r6m) else np.nan
            })
        except IndexError as e:
            print(f"❌ IndexError for {ticker}: {e}")
            continue
        except Exception as e:
            print(f"❌ Unexpected error for {ticker}: {e}")
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
    #print("📥 tickers to pull :", tickers_to_pull)
    df = get_returns(tickers_to_pull)
    #print("📥 Raw df before filtering:", df.shape)
    #print(df.head(10))
    #print("🔍 DataFrame columns:", df.columns)
    #print("🧪 Sample rows:\n", df.head())
    if df.empty:
        raise ValueError("❌ DataFrame is empty — check data source or filters.")
    df = df.fillna(0)
    df.columns = df.columns.str.strip().str.lower()
    #print("✅ Normalized columns:", df.columns)

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
