"""
grader.py  —  Stock Grader (standalone)
========================================
Reads raw_data.json produced by scraper.py, applies the scoring model and
letter-grade assignment, writes data.json, then re-runs the portfolio update.

Run any time you want to change grading criteria WITHOUT re-scraping:
    python grader.py

The grading logic lives entirely in this file.  Edit the anchor tables or
weights below, then run this script — the full cycle takes a few seconds.
"""

import json
import math
from datetime import date
from pathlib import Path

RAW_FILE       = "raw_data.json"
OUTPUT_FILE    = "data.json"
PORTFOLIO_FILE = "portfolio.json"

# Portfolio buy/sell thresholds — keep in sync with grade boundaries
BUY_THRESHOLD    = 65.0   # buy A and B rated stocks (overall >= 65)
SELL_THRESHOLD   = 52.0   # sell when grade drops to C (overall < 52)
RESET_PORTFOLIO  = True   # set to False after first run to preserve history

# ── Rebalancing parameters ────────────────────────────────────────────────────
# Weights are score-proportional with a super-linear exponent so that a
# score of 88 receives meaningfully more capital than a score of 70.
CONVICTION_POWER  = 1.5   # score exponent: 1.0=linear, 2.0=very concentrated
MAX_POSITION      = 0.10  # no single holding exceeds 10% of portfolio
MIN_POSITION      = 0.015 # no eligible holding falls below 1.5%
DRIFT_THRESHOLD   = 0.03  # 3pp absolute drift before acting on underweights
OVERWEIGHT_THRESH = 0.05  # 5pp over target before trimming (absent tax concern)
MIN_TRADE_USD     = 2_000 # ignore any trade worth less than this (prevents churn)
# Tax-aware trimming
SHORT_TERM_DAYS   = 365   # positions held < 365 days attract short-term CGT
SHORT_TERM_RATE   = 0.35  # assumed marginal tax rate on short-term gains
TAX_HURDLE_DRIFT  = 0.04  # ST gain positions need 4pp extra drift to justify trim

# ─────────────────────────────────────────────────────────────────────────────
# SCORING MODEL
# ─────────────────────────────────────────────────────────────────────────────
# ─── Scoring ──────────────────────────────────────────────────────────────────
#
# DESIGN
# ──────
# Every metric maps directly to a 0–100 score via anchor-point interpolation.
# Anchors are calibrated so that a median large-cap S&P 500 result on any given
# metric scores ~50.  Top-decile results score ~87-95.  The score is then
# interpreted as follows:
#
#   A  ≥ 78   Top ~15%: strong growth, good margins, reasonable valuation
#   B  ≥ 65   Top ~35%: above-average, solid fundamentals
#   C  ≥ 52   Middle:   mediocre — acceptable but uninspiring
#   D  ≥ 38   Below average: weaknesses outweigh strengths
#   F  < 38   Bottom ~20%: declining, poor quality, or badly overvalued
#
# CATEGORY WEIGHTS  (growth-focused model)
#   Growth    50%  — accel weighted more heavily; markets price in future growth
#   Quality   28%  — op margin + ROE dominate; gross margin reduced (sector-biased)
#   Valuation 15%  — PEG now 50% within category; EV/EBITDA + P/S trimmed
#   Momentum   7%  — reduced; analyst signals are noisy/lagging

FINANCIALS_SECTORS = {"Financial Services", "Financials"}
UTILITIES_SECTORS  = {"Utilities"}


def _interp(value, anchors):
    """
    Map a raw value to 0–100 using (raw_value, score) anchor pairs.
    Anchors must be sorted ascending by raw_value.
    Clamps to the first/last score outside the anchor range.
    Returns None if value is None.
    """
    if value is None:
        return None
    if value <= anchors[0][0]:
        return float(anchors[0][1])
    if value >= anchors[-1][0]:
        return float(anchors[-1][1])
    for i in range(len(anchors) - 1):
        lo_v, lo_s = anchors[i]
        hi_v, hi_s = anchors[i + 1]
        if lo_v <= value <= hi_v:
            t = (value - lo_v) / (hi_v - lo_v)
            return round(lo_s + t * (hi_s - lo_s), 1)
    return None


def _wavg(pairs):
    """Weighted average of (score, weight) pairs; gracefully skips None scores."""
    ws = wt = 0.0
    for sc, w in pairs:
        if sc is not None:
            ws += sc * w
            wt += w
    return round(ws / wt, 1) if wt > 0 else None


# ─────────────────────────────────────────────────────────────────────────────
# ANCHOR TABLES  (raw_value → 0-100 score)
# For "lower is better" metrics (P/E, D/E, etc.) the table is simply written
# with descending scores as raw values increase — no reverse flag needed.
# ─────────────────────────────────────────────────────────────────────────────

# GROWTH ──────────────────────────────────────────────────────────────────────
# Revenue growth YoY% (TTM)   median S&P ~5-6%  →  score 50
A_REV_GROWTH = [(-20,0),(-5,15),(0,30),(5,50),(12,70),(25,87),(50,100)]

# EPS growth YoY% (TTM)       median S&P ~7-9%  →  score 50
A_EPS_GROWTH = [(-20,0),(-5,15),(0,30),(8,50),(20,70),(40,87),(80,100)]

# Revenue acceleration (pp change in YoY growth rate)
# 0pp = flat / median;  +5pp = genuinely accelerating;  +15pp = strong
A_REV_ACCEL  = [(-15,5),(-5,25),(0,45),(3,58),(7,72),(15,87),(25,100)]

# EPS acceleration (same interpretation)
A_EPS_ACCEL  = [(-15,5),(-5,25),(0,45),(3,58),(7,72),(15,87),(25,100)]

# EPS surprise % vs consensus estimate
# Typical large-cap beat = 3-5%;  >10% = notably large beat
A_SURPRISE   = [(-15,0),(-3,20),(0,40),(4,58),(8,72),(12,85),(20,100)]

# QUALITY ─────────────────────────────────────────────────────────────────────
# Gross margin%   sector-dependent; strong SaaS/tech = 65-75%; industrials = 30-40%
A_GROSS_MGN  = [(-10,0),(5,15),(20,30),(35,50),(50,68),(65,82),(75,92),(85,100)]

# Operating margin%   median S&P ~14%;  >25% = strong;  >40% = elite
A_OP_MGN     = [(-20,0),(-5,15),(0,25),(7,42),(14,55),(22,70),(32,83),(45,100)]

# Return on Equity%   median S&P ~18%;  <0 = losing money;  >40% = exceptional
A_ROE        = [(-20,0),(0,18),(8,38),(18,55),(30,72),(45,87),(70,100)]

# Return on Assets%   median ~6%;  >16% = excellent capital efficiency
A_ROA        = [(-10,0),(0,22),(3,38),(6,52),(10,68),(16,82),(25,100)]

# Debt/Equity   LOWER is better.
# 0 = debt-free (90);  0.5-1 = healthy (65-72);  2+ = elevated (30);  5+ = concerning
A_DE_INV     = [(0,90),(0.3,78),(0.7,65),(1.2,50),(2.0,32),(3.5,18),(6.0,5),(10,0)]

# VALUATION ───────────────────────────────────────────────────────────────────
# PEG ratio (lower = better value-for-growth)
# <1 = cheap vs growth(90);  1.5-2.5 = fair(55-70);  >5 = expensive(18)
# NOTE: High-growth stocks are EXPECTED to have high P/E — PEG adjusts for that.
A_PEG_INV    = [(0.3,95),(0.8,85),(1.5,70),(2.5,50),(3.5,32),(5.0,18),(8.0,5),(12,0)]

# Forward P/E (lower = better, but high P/E on growth stocks is tolerated)
# 15=cheap(78), 25=fair-for-growth(58), 40=elevated(35), 60=steep(15)
# Intentionally generous: a 35x P/E on 25%-growth stock is not alarming.
A_FWD_PE_INV = [(8,90),(15,78),(22,65),(30,52),(40,38),(55,22),(70,10),(90,3)]

# EV/EBITDA (lower = better)   10=cheap(75);  20=fair(55);  35=premium(32)
A_EV_INV     = [(4,90),(10,75),(18,55),(28,38),(40,22),(60,8),(80,2)]

# Price/Sales (lower = better, but high-margin businesses deserve premium)
# 1.5=cheap(72);  4=fair-ish(55);  10=premium(38);  22=steep(12)
A_PS_INV     = [(0.3,88),(1.5,72),(4,55),(8,40),(14,25),(22,12),(35,3)]

# MOMENTUM ────────────────────────────────────────────────────────────────────
# 52-week price performance%
# -10%=lagging(30);  0%=flat(42);  12%=in line with market(58);  35%=outperforming(80)
A_PERF_52W   = [(-50,3),(-20,18),(-5,33),(0,42),(12,58),(25,72),(40,85),(70,100)]

# Analyst consensus price target upside%
# 0%=fully priced(38);  10%=typical(58);  25%=bullish(76);  45%=very bullish(90)
A_UPSIDE     = [(-25,3),(-5,22),(0,38),(5,50),(12,62),(22,76),(35,88),(55,100)]

# Analyst recommendation (1=Strong Buy, 5=Sell) — mapped to score directly
A_REC_INV    = [(1.0,100),(1.5,88),(2.0,72),(2.5,55),(3.0,35),(3.5,18),(4.0,8),(5.0,0)]


def score_record(raw):
    sector  = raw.get("sector", "")
    is_fin  = sector in FINANCIALS_SECTORS
    is_util = sector in UTILITIES_SECTORS
    s = {}

    # ── Growth (45%) ──────────────────────────────────────────────────────
    s["rev_growth_ttm"]    = _interp(raw.get("rev_growth_ttm"),    A_REV_GROWTH)
    s["eps_growth_ttm"]    = _interp(raw.get("eps_growth_ttm"),    A_EPS_GROWTH)
    s["rev_accel"]         = _interp(raw.get("rev_accel"),         A_REV_ACCEL)
    s["eps_accel"]         = _interp(raw.get("eps_accel"),         A_EPS_ACCEL)
    s["earnings_surprise"] = _interp(raw.get("earnings_surprise"), A_SURPRISE)
    s["growth"] = _wavg([
        (s["eps_growth_ttm"],    0.36),   # EPS growth leads — operating leverage matters
        (s["rev_growth_ttm"],    0.28),   # revenue growth still core signal
        (s["eps_accel"],         0.16),   # EPS acceleration: are margins expanding?
        (s["rev_accel"],         0.12),   # revenue acceleration
        (s["earnings_surprise"], 0.08),   # beaten-and-raised catalyst
    ])

    # ── Quality (30%) ─────────────────────────────────────────────────────
    s["gross_margin"]     = _interp(raw.get("gross_margin"),     A_GROSS_MGN)
    s["operating_margin"] = _interp(raw.get("operating_margin"), A_OP_MGN)
    s["roe"]              = _interp(raw.get("roe"),              A_ROE)
    s["roa"]              = _interp(raw.get("roa"),              A_ROA)
    s["debt_equity"]      = None if (is_fin or is_util) else                             _interp(raw.get("debt_equity"),      A_DE_INV)
    s["quality"] = _wavg([
        (s["operating_margin"], 0.30),   # best cross-sector profitability signal
        (s["roe"],              0.28),   # best capital efficiency — separates great from good
        (s["gross_margin"],     0.18),   # pricing power signal; reduced (correlated w/ op margin)
        (s["roa"],              0.14),   # asset efficiency; boosted (esp. for asset-light cos)
        (s["debt_equity"],      0.10),   # balance sheet risk penalty
    ])

    # ── Valuation (15%) ───────────────────────────────────────────────────
    s["peg_ratio"]   = _interp(raw.get("peg_ratio"),   A_PEG_INV)
    s["forward_pe"]  = _interp(raw.get("forward_pe"),  A_FWD_PE_INV)
    s["ev_ebitda"]   = _interp(raw.get("ev_ebitda"),   A_EV_INV)
    s["price_sales"] = _interp(raw.get("price_sales"), A_PS_INV)
    s["valuation"] = _wavg([
        (s["peg_ratio"],   0.42),   # best growth-adjusted metric
        (s["ev_ebitda"],   0.28),   # universal: works across capital structures
        (s["forward_pe"],  0.20),   # trimmed: largely captured by PEG
        (s["price_sales"], 0.10),   # weakest for large profitable cos; kept as tiebreaker
    ])

    # ── Momentum (10%) ────────────────────────────────────────────────────
    s["perf_52w"]       = _interp(raw.get("perf_52w"),       A_PERF_52W)
    s["analyst_upside"] = _interp(raw.get("analyst_upside"), A_UPSIDE)
    s["analyst_rec"]    = _interp(raw.get("analyst_rec"),    A_REC_INV)
    s["momentum"] = _wavg([
        (s["analyst_upside"], 0.42),   # forward-looking; analysts price in next 12m
        (s["perf_52w"],       0.38),   # trend confirmation
        (s["analyst_rec"],    0.20),   # lagging but directionally useful
    ])

    # ── Overall ───────────────────────────────────────────────────────────
    overall = _wavg([
        (s["growth"],    0.45),
        (s["quality"],   0.30),
        (s["valuation"], 0.15),
        (s["momentum"],  0.10),
    ])

    grade = "-"
    if overall is not None:
        if overall >= 78:   grade = "A"
        elif overall >= 65: grade = "B"
        elif overall >= 52: grade = "C"
        elif overall >= 38: grade = "D"
        else:               grade = "F"

    grade_color = {"A":"grade-a","B":"grade-b","C":"grade-c",
                   "D":"grade-d","F":"grade-f"}.get(grade, "neutral")

    return {
        **raw,
        "scores":      s,
        "growth_avg":  s["growth"],
        "val_avg":     s["valuation"],
        "prof_avg":    s["quality"],
        "mom_avg":     s["momentum"],
        "overall":     overall,
        "grade":       grade,
        "grade_color": grade_color,
    }



# ─── Format helpers ───────────────────────────────────────────────────────────

def fmt_pct(val, d=1):
    return f"{val:+.{d}f}%" if val is not None else None

def fmt_num(val, d=1):
    return f"{val:.{d}f}x" if val is not None else None

def fmt_cap(b):
    if b is None: return None
    return f"${b/1000:.2f}T" if b >= 1000 else f"${b:.1f}B"

def fmt_price(val):
    return f"${val:,.2f}" if val is not None else None

def format_record(rec):
    r = rec
    return {
        "ticker":           r["ticker"],
        "name":             r["name"],
        "sector":           r["sector"],
        "industry":         r["industry"],
        "grade":            r["grade"],
        "grade_color":      r["grade_color"],
        "overall":          r["overall"],
        "growth_avg":       r["growth_avg"],
        "val_avg":          r["val_avg"],
        "prof_avg":         r["prof_avg"],
        "mom_avg":          r["mom_avg"],
        "market_cap":       fmt_cap(r["market_cap_b"]),
        "market_cap_b":     r["market_cap_b"],
        "price":            fmt_price(r["price"]),
        "price_raw":        r["price"],
        "target_price":     fmt_price(r["target_price"]),
        "analyst_upside":   fmt_pct(r["analyst_upside"]),
        "analyst_rec_raw":  r["analyst_rec"],
        "analyst_rec_label": r.get("analyst_rec_label"),
        "perf_52w":         fmt_pct(r["perf_52w"]),
        "forward_pe":       fmt_num(r["forward_pe"]),
        "peg_ratio":        fmt_num(r["peg_ratio"]),
        "ev_ebitda":        fmt_num(r["ev_ebitda"]),
        "price_sales":      fmt_num(r["price_sales"]),
        "rev_growth_ttm":   fmt_pct(r["rev_growth_ttm"]),
        "eps_growth_ttm":   fmt_pct(r["eps_growth_ttm"]),
        "rev_accel":        fmt_pct(r["rev_accel"]),
        "eps_accel":        fmt_pct(r["eps_accel"]),
        "earnings_surprise":fmt_pct(r["earnings_surprise"]),
        "gross_margin":     fmt_pct(r["gross_margin"]),
        "operating_margin": fmt_pct(r["operating_margin"]),
        "profit_margin":    fmt_pct(r["profit_margin"]),
        "roe":              fmt_pct(r["roe"]),
        "roa":              fmt_pct(r["roa"]),
        "debt_equity":      fmt_num(r["debt_equity"], 2),
        "next_earnings":    r["next_earnings"],
        "scores":           r["scores"],
    }




# ─── Portfolio management (self-contained — no dependency on scraper.py) ─────

PORTFOLIO_START = 1_000_000.0

def load_portfolio():
    p = Path(PORTFOLIO_FILE)
    return json.loads(p.read_text()) if p.exists() else None

def save_portfolio(portfolio):
    Path(PORTFOLIO_FILE).write_text(json.dumps(portfolio, indent=2, default=str))

def _get_spy_history(start_date):
    """Fetch SPY price history normalised to PORTFOLIO_START for benchmark chart."""
    try:
        import yfinance as yf
        spy  = yf.Ticker("SPY")
        hist = spy.history(start=start_date, auto_adjust=True)
        if hist.empty:
            return []
        start_price = float(hist["Close"].iloc[0])
        return [
            {"date": dt.strftime("%Y-%m-%d"),
             "value": round(PORTFOLIO_START * float(row["Close"]) / start_price, 2)}
            for dt, row in hist.iterrows()
        ]
    except Exception as e:
        print(f"  WARNING: Could not fetch SPY history: {e}")
        return []

def _refresh_spy(portfolio):
    """Extend SPY benchmark history to today."""
    start = portfolio.get("start_date", date.today().isoformat())
    spy_h = _get_spy_history(start)
    if spy_h:
        portfolio["spy_history"] = spy_h
    return portfolio

def _target_weights(eligible_records):
    """
    Compute score-weighted target allocations for all eligible stocks.

    Uses a super-linear conviction exponent so a score of 88 receives
    meaningfully more capital than a score of 70 — not just proportionally
    more.  Positions are then clamped between MIN_POSITION and MAX_POSITION
    and renormalised to sum to 1.0.

    Returns {ticker: target_fraction}, e.g. {"NVDA": 0.088, "META": 0.081}
    """
    if not eligible_records:
        return {}

    raw = {r["ticker"]: r["overall"] ** CONVICTION_POWER for r in eligible_records}
    total_raw = sum(raw.values()) or 1.0
    w = {t: v / total_raw for t, v in raw.items()}
    w = {t: max(MIN_POSITION, min(MAX_POSITION, wt)) for t, wt in w.items()}
    total_w = sum(w.values()) or 1.0
    return {t: wt / total_w for t, wt in w.items()}


def _days_held(pos, today):
    """Return how many days a position has been held (None-safe)."""
    bd = pos.get("bought_date")
    if not bd:
        return 9999   # treat missing date as long-term
    try:
        return (today - date.fromisoformat(bd)).days
    except (ValueError, TypeError):
        return 9999


def _is_short_term_gain(pos, cur_price, today):
    """True if the position has an unrealised gain AND was bought < 365 days ago."""
    return (_days_held(pos, today) < SHORT_TERM_DAYS
            and cur_price > pos.get("cost_basis", cur_price))


def _trim_shares(ticker, pos, cur_price, trim_usd, today_str, cash, trades):
    """
    Sell `trim_usd` worth of shares from an existing position.
    Mutates pos, cash (returned), and appends to trades.
    """
    shares_to_sell = min(trim_usd / cur_price, pos["shares"])
    if shares_to_sell <= 0:
        return cash
    proceeds   = shares_to_sell * cur_price
    gain_pct   = round((cur_price - pos["cost_basis"]) / pos["cost_basis"] * 100, 2)                  if pos.get("cost_basis") else 0
    pos["shares"] = round(pos["shares"] - shares_to_sell, 6)
    pos["last_price"] = round(cur_price, 4)
    cash += proceeds
    trades.append({
        "date": today_str, "action": "TRIM", "ticker": ticker,
        "shares": round(shares_to_sell, 6), "price": round(cur_price, 2),
        "proceeds": round(proceeds, 2), "gain_pct": gain_pct,
    })
    print(f"    TRIM {ticker}: {shares_to_sell:.4f} sh @ ${cur_price:.2f}"
          f"  (gain {gain_pct:+.1f}%,  proceeds ${proceeds:,.0f})")
    return cash


def _update_portfolio(records, portfolio):
    """
    Smart tax-aware rebalancing.

    Pass 1 — Forced sells: grade has dropped below SELL_THRESHOLD or ticker
              vanished from the universe.  Always executed regardless of tax.

    Pass 2 — Compute target weights across all current + new eligible tickers.

    Pass 3 — Trims: positions significantly over their target weight.
              - Long-term positions (≥365 days): trim if > target + OVERWEIGHT_THRESH
              - Short-term LOSS positions: trim freely (tax-loss harvesting)
              - Short-term GAIN positions: trim only if drift > TAX_HURDLE_DRIFT
              - All trims: minimum trade size of MIN_TRADE_USD

    Pass 4 — Buys: new eligible tickers not yet held, bought at target weight.
              Existing under-weight positions get topped-up if cash is available
              and the shortfall exceeds DRIFT_THRESHOLD + MIN_TRADE_USD.

    Pass 5 — Price refresh for all current holdings; history snapshot.
    """
    today     = date.today()
    today_str = today.isoformat()
    stock_map = {r["ticker"]: r for r in records}
    holdings  = portfolio.get("holdings", {})
    cash      = portfolio.get("cash", PORTFOLIO_START)
    history   = portfolio.get("history", [])
    trades    = portfolio.get("trades", [])

    # ── helper: current price for a holding ───────────────────────────────
    def cur_price(ticker, pos):
        st = stock_map.get(ticker)
        if st and st.get("price_raw") and st["price_raw"] > 0:
            return float(st["price_raw"])
        return float(pos.get("last_price") or pos.get("cost_basis") or 1)

    # ── Pass 1: forced sells (grade/universe) ─────────────────────────────
    to_sell = [
        t for t, pos in holdings.items()
        if t not in stock_map
        or (stock_map[t].get("overall") or 0) < SELL_THRESHOLD
    ]
    for ticker in to_sell:
        pos      = holdings.pop(ticker)
        price    = cur_price(ticker, pos)
        proceeds = pos["shares"] * price
        cash    += proceeds
        gain_pct = (round((price - pos["cost_basis"]) / pos["cost_basis"] * 100, 2)
                    if pos.get("cost_basis") else 0)
        trades.append({
            "date": today_str, "action": "SELL", "ticker": ticker,
            "shares": pos["shares"], "price": round(price, 2),
            "proceeds": round(proceeds, 2), "gain_pct": gain_pct,
        })
        print(f"    SELL {ticker}: gain={gain_pct:+.1f}%  (grade dropped)")

    # ── Pass 2: compute target weights ────────────────────────────────────
    # Eligible = currently held (above threshold) + new candidates above threshold
    # We compute weights across ALL of them so trims and buys are self-consistent.
    eligible = [
        r for r in records
        if (r.get("overall") or 0) >= BUY_THRESHOLD
        and r.get("price_raw") and r["price_raw"] > 0
    ]
    targets = _target_weights(eligible)   # {ticker: fraction}

    # Current portfolio value (before any rebalancing)
    holdings_mv = sum(pos["shares"] * cur_price(t, pos) for t, pos in holdings.items())
    total_value = holdings_mv + cash

    # ── Pass 3: trims ─────────────────────────────────────────────────────
    # Process heaviest over-weights first so cash freed can fund new buys.
    overweight_order = sorted(
        [(t, pos) for t, pos in holdings.items() if t in targets],
        key=lambda x: -(x[1]["shares"] * cur_price(x[0], x[1])) / max(total_value, 1)
    )
    for ticker, pos in overweight_order:
        if total_value <= 0:
            break
        price       = cur_price(ticker, pos)
        mv          = pos["shares"] * price
        current_pct = mv / total_value
        target_pct  = targets[ticker]
        drift       = current_pct - target_pct       # positive = overweight

        if drift <= 0:
            continue

        trim_usd = drift * total_value               # $ amount to trim
        if trim_usd < MIN_TRADE_USD:
            continue                                  # not worth trading

        st_gain = _is_short_term_gain(pos, price, today)

        if st_gain:
            # Only trim if drift exceeds the tax hurdle
            if drift <= OVERWEIGHT_THRESH + TAX_HURDLE_DRIFT:
                print(f"    HOLD {ticker}: overweight {drift*100:.1f}pp "
                      f"but ST gain — below tax hurdle "
                      f"(need >{(OVERWEIGHT_THRESH+TAX_HURDLE_DRIFT)*100:.0f}pp)")
                continue
        else:
            # Long-term or unrealised loss: only trim if materially overweight
            if drift <= OVERWEIGHT_THRESH:
                continue

        cash = _trim_shares(ticker, pos, price, trim_usd, today_str, cash, trades)
        # Remove position if shares trimmed to near zero
        if pos["shares"] < 0.0001:
            holdings.pop(ticker)
        # Recalculate total_value after trim
        holdings_mv = sum(p["shares"] * cur_price(t, p) for t, p in holdings.items())
        total_value = holdings_mv + cash

    # ── Pass 4a: new buys ─────────────────────────────────────────────────
    new_tickers = [t for t in targets if t not in holdings]
    for ticker in sorted(new_tickers, key=lambda t: -targets[t]):
        target_usd  = targets[ticker] * total_value
        price       = float(stock_map[ticker]["price_raw"])
        affordable  = min(target_usd, cash * 0.98)
        if affordable < max(price, MIN_TRADE_USD):
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
            "date": today_str, "action": "BUY", "ticker": ticker,
            "shares": round(shares, 6), "price": round(price, 2),
            "cost":   round(cost, 2),
        })
        print(f"    BUY  {ticker}: {shares:.4f} sh @ ${price:.2f}"
              f"  (target {targets[ticker]*100:.1f}%,  cost ${cost:,.0f})")
        holdings_mv = sum(p["shares"] * cur_price(t, p) for t, p in holdings.items())
        total_value = holdings_mv + cash

    # ── Pass 4b: top-up existing under-weights ────────────────────────────
    for ticker, pos in sorted(holdings.items(),
                               key=lambda x: targets.get(x[0], 0) -
                               (x[1]["shares"] * cur_price(x[0], x[1])) / max(total_value, 1)):
        if ticker not in targets:
            continue
        price       = cur_price(ticker, pos)
        mv          = pos["shares"] * price
        current_pct = mv / max(total_value, 1)
        target_pct  = targets[ticker]
        shortfall   = target_pct - current_pct      # positive = underweight

        if shortfall < DRIFT_THRESHOLD:
            continue

        topup_usd = shortfall * total_value
        if topup_usd < MIN_TRADE_USD or topup_usd > cash * 0.98:
            continue

        shares_add = topup_usd / price
        cost       = shares_add * price
        cash      -= cost
        pos["shares"]     = round(pos["shares"] + shares_add, 6)
        pos["last_price"] = round(price, 4)
        trades.append({
            "date": today_str, "action": "BUY", "ticker": ticker,
            "shares": round(shares_add, 6), "price": round(price, 2),
            "cost":   round(cost, 2),
        })
        print(f"    TOP  {ticker}: +{shares_add:.4f} sh @ ${price:.2f}"
              f"  (under {shortfall*100:.1f}pp,  cost ${cost:,.0f})")
        holdings_mv = sum(p["shares"] * cur_price(t, p) for t, p in holdings.items())
        total_value = holdings_mv + cash

    # ── Pass 5: refresh prices + history snapshot ─────────────────────────
    holdings_mv = 0
    for ticker, pos in holdings.items():
        st = stock_map.get(ticker)
        if st and st.get("price_raw"):
            pos["last_price"] = round(float(st["price_raw"]), 4)
        holdings_mv += pos["shares"] * pos["last_price"]

    total_value = holdings_mv + cash
    if not history or history[-1]["date"] != today_str:
        history.append({"date": today_str, "value": round(total_value, 2),
                        "cash": round(cash, 2)})
    else:
        history[-1]["value"] = round(total_value, 2)

    portfolio.update({
        "holdings":    holdings,
        "cash":        round(cash, 2),
        "total_value": round(total_value, 2),
        "history":     history,
        "trades":      trades,
        "updated_at":  today_str,
    })
    return portfolio

def _init_portfolio(records):
    """Create a brand-new portfolio and make initial buys from current records."""
    today_str = date.today().isoformat()
    print(f"  Initialising new portfolio on {today_str} with ${PORTFOLIO_START:,.0f}")
    portfolio = {
        "start_date":  today_str,
        "start_value": PORTFOLIO_START,
        "cash":        PORTFOLIO_START,
        "holdings":    {},
        "history":     [],
        "spy_history": _get_spy_history(today_str),
        "trades":      [],
        "updated_at":  today_str,
    }
    return _update_portfolio(records, portfolio)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    raw_path = Path(RAW_FILE)
    if not raw_path.exists():
        print(f"ERROR: {RAW_FILE} not found. Run scraper.py first.")
        return

    print(f"Reading {RAW_FILE}...")
    raw_data = json.loads(raw_path.read_text())
    raws     = raw_data.get("stocks", [])
    print(f"  {len(raws)} stocks loaded")

    # Score + format every record
    records = []
    for raw in raws:
        try:
            scored    = score_record(raw)
            formatted = format_record(scored)
            records.append(formatted)
        except Exception as e:
            print(f"  ERROR grading {raw.get('ticker','?')}: {e}")

    records.sort(key=lambda x: (-(x["overall"] or -99), x["ticker"]))

    out = {
        "generated_at": raw_data.get("generated_at", "unknown"),
        "graded_at":    date.today().isoformat(),
        "total":        len(records),
        "stocks":       records,
    }
    Path(OUTPUT_FILE).write_text(json.dumps(out, indent=2, default=str))
    print(f"Written {OUTPUT_FILE}  ({len(records)} stocks)")

    # Grade distribution summary
    from collections import Counter
    dist = Counter(r["grade"] for r in records)
    print("  Grade distribution: " +
          "  ".join(f"{g}:{dist.get(g,0)}" for g in ["A","B","C","D","F","-"]))

    # Re-run portfolio with updated grades
    print("\n── Portfolio update ──────────────────────────────────────────────")
    portfolio = load_portfolio()
    if portfolio is None or RESET_PORTFOLIO:
        if RESET_PORTFOLIO and portfolio is not None:
            print("  Resetting portfolio (RESET_PORTFOLIO=True)")
        portfolio = _init_portfolio(records)
    else:
        portfolio = _refresh_spy(portfolio)
        portfolio = _update_portfolio(records, portfolio)
    save_portfolio(portfolio)
    print(f"  Portfolio: ${portfolio['total_value']:,.0f} | "
          f"{len(portfolio.get('holdings', {}))} holdings | "
          f"${portfolio['cash']:,.0f} cash")


if __name__ == "__main__":
    main()
