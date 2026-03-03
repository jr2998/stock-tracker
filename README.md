# Stock Grader v2

A self-updating stock dashboard that grades large-cap US companies (>$20B market cap) across growth, valuation, profitability, and momentum metrics using free data from Yahoo Finance.

## Setup

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO
pip install -r requirements.txt

# Fetch data and generate the site
python scraper.py        # ~30–45 min for full universe
python generate_html.py  # instant
```

Open `index.html` in a browser locally, or push to GitHub Pages.

## GitHub Pages Setup

1. Push this repo to GitHub
2. Go to **Settings → Pages → Source** → set to `main` branch, `/ (root)` folder
3. Enable the Actions workflow under **Actions → Update Stock Data → Enable**
4. Run it manually the first time via **Run workflow**
5. Your site will be at `https://YOUR-USERNAME.github.io/YOUR-REPO/`

The workflow runs automatically every Monday at midnight UTC. Change the cron schedule in `.github/workflows/update.yml` as desired.

---

## Grading System

Each stock receives an **A–F grade** based on a weighted composite score (0–4 scale).

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 3.3–4.0 | Exceptional across the board |
| B | 2.6–3.2 | Good, with minor weaknesses |
| C | 1.9–2.5 | Average — not compelling either way |
| D | 1.2–1.8 | Multiple concerning signals |
| F | < 1.2 | Failing on most dimensions |

### Category Weights

| Category | Weight | Rationale |
|----------|--------|-----------|
| Growth | 35% | Core question for large caps: is the business still expanding? |
| Valuation | 25% | Even great companies are bad investments at the wrong price |
| Profitability | 25% | Ensures growth isn't destroying value |
| Momentum/Sentiment | 15% | Real signal but noisy — given least weight |

---

## Metrics

### Growth (35% of grade)

| Metric | Source | What it measures |
|--------|--------|-----------------|
| **Rev Growth TTM** | Quarterly income stmt | Revenue YoY growth, trailing twelve months. The most fundamental measure of whether a business is expanding. |
| **EPS Growth TTM** | Quarterly income stmt | Earnings-per-share YoY growth, TTM. Growing revenue that doesn't translate to growing EPS is a red flag. |
| **Rev Acceleration** | Quarterly income stmt | Current quarter revenue YoY minus prior quarter YoY. Positive = business is speeding up. One of the strongest bullish signals. |
| **EPS Acceleration** | Quarterly income stmt | Same for EPS. Acceleration in both revenue and EPS simultaneously is the core CANSLIM signal. |
| **EPS Surprise** | yfinance earnings_dates | How much actual EPS beat/missed analyst estimates last quarter. Consistent beaters tend to keep beating. |

### Valuation (25% of grade)

| Metric | Source | What it measures |
|--------|--------|-----------------|
| **Forward P/E** | yfinance info | Price / next-twelve-months estimated earnings. Lower = cheaper, but must be read relative to growth rate. |
| **PEG Ratio** | yfinance info | Forward P/E ÷ EPS growth rate. The single most useful valuation metric for growth stocks — normalizes price for growth. <1 = undervalued, >2 = expensive. |
| **EV/EBITDA** | yfinance info | Enterprise Value / EBITDA. Better than P/E for comparing companies with different capital structures. <10 = cheap, >30 = expensive. |
| **Price/Sales** | yfinance info | Useful for low/negative earnings companies; harder to manipulate than earnings-based metrics. |

### Profitability (25% of grade)

| Metric | Source | What it measures |
|--------|--------|-----------------|
| **Gross Margin** | yfinance info | Revenue minus COGS as % of revenue. High margins (>50%) indicate pricing power and defensible business model. Sticky once established. |
| **Operating Margin** | yfinance info | Operating earnings as % of revenue. Measures management efficiency. Expanding margins over time = strong quality signal. |
| **ROE** | yfinance info | Net income / shareholder equity. How efficiently the company uses capital. >15% solid, >25% excellent. |
| **ROA** | yfinance info | Net income / total assets. Cleaner than ROE — not distorted by leverage. >10% = strong. |
| **Debt/Equity** | yfinance info | Total debt / equity. High debt amplifies risk. Not scored for banks/utilities (structural leverage). |

### Momentum & Sentiment (15% of grade)

| Metric | Source | What it measures |
|--------|--------|-----------------|
| **52W Performance** | yfinance history | 1-year price return. Price momentum is one of the most documented factors in academic finance. |
| **Analyst Upside** | yfinance info | % gap between current price and consensus analyst price target. |
| **Analyst Rec** | yfinance info | Consensus analyst rating (1=Strong Buy → 5=Sell). Converted to 0–4 score. |

---

## Notes

- **Sector adjustments**: Financials and Utilities are excluded from the Debt/Equity score (structural leverage is normal). REITs skip Forward P/E (P/FFO is the correct metric but not available in yfinance).
- **Missing data**: Many metrics are absent for some tickers. The grade is computed from available metrics only — a stock with fewer data points gets a grade based on what's available.
- **Use within sectors**: The grade is most meaningful when comparing companies in the same sector. A utility will almost always score lower on growth than a software company — sector context matters.
- **Not financial advice**: This tool is for research and learning only.
