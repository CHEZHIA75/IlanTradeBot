import pandas as pd
import time
from datetime import datetime
from ib_insync import *
import os
from dotenv import load_dotenv
import pytz
import math

# === Top-level flag ===
USE_ENV = "live"  # ⬅️ Change to "paper" for paper trading

# === Load selected .env ===
env_file = f".env.{USE_ENV}"
load_dotenv(dotenv_path=env_file)

# === Read from env ===
KILL_SWITCH = os.getenv("KILL_SWITCH", "false").lower() == "true"
IB_HOST = os.getenv("IB_HOST")
IB_PORT = int(os.getenv("IB_PORT"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID"))
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

print(f"🔧 Loaded config: {USE_ENV.upper()}")

# === Connect ===
ib = IB()
ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
print(f"✅ Connected to IB Gateway ({USE_ENV.upper()})")

# === Wait until 10:00 AM EST ===
nytz = pytz.timezone("America/New_York")
while True:
    now = datetime.now(nytz)
    if now.hour > 10 or (now.hour == 10 and now.minute >= 0):
        break
    print(f"⏳ Waiting... Current time: {now.strftime('%H:%M:%S')}")
    time.sleep(30)

if not KILL_SWITCH:
    print("⛔ Tradebot deactivated by kill switch.")
    exit()

# === Load Buy Alerts ===
df = pd.read_csv("buyalert.csv").dropna(how='any')
print(f"📊 Loaded {len(df)} stocks from buyalert.csv")
executed_trades = 0

for _, row in df.iterrows():
    if executed_trades >= 2:
        print("🚫 Max trades reached for today.")
        break

    ticker = row['Ticker']
    buy_price = float(row['BuyPrice'])
    stop_price = float(row['StopLossPrice'])
    allocated = float(row['AllocatedAmount'])

    contract = Stock(ticker, 'SMART', 'USD')
    market_data = ib.reqMktData(contract, snapshot=True, regulatorySnapshot=True)
    ib.sleep(2)

    if market_data.last == 0.0 or math.isnan(market_data.last):
        print(f"⚠️ No price for {ticker}")
        continue

    price = market_data.last
    print(f"📈 {ticker}: market price = {price}")

    if price > buy_price and price <= buy_price * 1.01:
        quantity = int(allocated // price)
        if quantity == 0:
            print(f"⚠️ Insufficient funds for {ticker}")
            continue

        # Submit market order with attached stop-loss
        order = MarketOrder('BUY', quantity)
        trade = ib.placeOrder(contract, order)
        ib.sleep(2)
        if trade.orderStatus.status != 'Filled':
            print(f"❌ Order for {ticker} not filled.")
            continue

        filled_price = trade.orderStatus.avgFillPrice
        print(f"✅ {ticker} bought @ {filled_price} x {quantity}")

        # Place Stop Loss
        stop_order = StopOrder('SELL', quantity, stop_price, parentId=trade.order.permId)
        ib.placeOrder(contract, stop_order)

        executed_trades += 1
    else:
        print(f"⏭️ {ticker} skipped (not in breakout zone)")
print("🏁 Trading session completed.")