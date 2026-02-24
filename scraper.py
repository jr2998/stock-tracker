"""
Stock Tracker Scraper
Pulls data from Finviz for the top 20 companies by market cap
and generates a static index.html file.

Data sources:
  - finvizfinance screener  → ticker list
  - ticker_fundament()      → snapshot fundamentals (market cap, earnings date,
                              EPS/Sales surprise combined field, target price, etc.)
  - Finviz AJAX API         → deeper financials
      statement.ashx?t=X&s=IA  → Annual Income Statement (revenue YoY, EPS YoY)
      statement.ashx?t=X&s=ED  → Earnings/Estimates (quarterly est, revisions)
"""

import json
import time
import requests
from datetime import datetime
import os

from finvizfinance.screener.overview import Overview
from finvizfinance.quote import finvizfinance


# ─── Config ───────────────────────────────────────────────────────────────────
DETAIL_DELAY  = 1.2   # seconds between per-ticker requests
MAX_RETRIES   = 3
AJAX_BASE     = "https://finviz.com/api/statement.ashx"
AJAX_HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finviz.com/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def parse_market_cap_value(cap_str):
    """Convert '5.2B' / '1.23T' / '850M' to float in billions."""
    if not cap_str or str(cap_str).strip() in ("-", "nan", "None", ""):
        return None
    s = str(cap_str).strip().upper()
    try:
        if s.endswith("T"):   return float(s[:-1]) * 1000
        elif s.endswith("B"): return float(s[:-1])
        elif s.endswith("M"): return float(s[:-1]) / 1000
        else:                  return float(s) / 1e9
    except ValueError:
        return None


def get_cap_category(cap_billions):
    if cap_billions is None: return "Unknown"
    if cap_billions >= 200:  return "Mega Cap"
    if cap_billions >= 20:   return "Large Cap"
    if cap_billions >= 2:    return "Mid Cap"
    return "Under $2B"


def pct(value, decimals=1):
    """Format a float as a percentage string, e.g. 12.3%."""
    if value is None:
        return "-"
    return f"{value:+.{decimals}f}%"


def yoy_pct(current, prior):
    """Calculate YoY % change from two numeric strings. Returns formatted string."""
    try:
        c = float(str(current).replace(",", ""))
        p = float(str(prior).replace(",", ""))
        if p == 0:
            return "-"
        return pct((c - p) / abs(p) * 100)
    except (ValueError, TypeError):
        return "-"


def safe_get(d, *keys):
    """Return first non-empty value from dict d for any of the given keys."""
    for k in keys:
        v = d.get(k, "")
        if v and str(v).strip() not in ("-", "nan", "None", ""):
            return str(v).strip()
    return "-"


# ─── Screener ─────────────────────────────────────────────────────────────────

def get_screener_tickers():
    """Return all tickers with market cap >$2B via finvizfinance screener."""
    print("Running Finviz screener (all companies >$2B market cap)...")
    screener = Overview()
    screener.set_filter(filters_dict={"Market Cap.": "+Mid (over $2bln)"})
    df = screener.screener_view(order="Market Cap.", ascend=False, verbose=1)
    if df is None or df.empty:
        print("  Screener returned no results.")
        return []
    tickers = df["Ticker"].dropna().tolist()
    print(f"  {len(tickers)} tickers selected.")
    return tickers


# ─── Per-ticker data fetchers ──────────────────────────────────────────────────

def fetch_fundament(ticker):
    """Fetch snapshot fundamentals dict via finvizfinance. Returns {} on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return finvizfinance(ticker).ticker_fundament() or {}
        except Exception as e:
            print(f"    fundament attempt {attempt} failed for {ticker}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
    return {}


def fetch_ajax(ticker, statement_code):
    """
    Fetch a Finviz AJAX statement table.
      s=IA  = Annual Income Statement
      s=IQ  = Quarterly Income Statement
      s=ED  = Earnings / Estimates (includes revisions)
    Returns parsed JSON dict, or None on failure.
    """
    url = f"{AJAX_BASE}?t={ticker}&s={statement_code}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=AJAX_HEADERS, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    AJAX {statement_code} attempt {attempt} failed for {ticker}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
    return None


# ─── AJAX helpers ─────────────────────────────────────────────────────────────

def ajax_row_map(data):
    """
    Convert Finviz AJAX JSON into a dict: label -> list[str values].
    The JSON looks like:
      { "data": [["Revenue", "100", "110", "120"], ["EPS", "1.0", "1.1", ...]], ... }
    All values are stringified and commas stripped.
    """
    result = {}
    if not data:
        return result
    for row in data.get("data", []):
        if row and len(row) >= 2:
            label = str(row[0]).strip()
            vals  = [str(v).replace(",", "").strip() for v in row[1:]]
            result[label] = vals
    return result


def find_row(row_map, *candidates):
    """Case-insensitive substring match across row_map keys. Returns list or None."""
    for c in candidates:
        cl = c.lower()
        for key, vals in row_map.items():
            if cl in key.lower():
                return vals
    return None


def first_numeric(vals):
    """Return the first value in a list that parses as a float."""
    if not vals:
        return None
    for v in vals:
        v = str(v).strip()
        if v and v not in ("-", "N/A", ""):
            try:
                return float(v)
            except ValueError:
                pass
    return None


def last_numeric(vals):
    """Return the last value in a list that parses as a float."""
    if not vals:
        return None
    for v in reversed(vals):
        v = str(v).strip()
        if v and v not in ("-", "N/A", ""):
            try:
                return float(v)
            except ValueError:
                pass
    return None


def fmt_pct(value, decimals=1):
    """Format float as percentage string with sign, e.g. +12.3%"""
    if value is None:
        return "-"
    return f"{value:+.{decimals}f}%"


def calc_yoy(current_val, prior_val):
    """Calculate YoY % from two floats. Returns formatted string."""
    if current_val is None or prior_val is None or prior_val == 0:
        return "-"
    return fmt_pct((current_val - prior_val) / abs(prior_val) * 100)


# ─── Parse Annual Income (s=IA) ───────────────────────────────────────────────

def parse_annual_income(data):
    """
    Extract from the Annual Income Statement:
      - eps_yy_ttm:      YoY EPS growth % (most recent two reported years)
      - rev_ann_rep:     YoY Revenue growth % (most recent two reported years)
      - rev_ann_est_cur: YoY Revenue growth % (current estimate vs last reported)
      - rev_ann_est_fut: YoY Revenue growth % (next estimate vs current estimate)

    Finviz AJAX headers look like: ["", "2021", "2022", "2023", "2024", "2025E", "2026E"]
    Columns ending in "E" are estimates; others are reported.
    """
    out = {"eps_yy_ttm": "-", "rev_ann_rep": "-",
           "rev_ann_est_cur": "-", "rev_ann_est_fut": "-"}
    if not data:
        return out

    headers    = data.get("headers", [])
    col_labels = [str(h).strip() for h in headers[1:]]  # skip first blank header
    is_est     = [h.upper().endswith("E") for h in col_labels]
    row_map    = ajax_row_map(data)

    # Get numeric values from a row by reported/estimate position
    def get_vals(row, flag):
        """Return list of (float|None) for columns where is_est==flag."""
        if not row:
            return []
        return [first_numeric([v]) if (i < len(row) and is_est[i] == flag) else None
                for i, v in enumerate(row)]

    rev_row = find_row(row_map, "Revenue", "Total Revenue", "Sales")
    eps_row = find_row(row_map, "EPS", "Earnings Per Share")

    if rev_row:
        rep_vals = [first_numeric([v]) for i, v in enumerate(rev_row)
                    if i < len(is_est) and not is_est[i]]
        est_vals = [first_numeric([v]) for i, v in enumerate(rev_row)
                    if i < len(is_est) and is_est[i]]
        if len(rep_vals) >= 2:
            out["rev_ann_rep"]     = calc_yoy(rep_vals[-1], rep_vals[-2])
        if rep_vals and est_vals:
            out["rev_ann_est_cur"] = calc_yoy(est_vals[0], rep_vals[-1])
        if len(est_vals) >= 2:
            out["rev_ann_est_fut"] = calc_yoy(est_vals[1], est_vals[0])

    if eps_row:
        rep_vals = [first_numeric([v]) for i, v in enumerate(eps_row)
                    if i < len(is_est) and not is_est[i]]
        if len(rep_vals) >= 2:
            out["eps_yy_ttm"] = calc_yoy(rep_vals[-1], rep_vals[-2])

    return out


# ─── Parse Earnings/Estimates (s=ED) ─────────────────────────────────────────

def parse_earnings_estimates(data):
    """
    Extract from the Earnings/Estimates page:
      - eps_q_est / eps_q_rep:        EPS quarterly YoY % (estimate & reported)
      - rev_q_est / rev_q_rep:        Revenue quarterly YoY % (estimate & reported)
      - eps_revisions_up/down:        EPS revision counts
      - sales_revisions_up/down:      Sales revision counts

    The ED JSON has multiple sections. Row labels we care about:
      Quarterly estimates: "EPS Estimate", "EPS Actual", "Revenue Estimate", "Revenue Actual"
      Revisions:           "EPS Up", "EPS Down", "Revenue Up", "Revenue Down"
                           (also seen as "Rev Up" / "Rev Down")
    """
    out = {
        "eps_q_est": "-", "eps_q_rep": "-",
        "rev_q_est": "-", "rev_q_rep": "-",
        "eps_revisions_up": "-", "eps_revisions_down": "-",
        "sales_revisions_up": "-", "sales_revisions_down": "-",
    }
    if not data:
        return out

    row_map = ajax_row_map(data)

    # ── Quarterly EPS ──
    eps_est = find_row(row_map, "EPS Estimate", "EPS Est.")
    eps_act = find_row(row_map, "EPS Actual",   "EPS Act.")
    if eps_est and eps_act:
        # YoY est: next quarter estimate vs same quarter a year ago (last actual)
        out["eps_q_est"] = calc_yoy(first_numeric(eps_est), last_numeric(eps_act))
    if eps_act:
        actuals = [v for v in eps_act if v and v not in ("-","N/A","")]
        if len(actuals) >= 2:
            out["eps_q_rep"] = calc_yoy(
                first_numeric([actuals[-1]]), first_numeric([actuals[-2]]))

    # ── Quarterly Revenue ──
    rev_est = find_row(row_map, "Revenue Estimate", "Sales Estimate", "Rev. Estimate")
    rev_act = find_row(row_map, "Revenue Actual",   "Sales Actual",   "Rev. Actual")
    if rev_est and rev_act:
        out["rev_q_est"] = calc_yoy(first_numeric(rev_est), last_numeric(rev_act))
    if rev_act:
        actuals = [v for v in rev_act if v and v not in ("-","N/A","")]
        if len(actuals) >= 2:
            out["rev_q_rep"] = calc_yoy(
                first_numeric([actuals[-1]]), first_numeric([actuals[-2]]))

    # ── Revisions ──
    # These rows typically have a single count value, e.g. ["EPS Up", "12"]
    def revision_val(row):
        if not row:
            return "-"
        v = first_numeric(row)
        return str(int(v)) if v is not None else "-"

    out["eps_revisions_up"]    = revision_val(find_row(row_map, "EPS Up"))
    out["eps_revisions_down"]  = revision_val(find_row(row_map, "EPS Down", "EPS Dn"))
    out["sales_revisions_up"]  = revision_val(find_row(row_map, "Revenue Up", "Rev Up", "Sales Up"))
    out["sales_revisions_down"]= revision_val(find_row(row_map, "Revenue Down", "Rev Down", "Sales Down"))

    return out


# ─── Screener pipeline ────────────────────────────────────────────────────────

def scrape_all_tickers():
    """Fetch ticker_fundament() snapshot for each of the top 20 tickers.
    All required fields are available directly from ticker_fundament() on the
    free tier. The AJAX endpoints return labels only with no values on free
    accounts, so they are not used.
    """
    tickers = get_screener_tickers()
    if not tickers:
        return []

    records = []
    total   = len(tickers)
    for i, ticker in enumerate(tickers):
        print(f"  [{i+1}/{total}] {ticker}...")
        fundament = fetch_fundament(ticker)
        time.sleep(DETAIL_DELAY)
        records.append({"ticker": ticker, "fundament": fundament})

    return records


# ─── Build display record ─────────────────────────────────────────────────────

def build_stock_record(raw):
    """
    Map ticker_fundament() snapshot fields to display columns.

    Confirmed field names from live AAPL debug output:
      'EPS Y/Y TTM'      -> e.g. '25.58%'     (annual EPS growth YoY, TTM)
      'Sales Y/Y TTM'    -> e.g. '10.07%'     (annual revenue growth YoY, TTM)
      'EPS Q/Q'          -> e.g. '18.54%'     (quarterly EPS YoY reported)
      'Sales Q/Q'        -> e.g. '15.65%'     (quarterly revenue YoY reported)
      'EPS/Sales Surpr.' -> e.g. '6.24%3.88%' (two %-tokens concatenated)
      'Target Price'     -> e.g. '297.92'
      'Earnings'         -> e.g. 'Jan 29 AMC'
      'Market Cap'       -> e.g. '3907.83B'
    """
    ticker = raw["ticker"]
    fund   = raw["fundament"]

    # Cap category
    cap_str      = safe_get(fund, "Market Cap")
    cap_val      = parse_market_cap_value(cap_str)
    cap_category = get_cap_category(cap_val)

    # EPS/Sales Surprise: raw value is e.g. '6.24%3.88%' — two %-tokens concatenated.
    # Extract all tokens matching a signed decimal followed by %.
    import re as _re
    surpr_raw   = safe_get(fund, "EPS/Sales Surpr.")
    eps_surpr   = "-"
    sales_surpr = "-"
    if surpr_raw and surpr_raw not in ("-", ""):
        tokens = _re.findall(r"-?\d+\.?\d*%", surpr_raw)
        eps_surpr   = tokens[0] if len(tokens) > 0 else "-"
        sales_surpr = tokens[1] if len(tokens) > 1 else "-"

    return {
        "ticker":          ticker,
        "market_cap":      cap_str,
        "cap_category":    cap_category,
        "next_earnings":   safe_get(fund, "Earnings"),
        # Annual YoY growth (TTM basis) — confirmed direct fields
        "eps_yy_ttm":      safe_get(fund, "EPS Y/Y TTM"),
        "sales_yy_ttm":    safe_get(fund, "Sales Y/Y TTM"),
        # Most recent quarter YoY reported — confirmed direct fields
        "eps_q_rep":       safe_get(fund, "EPS Q/Q"),
        "sales_q_rep":     safe_get(fund, "Sales Q/Q"),
        # Earnings surprise split from combined field
        "eps_surpr":       eps_surpr,
        "sales_surpr":     sales_surpr,
        # Not available on free tier
        "avg_target_price": safe_get(fund, "Target Price"),
    }


def generate_html(stocks, generated_at):
    """Generate the complete index.html with embedded data."""

    stocks_json = json.dumps(stocks, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Stock Tracker — Market Cap &gt; $2B</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:        #0a0c10;
    --surface:   #10131a;
    --border:    #1e2435;
    --accent:    #00e5a0;
    --accent2:   #0066ff;
    --mid:       #f0a500;
    --large:     #4da6ff;
    --mega:      #c084fc;
    --text:      #e2e8f0;
    --muted:     #64748b;
    --positive:  #34d399;
    --negative:  #f87171;
    --font-head: 'Syne', sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
  }}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 13px;
    min-height: 100vh;
    overflow-x: hidden;
  }}

  /* ── Animated grid background ── */
  body::before {{
    content: '';
    position: fixed; inset: 0;
    background-image:
      linear-gradient(rgba(0,229,160,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,229,160,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }}

  .wrapper {{ position: relative; z-index: 1; padding: 2rem; max-width: 1800px; margin: 0 auto; }}

  /* ── Header ── */
  header {{
    display: flex; align-items: flex-end; justify-content: space-between;
    margin-bottom: 2.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap; gap: 1rem;
  }}
  .header-left h1 {{
    font-family: var(--font-head);
    font-size: clamp(1.8rem, 4vw, 3rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1;
    color: #fff;
  }}
  .header-left h1 span {{ color: var(--accent); }}
  .header-left p {{
    margin-top: 0.4rem;
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }}
  .stats {{
    display: flex; gap: 2rem; flex-wrap: wrap;
  }}
  .stat {{
    text-align: right;
  }}
  .stat-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); }}
  .stat-value {{ font-family: var(--font-head); font-size: 1.4rem; font-weight: 700; color: var(--accent); }}

  /* ── Legend ── */
  .legend {{
    display: flex; gap: 1.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; align-items: center;
  }}
  .legend-item {{
    display: flex; align-items: center; gap: 0.4rem;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted);
  }}
  .dot {{
    width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
  }}
  .dot.mid {{ background: var(--mid); }}
  .dot.large {{ background: var(--large); }}
  .dot.mega {{ background: var(--mega); }}

  /* ── Filter bar ── */
  .filters {{
    display: flex; gap: 0.75rem; margin-bottom: 1.25rem; flex-wrap: wrap; align-items: center;
  }}
  .filter-btn {{
    padding: 0.35rem 0.9rem;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .filter-btn:hover, .filter-btn.active {{
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(0,229,160,0.06);
  }}
  .search-wrap {{
    margin-left: auto;
    position: relative;
  }}
  .search-wrap input {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 12px;
    padding: 0.35rem 0.9rem;
    border-radius: 4px;
    width: 200px;
    outline: none;
    transition: border-color 0.15s;
  }}
  .search-wrap input:focus {{ border-color: var(--accent); }}
  .search-wrap input::placeholder {{ color: var(--muted); }}

  /* ── Table container ── */
  .table-wrap {{
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    white-space: nowrap;
  }}

  /* ── Header cells ── */
  thead tr {{
    background: var(--surface);
    border-bottom: 2px solid var(--border);
  }}
  th {{
    padding: 0.75rem 0.9rem;
    font-family: var(--font-head);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--muted);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    position: relative;
    transition: color 0.15s;
  }}
  th:hover {{ color: var(--accent); }}
  th.sort-asc {{ color: var(--accent); }}
  th.sort-asc::after {{ content: ' ↑'; }}
  th.sort-desc {{ color: var(--accent); }}
  th.sort-desc::after {{ content: ' ↓'; }}

  /* ── Data rows ── */
  tbody tr {{
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }}
  tbody tr:hover {{ background: rgba(255,255,255,0.025); }}
  tbody tr.hidden {{ display: none; }}

  td {{
    padding: 0.6rem 0.9rem;
    color: var(--text);
    vertical-align: middle;
  }}

  /* ── Ticker cell ── */
  .cell-ticker {{
    font-family: var(--font-head);
    font-weight: 700;
    font-size: 13px;
    color: #fff;
    letter-spacing: 0.04em;
  }}

  /* ── Cap category badge ── */
  .badge {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}
  .badge-mid   {{ background: rgba(240,165,0,0.15);   color: var(--mid);   border: 1px solid rgba(240,165,0,0.3); }}
  .badge-large {{ background: rgba(77,166,255,0.12);  color: var(--large); border: 1px solid rgba(77,166,255,0.3); }}
  .badge-mega  {{ background: rgba(192,132,252,0.12); color: var(--mega);  border: 1px solid rgba(192,132,252,0.3); }}

  /* ── Positive / Negative values ── */
  .pos {{ color: var(--positive); }}
  .neg {{ color: var(--negative); }}
  .neutral {{ color: var(--muted); }}

  /* ── Footer ── */
  footer {{
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;
  }}
</style>
</head>
<body>
<div class="wrapper">

  <header>
    <div class="header-left">
      <h1>Stock<span>Track</span></h1>
      <p>Market Cap &gt; $2B &nbsp;·&nbsp; Updated every Sunday at 8 PM ET</p>
    </div>
    <div class="stats">
      <div class="stat">
        <div class="stat-label">Total Tickers</div>
        <div class="stat-value" id="total-count">—</div>
      </div>
      <div class="stat">
        <div class="stat-label">Last Updated</div>
        <div class="stat-value" style="font-size:1rem;color:var(--text)">{generated_at}</div>
      </div>
    </div>
  </header>

  <div class="legend">
    <div class="legend-item"><span class="dot mid"></span> Mid Cap ($2B–$20B)</div>
    <div class="legend-item"><span class="dot large"></span> Large Cap ($20B–$200B)</div>
    <div class="legend-item"><span class="dot mega"></span> Mega Cap ($200B+)</div>
  </div>

  <div class="filters">
    <button class="filter-btn active" data-filter="all">All</button>
    <button class="filter-btn" data-filter="Mid Cap">Mid Cap</button>
    <button class="filter-btn" data-filter="Large Cap">Large Cap</button>
    <button class="filter-btn" data-filter="Mega Cap">Mega Cap</button>
    <div class="search-wrap">
      <input type="text" id="ticker-search" placeholder="Search ticker…">
    </div>
  </div>

  <div class="table-wrap">
    <table id="stock-table">
      <thead>
        <tr>
          <th data-col="ticker">Ticker</th>
          <th data-col="market_cap">Mkt Cap</th>
          <th data-col="cap_category">Category</th>
          <th data-col="next_earnings">Next Earnings</th>
          <th data-col="eps_yy_ttm">EPS Y/Y TTM</th>
          <th data-col="sales_yy_ttm">Sales Y/Y TTM</th>
          <th data-col="eps_surpr">EPS Surprise</th>
          <th data-col="sales_surpr">Sales Surprise</th>
          <th data-col="eps_q_rep">EPS Q YoY Rep.</th>
          <th data-col="sales_q_rep">Sales Q YoY Rep.</th>
          <th data-col="avg_target_price">Avg Target</th>
        </tr>
      </thead>
      <tbody id="table-body"></tbody>
    </table>
  </div>

  <footer>
    <span>Data sourced from Finviz.com &nbsp;·&nbsp; For informational purposes only &nbsp;·&nbsp; Not financial advice</span>
    <span>Next update: Sunday 8 PM ET</span>
  </footer>
</div>

<script>
const STOCKS = {stocks_json};

// ── Helpers ──────────────────────────────────────────────────────────────────
function parseNumeric(val) {{
  if (!val || val === '-') return null;
  const clean = val.replace(/[$,B%+]/g, '').trim();
  const n = parseFloat(clean);
  return isNaN(n) ? null : n;
}}

function colorClass(val) {{
  if (!val || val === '-') return 'neutral';
  const str = String(val);
  if (str.startsWith('-')) return 'neg';
  if (str.startsWith('+') || parseFloat(str) > 0) return 'pos';
  return 'neutral';
}}

function badgeClass(cat) {{
  if (cat === 'Mid Cap')   return 'badge badge-mid';
  if (cat === 'Large Cap') return 'badge badge-large';
  if (cat === 'Mega Cap')  return 'badge badge-mega';
  return 'badge';
}}

function cell(val, collapseColor=false) {{
  const cls = collapseColor ? '' : colorClass(val);
  return `<td class="${{cls}}">${{val || '-'}}</td>`;
}}

// ── Render table ─────────────────────────────────────────────────────────────
function renderTable(data) {{
  const tbody = document.getElementById('table-body');
  tbody.innerHTML = '';
  data.forEach(s => {{
    const tr = document.createElement('tr');
    tr.dataset.category = s.cap_category;
    tr.innerHTML = `
      <td class="cell-ticker">${{s.ticker}}</td>
      <td>${{s.market_cap}}</td>
      <td><span class="${{badgeClass(s.cap_category)}}">${{s.cap_category}}</span></td>
      ${{cell(s.next_earnings, true)}}
      ${{cell(s.eps_yy_ttm)}}
      ${{cell(s.sales_yy_ttm)}}
      ${{cell(s.eps_surpr)}}
      ${{cell(s.sales_surpr)}}
      ${{cell(s.eps_q_rep)}}
      ${{cell(s.sales_q_rep)}}
      ${{cell(s.sales_q_rep)}}
      ${{cell(s.avg_target_price, true)}}
    `;
    tbody.appendChild(tr);
  }});
  document.getElementById('total-count').textContent = data.length.toLocaleString();
}}

// ── Sort ─────────────────────────────────────────────────────────────────────
let sortState = {{ col: 'ticker', dir: 'asc' }};

function sortData(data, col, dir) {{
  return [...data].sort((a, b) => {{
    const av = a[col], bv = b[col];
    const an = parseNumeric(av), bn = parseNumeric(bv);
    let cmp;
    if (an !== null && bn !== null) {{
      cmp = an - bn;
    }} else {{
      cmp = String(av || '').localeCompare(String(bv || ''));
    }}
    return dir === 'asc' ? cmp : -cmp;
  }});
}}

document.querySelectorAll('th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.col;
    if (sortState.col === col) {{
      sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
    }} else {{
      sortState.col = col;
      sortState.dir = 'asc';
    }}
    document.querySelectorAll('th').forEach(h => h.classList.remove('sort-asc','sort-desc'));
    th.classList.add(sortState.dir === 'asc' ? 'sort-asc' : 'sort-desc');
    applyFilters();
  }});
}});

// ── Filter ───────────────────────────────────────────────────────────────────
let activeFilter = 'all';
let searchQuery = '';

function applyFilters() {{
  let data = STOCKS;
  if (activeFilter !== 'all') {{
    data = data.filter(s => s.cap_category === activeFilter);
  }}
  if (searchQuery) {{
    data = data.filter(s => s.ticker.toUpperCase().includes(searchQuery.toUpperCase()));
  }}
  data = sortData(data, sortState.col, sortState.dir);
  renderTable(data);
}}

document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    applyFilters();
  }});
}});

document.getElementById('ticker-search').addEventListener('input', e => {{
  searchQuery = e.target.value;
  applyFilters();
}});

// ── Init ─────────────────────────────────────────────────────────────────────
applyFilters();
</script>
</body>
</html>"""

    return html


def main():
    print("=" * 60)
    print("Stock Tracker Scraper")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    stocks_raw = scrape_all_tickers()

    if not stocks_raw:
        print("No data scraped. Exiting.")
        return

    stocks = [build_stock_record(r) for r in stocks_raw]
    # Filter out any sub-$2B that slipped through
    stocks = [s for s in stocks if s["cap_category"] != "Under $2B"]
    stocks.sort(key=lambda s: s["ticker"])

    print(f"\nFinal stock count: {len(stocks)}")

    generated_at = datetime.now().strftime("%b %d, %Y")
    html = generate_html(stocks, generated_at)

    output_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"index.html written ({len(html):,} bytes)")
    print("Done.")


if __name__ == "__main__":
    main()
