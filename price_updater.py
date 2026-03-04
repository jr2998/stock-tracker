"""
price_updater.py  —  Daily Portfolio Price Refresh
===================================================
Fetches current prices ONLY for tickers currently held in portfolio.json,
updates holding values and portfolio history, then writes updated portfolio.json.

This runs daily (Mon–Fri) and is fast (~5-10 seconds) since it only fetches
prices for held positions, not the full S&P 500 universe.

The full scrape (scraper.py → grader.py) runs weekly to refresh fundamentals
and rebalance the portfolio. This script just keeps valuations current between
weekly scrapes.

Pipeline:
  Daily (Mon-Fri):   price_updater.py  →  generate_html.py
  Weekly (Sunday):   scraper.py  →  grader.py  →  generate_html.py
                     (grader resets portfolio when RESET_PORTFOLIO=True)
"""

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import yfinance as yf

PORTFOLIO_FILE = "portfolio.json"
DATA_FILE      = "data.json"

def fetch_prices(tickers):
    """Fetch current prices for a list of tickers. Returns {ticker: price}."""
    prices = {}
    for symbol in tickers:
        try:
            tk   = yf.Ticker(symbol)
            info = tk.info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price:
                prices[symbol] = float(price)
            time.sleep(0.3)   # light delay — only fetching held positions
        except Exception as e:
            print(f"  WARNING: could not fetch price for {symbol}: {e}")
    return prices

def fetch_spy_price():
    """Fetch current SPY price for benchmark update."""
    try:
        info = yf.Ticker("SPY").info or {}
        return float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    except Exception:
        return None

def update_portfolio_prices(portfolio, prices):
    """Update holding prices and recalculate portfolio value."""
    today_str = date.today().isoformat()
    holdings  = portfolio.get("holdings", {})

    holdings_mv = 0
    updated = 0
    for ticker, pos in holdings.items():
        if ticker in prices:
            pos["last_price"] = round(prices[ticker], 4)
            updated += 1
        holdings_mv += pos["shares"] * pos.get("last_price", pos["cost_basis"])

    cash        = portfolio.get("cash", 0)
    total_value = holdings_mv + cash

    # Append to history (avoid duplicate date entries)
    history = portfolio.get("history", [])
    if not history or history[-1]["date"] != today_str:
        history.append({
            "date":  today_str,
            "value": round(total_value, 2),
            "cash":  round(cash, 2),
        })
    else:
        # Update today's entry with latest prices
        history[-1]["value"] = round(total_value, 2)

    portfolio["holdings"]    = holdings
    portfolio["total_value"] = round(total_value, 2)
    portfolio["history"]     = history
    portfolio["updated_at"]  = today_str
    return portfolio, updated

def update_spy_history(portfolio, spy_price):
    """Extend SPY benchmark history with today's value."""
    if spy_price is None:
        return portfolio
    today_str   = date.today().isoformat()
    start_value = portfolio.get("start_value", 1_000_000.0)
    spy_history = portfolio.get("spy_history", [])

    # Get SPY price at portfolio start to normalise
    start_spy = None
    if spy_history:
        # Back-calculate: first entry value = start_value (by construction)
        # We need the raw SPY price at start — stored implicitly
        # Simpler: just use the ratio approach from full SPY history in portfolio
        pass

    # If we have existing spy_history, extend it using yfinance full history
    start_date = portfolio.get("start_date", today_str)
    try:
        spy  = yf.Ticker("SPY")
        hist = spy.history(start=start_date, auto_adjust=True)
        if not hist.empty:
            start_price = float(hist["Close"].iloc[0])
            spy_history = [
                {"date": dt.strftime("%Y-%m-%d"),
                 "value": round(start_value * float(row["Close"]) / start_price, 2)}
                for dt, row in hist.iterrows()
            ]
            portfolio["spy_history"] = spy_history
    except Exception as e:
        print(f"  WARNING: SPY history update failed: {e}")

    return portfolio

def main():
    now = datetime.now(timezone.utc)
    print(f"=== Price Updater | {now.strftime('%Y-%m-%d %H:%M UTC')} ===\n")

    p = Path(PORTFOLIO_FILE)
    if not p.exists():
        print(f"ERROR: {PORTFOLIO_FILE} not found. Run grader.py first.")
        return

    portfolio = json.loads(p.read_text())
    holdings  = portfolio.get("holdings", {})

    if not holdings:
        print("  No holdings to update.")
        return

    tickers = list(holdings.keys())
    print(f"  Fetching prices for {len(tickers)} holdings: {', '.join(tickers)}")

    prices = fetch_prices(tickers)
    print(f"  Got prices for {len(prices)}/{len(tickers)} tickers")

    portfolio, updated = update_portfolio_prices(portfolio, prices)
    print(f"  Updated {updated} positions")

    spy_price = fetch_spy_price()
    portfolio = update_spy_history(portfolio, spy_price)

    Path(PORTFOLIO_FILE).write_text(json.dumps(portfolio, indent=2, default=str))

    print(f"\n  Portfolio value: ${portfolio['total_value']:,.0f}")
    print(f"  Holdings: {len(holdings)} | Cash: ${portfolio['cash']:,.0f}")
    print(f"  History entries: {len(portfolio.get('history', []))}")
    print(f"\n  → Now run:  python generate_html.py")


if __name__ == "__main__":
    main()
