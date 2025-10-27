#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradeBot Bridge (Bracket Orders + Safe Reconnect + Auto Cancel)
---------------------------------------------------------------
- Loads decision_summary.json + position_sizing_output.csv
- Waits until 30 minutes after NYSE open (New York time)
- Connects only after wait (avoids pre-market disconnect)
- Places StopLimit BUY with linked Stop SELL (GTC)
- Keeps heartbeat & reconnects if socket drops
- Cancels all unfilled entries 10 min before close
- Logs all actions in ASCII (Windows-safe)

Requires:  pip install ib_insync
"""

from ib_insync import *
import pandas as pd
import json, time, datetime, os
from zoneinfo import ZoneInfo

# === Configuration ===
MAX_POSITIONS = 2
NY_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = datetime.time(9, 30, tzinfo=NY_TZ)
MARKET_CLOSE = datetime.time(16, 0, tzinfo=NY_TZ)
ENTRY_BUFFER = 0.005   # +0.5%
LOG_FILE = "tradebot_log_%s.txt" % datetime.date.today()

def log(msg):
    ts = datetime.datetime.now().strftime("[%H:%M:%S]")
    line = "%s %s" % (ts, msg)
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def now_ny():
    return datetime.datetime.now(tz=NY_TZ)

def wait_until_market_ready():
    now = now_ny()
    open_dt = now.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute,
                          second=0, microsecond=0)
    ready_dt = open_dt + datetime.timedelta(minutes=30)
    if now < ready_dt:
        wait = (ready_dt - now).total_seconds()
        log("Waiting %d minutes until 30 minutes post-open (NY %s)..." %
            (int(wait/60), ready_dt.time()))
        time.sleep(wait)
    else:
        log("Market already past 30-minute buffer (NY) starting now.")

def ensure_connection(ib, client_id):
    """Reconnect if IB socket dropped."""
    if not ib.isConnected():
        try:
            ib.disconnect()
            ib.connect("127.0.0.1", 7497, clientId=client_id)
            log("Reconnected to IB Gateway.")
        except Exception as e:
            log("Reconnect failed: %s" % e)

def main():
    # --- Load decision & positions ---
    decision = json.load(open("decision_summary.json"))
    df = pd.read_csv("position_sizing_output.csv")

    phase = decision["phase"]
    market = decision["market"]
    portfolio_value = decision["portfolio_value"]

    log("=== TradeBot Bridge started | Phase %d | Market: %s | Portfolio: $%.2f ===" %
        (phase, market, portfolio_value))

    # --- Wait until 30 minutes after open ---
    wait_until_market_ready()

    # --- Connect to IB Gateway AFTER wait ---
    ib = IB()
    try:
        ib.connect("127.0.0.1", 7497, clientId=phase)
        log("Connected to IB Gateway.")
    except Exception as e:
        log("Connection error: %s" % e)
        return

    # --- Prepare contracts ---
    contracts = {}
    for _, row in df.iterrows():
        sym = row["Symbol"]
        c = Stock(sym, "SMART", "USD")
        ib.qualifyContracts(c)
        contracts[sym] = (c, row)

    active_positions = 0
    open_trades = {}
    canceled_for_close = False

    while True:
        now = now_ny()

        # Auto-cancel all unfilled entries 10 min before close
        close_warn = datetime.datetime.combine(now.date(),
                     (datetime.datetime.min + datetime.timedelta(hours=15, minutes=50)).time(),
                     tzinfo=NY_TZ)
        if now >= close_warn and not canceled_for_close:
            log("10 min before close - canceling all unfilled entries.")
            for sym, trade in open_trades.items():
                if trade.orderStatus.status not in ("Filled", "Cancelled"):
                    ib.cancelOrder(trade.order)
                    log("Canceled entry for %s" % sym)
            canceled_for_close = True

        if now.time() >= MARKET_CLOSE:
            log("Market close reached - disconnecting.")
            break

        ensure_connection(ib, phase)

        if active_positions >= MAX_POSITIONS:
            log("Two positions filled - stopping new entries.")
            break

        for sym, (contract, row) in contracts.items():
            if sym in open_trades or canceled_for_close:
                continue

            ticker = ib.reqMktData(contract, "", False, False)
            ib.sleep(2)
            last = ticker.last if ticker.last else ticker.marketPrice()
            ib.cancelMktData(contract)
            if not last or last <= 0:
                continue

            stop_price = float(row["EntryPrice"])
            limit_price = round(stop_price * (1 + ENTRY_BUFFER), 2)
            qty = int(row["PositionSize"])
            stop_loss_price = float(row["StopLoss"])

            # Parent StopLimit BUY + Child Stop SELL (GTC)
            if last < stop_price:
                parent = StopLimitOrder("BUY", qty, stop_price, limit_price)
                parent.tif = "DAY"
                parent.transmit = False

                child = StopOrder("SELL", qty, stop_loss_price, tif="GTC")
                child.parentId = parent.orderId
                child.transmit = True

                ib.placeOrder(contract, parent)
                ib.placeOrder(contract, child)

                open_trades[sym] = parent
                log("Placed StopLimit BUY + Stop SELL(GTC) for %s | Qty %d Stop %.2f Limit %.2f SL %.2f"
                    % (sym, qty, stop_price, limit_price, stop_loss_price))
                time.sleep(1)

        # --- Check fills & heartbeat ---
        for sym, trade in list(open_trades.items()):
            ib.sleep(1)
            status = trade.orderStatus.status
            if status == "Filled":
                active_positions += 1
                price = trade.orderStatus.avgFillPrice
                log("%s filled at %.2f - protective stop active." % (sym, price))
                open_trades.pop(sym)

        ib.reqCurrentTime()     # keep socket alive
        time.sleep(30)

    ib.disconnect()
    log("TradeBot Bridge session complete.")

if __name__ == "__main__":
    main()
