# Stock Grader

A fully automated S&P 500 stock screener that scores every company in the index on growth, quality, valuation, and momentum — then simulates a portfolio that buys the best-graded stocks and tracks its performance against the S&P 500. Runs on GitHub Actions and publishes to GitHub Pages.

---

## What it does

Every week, the pipeline scrapes fundamentals for ~530 tickers (S&P 500 + a curated large-cap watchlist) from Yahoo Finance, runs each one through a scoring model, assigns a letter grade A–F, and publishes an interactive website. Every weekday, a lightweight price update refreshes the simulated portfolio without re-scraping.

The website has two pages:

- **Stock Data** — a sortable, filterable table of every stock with 26 columns spanning growth, valuation, quality, and momentum metrics
- **Performance Tracker** — a chart and holdings breakdown for the simulated portfolio, benchmarked against SPY

---

## Pipeline

```
Weekly (Sunday 11 PM ET)        Daily (Mon–Fri 9 PM ET)
─────────────────────────       ───────────────────────
scraper.py                      price_updater.py
   ↓ raw_data.json                  ↓ portfolio.json (prices only)
grader.py                       generate_html.py
   ↓ data.json                      ↓ index.html
   ↓ portfolio.json (holds/sells/fills)

One-time reset (manual trigger)
────────────────────────────────
scraper.py → grader.py → reset_portfolio.py → generate_html.py
```

| Script | Role | Runtime |
|---|---|---|
| `scraper.py` | Fetches fundamentals for every ticker via yfinance | ~45–60 min |
| `grader.py` | Scores and grades each stock; runs buy-and-hold portfolio logic | ~5 seconds |
| `reset_portfolio.py` | One-time script to build a clean 25-stock portfolio | ~5 seconds |
| `price_updater.py` | Refreshes held-position prices only | ~15 seconds |
| `generate_html.py` | Renders `index.html` from `data.json` + `portfolio.json` | ~1 second |

The grader is intentionally decoupled from the scraper. To adjust the scoring model without re-scraping, edit the anchor tables or weights in `grader.py` — it reads the existing `raw_data.json` and produces a new `data.json` in seconds when triggered via the `weekly` workflow mode.

---

## Grading model

Each stock receives a composite score from 0–100, then a letter grade based on that score. The model is tuned to surface **strong growth stocks with solid fundamentals** — it rewards accelerating earnings more than cheap valuation.

### Grade thresholds

| Grade | Score | Interpretation |
|---|---|---|
| **A** | ≥ 78 | Exceptional — top ~15% of the universe |
| **B** | 65–77 | Good — above-average growth and quality |
| **C** | 52–64 | Average — mediocre but not broken |
| **D** | 38–51 | Weak — meaningful problems in at least one area |
| **F** | < 38 | Poor — declining fundamentals or badly overvalued |

### Category weights

| Category | Weight | What it captures |
|---|---|---|
| **Growth** | 45% | Revenue and EPS trajectory, acceleration, and earnings beats |
| **Quality** | 30% | Margin structure, return on capital, balance sheet strength |
| **Valuation** | 15% | How much you're paying relative to growth and earnings power |
| **Momentum** | 10% | Price trend and analyst forward expectations |

### Metrics and effective weights

Every raw metric is mapped to a 0–100 score via interpolated anchor tables, calibrated so that a median S&P 500 result scores approximately 50. Scores above 80 require top-decile results.

**Growth (45% of overall)**

| Metric | Sub-weight | Effective weight | Notes |
|---|---|---|---|
| EPS Growth TTM | 36% | **16.2%** | Trailing-twelve-month EPS growth YoY. Weighted above revenue growth because EPS leverage (growing earnings faster than revenue) is the hallmark of quality compounders. |
| Rev Growth TTM | 28% | **12.6%** | Trailing-twelve-month revenue growth YoY. |
| EPS Acceleration | 16% | **7.2%** | Change in EPS YoY growth rate vs the prior quarter (percentage points). Positive = margins are expanding. |
| Rev Acceleration | 12% | **5.4%** | Change in revenue YoY growth rate vs the prior quarter (pp). |
| Earnings Surprise | 8% | **3.6%** | Most recent quarter EPS beat vs analyst consensus. |

**Quality (30% of overall)**

| Metric | Sub-weight | Effective weight | Notes |
|---|---|---|---|
| Operating Margin | 30% | **9.0%** | Best cross-sector profitability signal — captures R&D and SG&A efficiency, not just pricing power. |
| ROE | 28% | **8.4%** | Return on Equity. The single best measure of whether a business earns exceptional returns on capital. |
| Gross Margin | 18% | **5.4%** | Reflects pricing power and cost structure. Sector-dependent — used as a secondary signal rather than primary. |
| ROA | 14% | **4.2%** | Return on Assets. Particularly informative for asset-light businesses. |
| Debt/Equity | 10% | **3.0%** | Balance sheet risk penalty. Excluded for Financials and Utilities, where leverage is structural. |

**Valuation (15% of overall)**

| Metric | Sub-weight | Effective weight | Notes |
|---|---|---|---|
| PEG Ratio | 42% | **6.3%** | Price/Earnings-to-Growth. Adjusts P/E for expected growth rate — the best single valuation signal for a growth-focused screener. &lt;1 = cheap vs growth; &gt;3.5 = expensive. |
| EV/EBITDA | 28% | **4.2%** | Enterprise Value / EBITDA. Works across capital structures; preferred over raw P/E for capital-intensive companies. |
| Forward P/E | 20% | **3.0%** | Next-twelve-month P/E. Intentionally tolerant of high multiples on high-growth stocks. |
| Price/Sales | 10% | **1.5%** | Weakest signal for large profitable companies; retained as a tiebreaker for revenue-stage businesses. |

**Momentum (10% of overall)**

| Metric | Sub-weight | Effective weight | Notes |
|---|---|---|---|
| Analyst Upside | 42% | **4.2%** | Consensus price target upside from current price. Forward-looking — analysts are pricing in the next 12 months. |
| 52W Performance | 38% | **3.8%** | Trailing 52-week price return. Trend confirmation signal. |
| Analyst Rec | 20% | **2.0%** | Consensus recommendation (Strong Buy → Sell). Useful as a directional signal but trimmed because analyst downgrades tend to lag reality. |

### Sector adjustments

Debt/Equity is excluded from scoring for **Financials** and **Utilities** — leverage is a core part of their business model, not a risk signal.

---

## Portfolio

The portfolio starts with $1,000,000 and holds the top 25 stocks by score, allocated proportionally to conviction. Positions are held for the long term — the weekly run does the minimum necessary to keep the portfolio healthy, not routine rebalancing.

### Construction

At initialisation, capital is allocated across the top 25 eligible stocks (score ≥ 65) using score-weighted sizing. A stock scoring 88 receives meaningfully more capital than one scoring 70 — not just proportionally more, but with a super-linear exponent (`score^1.5`) that rewards top-tier conviction. Individual positions are capped at 10% and floored at 1.5%, then renormalised to sum to 100%.

### Weekly behaviour

The weekly run has three narrowly-scoped actions:

**Sell** — a position is sold only when its grade drops below C (score < 52), indicating genuine fundamental deterioration. Price movements alone never trigger a sell.

**Trim** — a position is trimmed only when its market value grows beyond 2× its original target dollar allocation. Short-term gains (positions held less than 365 days) are protected from trimming even at this threshold, since the tax cost of realising a short-term gain typically outweighs the portfolio benefit.

**Fill** — any slot vacated by a sell or trim is immediately filled with the highest-scoring eligible stock not already held, up to the 25-position cap. Existing positions are never topped up week-to-week.

A normal week with no grade changes and no extreme price moves produces zero trades.

### Daily behaviour

Every weeknight, prices are refreshed for all held positions and the SPY benchmark is updated. No trades are executed.

### Performance Tracker

The Performance Tracker page shows portfolio value vs S&P 500 (SPY) from inception, current holdings with cost basis, gain/loss, current weight vs target weight, and days held, plus a full trade history log.

---

## Website features

### Stock Data page

- **26 columns** across four column groups: Info, Growth, Valuation, Quality, Momentum
- **Column tooltips** — hover any column header for a description of the metric and its weight in the model
- **Sort** by any column (click header to toggle ascending/descending)
- **Filter by grade** — one-click buttons to show only A, B, C, D, or F stocks
- **Filter by sector** — dropdown covering all 11 GICS sectors
- **Search** by ticker or company name
- **Score bar** — every stock shows a mini progress bar coloured by grade alongside its numeric score
- Sticky first two columns (Ticker, Name) so they stay visible when scrolling right

### Performance Tracker page

- **KPI cards** — current portfolio value, total return %, number of holdings, and trade count
- **Return chart** — portfolio vs S&P 500 (SPY) as % return from inception, with hover tooltips
- **Holdings table** — all current positions with shares, cost basis, current price, market value, gain/loss, current weight, target weight, drift from target, days held, and buy date
- **Trade history** — full log of every buy, sell, and trim with date, price, and realised gain %

---

## Data source and disclaimer

All data is sourced from Yahoo Finance via [yfinance](https://github.com/ranaroussi/yfinance). Data may be delayed, incomplete, or incorrect. This project is for informational and educational purposes only. **Not financial advice.**
