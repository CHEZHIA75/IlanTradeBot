
#!/usr/bin/env python3
"""
Decision Tool for Progressive Exposure Plan
---------------------------------------------------------------
Adds --json flag to export decision summary for downstream automation.

Example:
    python decision_tool.py \
        --portfolio 60000 \
        --market Orange \
        --phase 2 \
        --wins 3 \
        --breakeven y \
        --drawdown 0.8 \
        --growth 4.0 \
        --days 45 \
        --csv shortlisted.csv \
        --out position_sizing_output.csv \
        --json summary.json
"""

import sys
import math
import argparse
import pandas as pd
import json

ALLOWED_PHASES_BY_MARKET = {
    "red": [],
    "yellow": [1, 2],
    "orange": [1, 2, 3, 4],
    "green": [1, 2, 3, 4],
}

PHASE_RISK_PCT = {1: 0.01, 2: 0.02, 3: 0.06, 4: 0.09}

def decide_phase(last_phase:int,
                 market_condition:str,
                 wins_2r:int,
                 both_to_breakeven:bool,
                 drawdown_pct:float,
                 growth_since_high_pct:float,
                 consistency_days:int):
    messages = []
    phase = int(last_phase)
    phase_risk_pct = PHASE_RISK_PCT.get(phase, 0.01) * 100.0

    if drawdown_pct >= phase_risk_pct:
        new_phase = max(1, phase - 1)
        if new_phase != phase:
            messages.append(f"Reversion: Drawdown {drawdown_pct:.2f}% ≥ {phase_risk_pct:.2f}%. Phase {phase} → {new_phase}.")
            phase = new_phase

    if phase == 1:
        if both_to_breakeven and wins_2r >= 2:
            messages.append("Advance: Phase 1 criteria met (both BE + ≥2×2R wins). 1 → 2.")
            phase = 2
        else:
            messages.append("Remain: Phase 1 criteria not met.")
    elif phase == 2:
        if wins_2r >= 2 and drawdown_pct < PHASE_RISK_PCT[2]*100:
            messages.append("Advance: Phase 2 criteria met (≥2×2R wins, no DD breach). 2 → 3.")
            phase = 3
        else:
            messages.append("Remain: Phase 2 criteria not met.")
    elif phase == 3:
        if growth_since_high_pct >= 5.0:
            messages.append("Advance: Phase 3 criteria met (+5% growth). 3 → 4.")
            phase = 4
        else:
            messages.append("Remain: Phase 3 criteria not met.")
    elif phase == 4:
        if consistency_days >= 90:
            messages.append("Maintain: Phase 4 consistency confirmed (≥90 days).")
        else:
            messages.append("Maintain: Phase 4 (consistency < 90 days).")

    allowed = ALLOWED_PHASES_BY_MARKET.get(market_condition.lower(), [])
    if not allowed:
        messages.append("Market RED: No entries allowed → Phase 0.")
        return 0, messages

    if phase not in allowed:
        capped = max([p for p in allowed if p <= phase], default=allowed[0])
        if capped != phase:
            messages.append(f"Market gating: Phase {phase} not allowed in {market_condition}. Capped to {capped}.")
            phase = capped

    return phase, messages

def size_positions(df: pd.DataFrame, portfolio_value: float, phase: int):
    risk_pct = PHASE_RISK_PCT[phase]
    total_risk_dollars = portfolio_value * risk_pct

    for col in ["Symbol", "EntryPrice", "StopLoss"]:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    if "VolFactor" not in df.columns:
        df["VolFactor"] = 1.0

    df["VolFactor"] = df["VolFactor"].fillna(1.0).astype(float)
    df["RiskPerShare"] = (df["EntryPrice"] - df["StopLoss"]).astype(float)
    df["InvalidRisk"] = df["RiskPerShare"] <= 0

    if df["InvalidRisk"].any():
        print("⚠️ Warning: Some rows have invalid risk (Entry ≤ Stop).")

    def compute_pos(row):
        if row["InvalidRisk"] or row["VolFactor"] <= 0:
            return 0
        denom = row["RiskPerShare"] * row["VolFactor"]
        return int(math.floor(total_risk_dollars / denom)) if denom > 0 else 0

    df["PhaseRisk%"] = f"{risk_pct*100:.2f}%"
    df["PositionSize"] = df.apply(compute_pos, axis=1)
    df["Phase"] = phase
    return df, total_risk_dollars

def main():
    parser = argparse.ArgumentParser(description="Decision Tool for Progressive Exposure Plan (with JSON output)")
    parser.add_argument("--portfolio", type=float, required=True, help="Portfolio value in USD")
    parser.add_argument("--market", type=str, required=True, help="Market condition: Red/Yellow/Orange/Green")
    parser.add_argument("--phase", type=int, required=True, help="Last confirmed phase (1-4)")
    parser.add_argument("--wins", type=int, required=True, help="Recent 2R wins")
    parser.add_argument("--breakeven", type=str, required=True, help="Both positions breakeven (y/n)")
    parser.add_argument("--drawdown", type=float, required=True, help="Drawdown %% from equity high")
    parser.add_argument("--growth", type=float, required=True, help="Growth %% since last equity high")
    parser.add_argument("--days", type=int, required=True, help="Consistency days for Phase 4")
    parser.add_argument("--csv", type=str, required=True, help="Input CSV filename")
    parser.add_argument("--out", type=str, default="position_sizing_output.csv", help="Output CSV filename")
    parser.add_argument("--json", type=str, help="Optional JSON summary output filename")
    args = parser.parse_args()

    portfolio_value = args.portfolio
    market_condition = args.market.capitalize()
    last_phase = args.phase
    wins_2r = args.wins
    both_to_breakeven = args.breakeven.lower() in ("y","yes")
    drawdown_pct = args.drawdown
    growth_since_high_pct = args.growth
    consistency_days = args.days
    csv_name = args.csv
    out_name = args.out
    json_name = args.json

    phase, reasons = decide_phase(
        last_phase, market_condition, wins_2r, both_to_breakeven,
        drawdown_pct, growth_since_high_pct, consistency_days
    )

    print("\n--- Phase Decision ---")
    for m in reasons:
        print("-", m)

    if phase == 0:
        print("⛔ Market RED: entries halted. No sizing performed.")
        sys.exit(0)

    print(f"✅ Phase {phase} selected ({PHASE_RISK_PCT[phase]*100:.2f}% risk) | Market: {market_condition}")

    try:
        df = pd.read_csv(csv_name)
    except FileNotFoundError:
        print(f"⛔ Input file not found: {csv_name}")
        sys.exit(1)

    sized_df, total_risk_dollars = size_positions(df, portfolio_value, phase)
    sized_df.to_csv(out_name, index=False)

    print(f"\n✅ Output saved → {out_name}")
    print(f"Total risk: ${total_risk_dollars:,.2f}")
    print(sized_df.head().to_string(index=False))

    if json_name:
        summary = {
            "phase": phase,
            "market": market_condition,
            "portfolio_value": portfolio_value,
            "risk_pct": PHASE_RISK_PCT[phase],
            "total_risk": total_risk_dollars,
            "csv_input": csv_name,
            "csv_output": out_name,
            "decision_messages": reasons,
        }
        with open(json_name, "w") as jf:
            json.dump(summary, jf, indent=2)
        print(f"\n📄 JSON summary saved → {json_name}")

if __name__ == "__main__":
    main()
