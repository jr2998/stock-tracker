"""
reset_portfolio.py  —  One-time portfolio reconstruction
=========================================================
Run this ONCE to wipe the current (corrupted) portfolio.json and rebuild
a clean one from the top 25 picks in the most recent data.json.

What it does:
  1. Reads data.json for current scores + prices
  2. Picks the top 25 stocks by score (same logic as grader.py)
  3. Allocates $1,000,000 score-proportionally across those 25 positions
  4. Sets the start_date to the original portfolio founding date
  5. Fetches full SPY history from that date for benchmark comparison
  6. Writes a clean portfolio.json

After running this, set RESET_PORTFOLIO = False in grader.py (it already is).
The weekly grader run will then maintain the portfolio via buy-and-hold logic.

Usage:
    python reset_portfolio.py
    python generate_html.py
"""

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import yfinance as yf

DATA_FILE      = "data.json"
PORTFOLIO_FILE = "portfolio.json"

# ── Parameters (must match grader.py) ────────────────────────────────────────
PORTFOLIO_START  = 1_000_000.0
MAX_HOLDINGS     = 25
BUY_THRESHOLD    = 65.0
CONVICTION_POWER = 1.5
MAX_POSITION     = 0.10
MIN_POSITION     = 0.015
MIN_TRADE_USD    = 2_000

# ── Original start date ───────────────────────────────────────────────────────
# Back-date to the week the portfolio was first created so the SPY benchmark
# and portfolio history both start from the same reference point.
# Adjust this if you know the exact original date.
PORTFOLIO_ORIGIN = "2026-02-24"   # ← first Monday the workflow ran


def _target_weights(records):
    """Top MAX_HOLDINGS picks, score^CONVICTION_POWER weights, clamped + normalised."""
    eligible = sorted(
        [r for r in records
         if (r.get("overall") or 0) >= BUY_THRESHOLD
         and r.get("price_raw") and r["price_raw"] > 0],
        key=lambda r: -(r.get("overall") or 0)
    )[:MAX_HOLDINGS]

    if not eligible:
        return {}, []

    raw     = {r["ticker"]: r["overall"] ** CONVICTION_POWER for r in eligible}
    total   = sum(raw.values()) or 1.0
    w       = {t: v / total for t, v in raw.items()}
    w       = {t: max(MIN_POSITION, min(MAX_POSITION, wt)) for t, wt in w.items()}
    total_w = sum(w.values()) or 1.0
    weights = {t: wt / total_w for t, wt in w.items()}
    return weights, eligible


def fetch_spy_history(start_date):
    """Fetch full SPY price history normalised to PORTFOLIO_START."""
    print(f"  Fetching SPY history from {start_date}…", end=" ", flush=True)
    try:
        spy  = yf.Ticker("SPY")
        hist = spy.history(start=start_date, auto_adjust=True)
        if hist.empty:
            print("empty — no SPY data returned")
            return []
        start_price = float(hist["Close"].iloc[0])
        result = [
            {"date":  dt.strftime("%Y-%m-%d"),
             "value": round(PORTFOLIO_START * float(row["Close"]) / start_price, 2)}
            for dt, row in hist.iterrows()
        ]
        print(f"{len(result)} trading days")
        return result
    except Exception as e:
        print(f"ERROR: {e}")
        return []


def build_portfolio(records, today_str):
    """Allocate capital across the top 25 picks and return holdings + trades."""
    weights, eligible = _target_weights(records)
    if not weights:
        print("  ERROR: no eligible stocks found in data.json")
        return {}, [], PORTFOLIO_START

    holdings = {}
    trades   = []
    cash     = PORTFOLIO_START

    print(f"\n  Buying top {len(eligible)} picks:")
    print(f"  {'Ticker':<8} {'Score':>6} {'Target%':>8} {'Shares':>10} "
          f"{'Price':>8} {'Cost':>12}")
    print(f"  {'─'*60}")

    for r in eligible:
        ticker     = r["ticker"]
        price      = float(r["price_raw"])
        target_usd = weights[ticker] * PORTFOLIO_START
        affordable = min(target_usd, cash * 0.98)
        if affordable < max(price, MIN_TRADE_USD):
            print(f"  {ticker:<8} — skipped (price ${price:.2f} > available ${affordable:,.0f})")
            continue

        shares = affordable / price
        cost   = shares * price
        cash  -= cost

        holdings[ticker] = {
            "shares":      round(shares, 6),
            "cost_basis":  round(price, 4),
            "last_price":  round(price, 4),
            "bought_date": today_str,
        }
        trades.append({
            "date":   today_str,
            "action": "BUY",
            "ticker": ticker,
            "shares": round(shares, 6),
            "price":  round(price, 2),
            "cost":   round(cost, 2),
        })
        print(f"  {ticker:<8} {r['overall']:>6.1f} {weights[ticker]*100:>7.1f}%"
              f" {shares:>10.4f} {price:>8.2f} {cost:>12,.0f}")

    return holdings, trades, cash


def main():
    now = datetime.now(timezone.utc)
    print(f"=== Portfolio Reset | {now.strftime('%Y-%m-%d %H:%M UTC')} ===\n")

    # ── Load data.json ────────────────────────────────────────────────────
    dp = Path(DATA_FILE)
    if not dp.exists():
        print(f"ERROR: {DATA_FILE} not found. Run grader.py first.")
        return

    data    = json.loads(dp.read_text())
    records = data.get("stocks", [])
    print(f"Loaded {len(records)} stocks from {DATA_FILE}"
          f"  (graded {data.get('graded_at', '?')})")

    # ── Use today as the buy date (current prices = cost basis) ──────────
    today_str = date.today().isoformat()

    # ── Build holdings ────────────────────────────────────────────────────
    holdings, trades, cash = build_portfolio(records, today_str)

    holdings_mv = sum(
        pos["shares"] * pos["last_price"] for pos in holdings.values()
    )
    total_value = holdings_mv + cash

    print(f"\n  ── Summary ────────────────────────────────────────────")
    print(f"  Holdings:      {len(holdings)}")
    print(f"  Invested:      ${holdings_mv:>12,.2f}")
    print(f"  Cash:          ${cash:>12,.2f}")
    print(f"  Total value:   ${total_value:>12,.2f}")

    # ── Fetch SPY history from the original founding date ─────────────────
    spy_history = fetch_spy_history(PORTFOLIO_ORIGIN)

    # ── Build history: one entry per day from origin to today ────────────
    # We only have today's actual values.  For the chart to render a flat
    # baseline from the start date, seed a single entry at the origin date
    # at PORTFOLIO_START, then add today's real value.
    history = []
    if PORTFOLIO_ORIGIN != today_str:
        history.append({
            "date":  PORTFOLIO_ORIGIN,
            "value": PORTFOLIO_START,
            "cash":  PORTFOLIO_START,
            "note":  "reconstructed — buy prices are current prices at reset date",
        })
    history.append({
        "date":  today_str,
        "value": round(total_value, 2),
        "cash":  round(cash, 2),
    })

    # ── Write portfolio.json ──────────────────────────────────────────────
    portfolio = {
        "start_date":   PORTFOLIO_ORIGIN,
        "start_value":  PORTFOLIO_START,
        "reset_date":   today_str,
        "cash":         round(cash, 2),
        "total_value":  round(total_value, 2),
        "holdings":     holdings,
        "history":      history,
        "spy_history":  spy_history,
        "trades":       trades,
        "updated_at":   today_str,
    }

    Path(PORTFOLIO_FILE).write_text(json.dumps(portfolio, indent=2, default=str))
    print(f"\n  Written {PORTFOLIO_FILE}")
    print(f"  Start date set to {PORTFOLIO_ORIGIN}  (original founding date)")
    print(f"\n  Next steps:")
    print(f"    1. python generate_html.py   ← rebuild the website")
    print(f"    2. git add portfolio.json index.html && git commit -m 'reset: clean portfolio'")
    print(f"    3. grader.py will now maintain this portfolio each week (RESET_PORTFOLIO=False)")


if __name__ == "__main__":
    main()
