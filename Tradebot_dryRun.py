from ib_insync import *
import pandas as pd
from dotenv import load_dotenv
import os

# === Top-level flag ===
USE_ENV = "paper"  # ⬅️ Change to "live" for live trading

# === Load selected .env ===
env_file = f".env.{USE_ENV}"
load_dotenv(dotenv_path=env_file)

# === Read from env ===
IB_HOST = os.getenv("IB_HOST")
IB_PORT = int(os.getenv("IB_PORT"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID"))
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

print(f"🔧 Loaded config: {USE_ENV.upper()}")

# === Connect ===
ib = IB()
ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
print(f"✅ Connected to IB Gateway ({USE_ENV.upper()})")

# ===  Cancel Existing Orders ===
open_orders = ib.openOrders()
if open_orders:
    print(f"🚫 Canceling {len(open_orders)} open orders...")
    for o in open_orders:
        ib.cancelOrder(o)
    ib.sleep(2)
else:
    print("✅ No open orders to cancel.")

# === Load CSV ===
watchlist = pd.read_csv('buyalert.csv').dropna(how='any')
print(f"📊 Loaded {len(watchlist)} stocks from buyalert.csv")

# === Process each stock ===
for _, row in watchlist.iterrows():
    ticker = row['Ticker']
    buy_price = float(row['BuyPrice'])
    stop_loss = float(row['StopLossPrice'])
    allocated = float(row['AllocatedAmount'])

    qty = int(allocated // buy_price)
    if qty < 1:
        print(f"⚠️ Skipping {ticker} — not enough allocation for even 1 share.")
        continue

    # === Build contract ===
    contract = Stock(ticker, 'SMART', 'USD')

    # === Build limit order ===
    order = LimitOrder('BUY', qty, buy_price, tif='DAY')

    # === Submit ===
    trade = ib.placeOrder(contract, order)
    print(f"📩 Submitted LIMIT order for {ticker}: {qty} @ ${buy_price}")

    # Optional: Wait and display order status
    ib.sleep(1)
    print(f"🧾 Order Status: {trade.orderStatus.status}")

    watchlist['Quantity'] = watchlist['AllocatedAmount'] // watchlist['BuyPrice']
    watchlist.to_csv('executed_orders_log.csv', index=False)

ib.disconnect()
print("🚪 Disconnected from IB Gateway")
