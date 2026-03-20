"""
reset_portfolio.py  —  Portfolio reconstruction with retroactive history
=========================================================================
Rebuilds portfolio.json from scratch using the current top 25 picks, but
back-dates cost basis and daily history to PORTFOLIO_ORIGIN so the
performance chart shows real returns since the founding date.

How it works:
  1. Reads data.json for current scores + tickers (the top 25 picks)
  2. Fetches full daily price history for all 25 tickers + SPY from
     PORTFOLIO_ORIGIN to today using a single yfinance batch download
  3. Sets each holding's cost_basis to its price on PORTFOLIO_ORIGIN
     (or its first available trading day if the ticker is newer)
  4. Computes portfolio market value for every trading day from origin
     to today — this becomes the history[] array in portfolio.json
  5. Writes a clean portfolio.json with accurate retroactive returns

The result: the performance chart and gain/loss figures reflect what
this exact portfolio of 25 stocks would have returned since the start
date, using real historical prices.

Note on weights: allocations use today's scores, not scores from the
origin date. This is a "what if we had bought these 25 stocks then"
backtest, not a simulation of what we actually would have bought.

Usage:
    python reset_portfolio.py
    python generate_html.py
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
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

# ── Founding date ─────────────────────────────────────────────────────────────
# This is the date cost basis is calculated from.  Set it to the Monday the
# original workflow first ran.  All history is back-filled from this date.
PORTFOLIO_ORIGIN = "2026-02-24"


# ─────────────────────────────────────────────────────────────────────────────

def _target_weights(records):
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
    return {t: wt / total_w for t, wt in w.items()}, eligible


def fetch_all_history(tickers, start_date):
    """
    Batch-download daily Close prices for all tickers + SPY from start_date.
    Returns a DataFrame indexed by date strings with one column per ticker.
    """
    all_tickers = list(tickers) + ["SPY"]
    print(f"  Downloading price history for {len(all_tickers)} tickers"
          f" from {start_date}...", flush=True)

    raw = yf.download(
        all_tickers,
        start=start_date,
        auto_adjust=True,
        progress=False,
    )

    # yf.download returns MultiIndex columns (metric, ticker) when >1 ticker
    if isinstance(raw.columns, pd.MultiIndex):
        closes = raw["Close"].copy()
    else:
        closes = raw[["Close"]].rename(columns={"Close": all_tickers[0]})

    closes.index = pd.to_datetime(closes.index).strftime("%Y-%m-%d")
    closes = closes.dropna(how="all")

    print(f"  Got {len(closes)} trading days  "
          f"({closes.index[0]} -> {closes.index[-1]})")
    return closes


def build_holdings_and_history(records, closes):
    """
    Compute holdings (with origin-date cost basis) and full daily history.
    """
    weights, eligible = _target_weights(records)
    if not weights:
        print("  ERROR: no eligible stocks found")
        return {}, [], [], PORTFOLIO_START

    holdings = {}
    trades   = []
    cash     = PORTFOLIO_START

    print(f"\n  Building {len(eligible)} positions:")
    print(f"  {'Ticker':<8} {'Score':>6} {'Wt%':>6}  {'Buy date':<12}"
          f" {'Cost basis':>10} {'Shares':>10} {'Allocation':>12}")
    print(f"  {'-'*72}")

    for r in eligible:
        ticker     = r["ticker"]
        weight     = weights[ticker]
        allocation = weight * PORTFOLIO_START

        if ticker not in closes.columns:
            print(f"  {ticker:<8} -- no price history, holding as cash")
            continue

        col = closes[ticker].dropna()
        if col.empty:
            print(f"  {ticker:<8} -- empty series, holding as cash")
            continue

        # Use founding date price if available; otherwise earliest date
        if PORTFOLIO_ORIGIN in col.index:
            buy_date  = PORTFOLIO_ORIGIN
            buy_price = float(col[PORTFOLIO_ORIGIN])
        else:
            buy_date  = col.index[0]
            buy_price = float(col.iloc[0])
            print(f"  {ticker:<8} -- no data on {PORTFOLIO_ORIGIN},"
                  f" using {buy_date}")

        if buy_price <= 0:
            print(f"  {ticker:<8} -- zero price, skipping")
            continue

        affordable = min(allocation, cash * 0.98)
        if affordable < max(buy_price, MIN_TRADE_USD):
            print(f"  {ticker:<8} -- insufficient funds, skipping")
            continue

        shares = affordable / buy_price
        cost   = shares * buy_price
        cash  -= cost

        holdings[ticker] = {
            "shares":      round(shares, 6),
            "cost_basis":  round(buy_price, 4),
            "last_price":  round(float(col.iloc[-1]), 4),
            "bought_date": buy_date,
        }
        trades.append({
            "date":   buy_date,
            "action": "BUY",
            "ticker": ticker,
            "shares": round(shares, 6),
            "price":  round(buy_price, 2),
            "cost":   round(cost, 2),
        })
        print(f"  {ticker:<8} {r['overall']:>6.1f} {weight*100:>5.1f}%"
              f"  {buy_date:<12} {buy_price:>10.2f} {shares:>10.4f}"
              f" {cost:>12,.0f}")

    # ── Daily portfolio value ─────────────────────────────────────────────
    print(f"\n  Computing daily portfolio history...", flush=True)

    history = []
    all_dates = closes.index.tolist()

    for day in all_dates:
        mv = 0.0
        for ticker, pos in holdings.items():
            # Don't count a position before its buy date
            if day < pos["bought_date"]:
                continue
            if ticker not in closes.columns:
                continue
            price_today = closes[ticker].get(day)
            if price_today is None or (price_today != price_today):  # NaN check
                # Forward-fill: use most recent known price
                past = closes[ticker].loc[:day].dropna()
                price_today = float(past.iloc[-1]) if not past.empty else pos["cost_basis"]
            mv += pos["shares"] * float(price_today)

        history.append({
            "date":  day,
            "value": round(mv + cash, 2),
            "cash":  round(cash, 2),
        })

    print(f"  {len(history)} daily data points  "
          f"({history[0]['date']} -> {history[-1]['date']})")

    return holdings, trades, history, cash


def build_spy_history(closes):
    """Normalise SPY close series to PORTFOLIO_START."""
    if "SPY" not in closes.columns:
        print("  WARNING: SPY data missing")
        return []
    spy = closes["SPY"].dropna()
    if spy.empty:
        return []
    start_price = float(spy.iloc[0])
    return [
        {"date": d, "value": round(PORTFOLIO_START * float(p) / start_price, 2)}
        for d, p in spy.items()
        if p == p  # skip NaN
    ]


def main():
    now = datetime.now(timezone.utc)
    print(f"=== Portfolio Reset (retroactive) | {now.strftime('%Y-%m-%d %H:%M UTC')} ===\n")

    dp = Path(DATA_FILE)
    if not dp.exists():
        print(f"ERROR: {DATA_FILE} not found. Run grader.py first.")
        return

    data    = json.loads(dp.read_text())
    records = data.get("stocks", [])
    print(f"Loaded {len(records)} stocks  (graded {data.get('graded_at', '?')})")

    weights, eligible = _target_weights(records)
    if not eligible:
        print("ERROR: no eligible stocks in data.json")
        return

    tickers = [r["ticker"] for r in eligible]
    print(f"Top {len(tickers)} picks: {', '.join(tickers)}\n")

    closes      = fetch_all_history(tickers, PORTFOLIO_ORIGIN)
    holdings, trades, history, cash = build_holdings_and_history(records, closes)
    spy_history = build_spy_history(closes)

    holdings_mv  = sum(pos["shares"] * pos["last_price"] for pos in holdings.values())
    total_value  = holdings_mv + cash
    start_value  = history[0]["value"] if history else PORTFOLIO_START
    total_return = (total_value - start_value) / start_value * 100

    print(f"\n  -- Summary --")
    print(f"  Holdings:       {len(holdings)}")
    print(f"  Cost basis:     prices on {PORTFOLIO_ORIGIN} (or first available date)")
    print(f"  Start value:    ${start_value:>12,.2f}")
    print(f"  Current value:  ${total_value:>12,.2f}")
    print(f"  Total return:   {total_return:+.2f}%")
    print(f"  Cash:           ${cash:>12,.2f}")
    print(f"  History:        {len(history)} trading days")
    print(f"  SPY history:    {len(spy_history)} trading days")

    today_str = date.today().isoformat()

    portfolio = {
        "start_date":   PORTFOLIO_ORIGIN,
        "start_value":  PORTFOLIO_START,
        "reset_date":   today_str,
        "cash":         round(cash, 2),
        "total_value":  round(total_value, 2),
        "holdings":     holdings,
        "history":      history,
        "spy_history":  spy_history,
        "trades":       sorted(trades, key=lambda t: t["date"]),
        "updated_at":   today_str,
    }

    Path(PORTFOLIO_FILE).write_text(json.dumps(portfolio, indent=2, default=str))
    print(f"\n  Written {PORTFOLIO_FILE}")
    print(f"\n  Next steps:")
    print(f"    python generate_html.py")
    print(f"    git add portfolio.json index.html")
    print(f"    git commit -m 'reset: retroactive history from {PORTFOLIO_ORIGIN}'")
    print(f"    git push")


if __name__ == "__main__":
    main()
