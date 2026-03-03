"""
scraper.py  —  Stock Tracker v2
Fetches fundamentals for all US-listed companies with market cap >$20B
via yfinance, scores each metric, assigns an A–F grade, and writes data.json.

Run:  python scraper.py
Output: data.json  (read by generate_html.py)
"""

import json
import math
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf
import pandas as pd

# ─── Config ───────────────────────────────────────────────────────────────────
MIN_MARKET_CAP_B = 20          # $20B minimum
OUTPUT_FILE      = "data.json"
DELAY_BETWEEN    = 1.0         # seconds between tickers (be polite to Yahoo)
MAX_RETRIES      = 3

# ─── Ticker universe ──────────────────────────────────────────────────────────
#
# Static list of S&P 500 constituents (as of early 2025).
# Wikipedia blocks requests from GitHub Actions (403), so we embed the list
# directly. The scraper then filters to >$20B market cap at fetch time.
# Update this list periodically as the index composition changes.

SP500_TICKERS = [
    "A","AAPL","ABBV","ABNB","ABT","ACGL","ACN","ADBE","ADI","ADM","ADP","ADSK",
    "AEE","AEP","AES","AFL","AIG","AIZ","AJG","AKAM","ALB","ALGN","ALL","ALLE",
    "AMAT","AMCR","AMD","AME","AMGN","AMP","AMT","AMZN","ANET","ANSS","AON","AOS",
    "APA","APD","APH","APTV","ARE","ATO","AVB","AVGO","AVY","AWK","AXON","AXP",
    "AZO","BA","BAC","BALL","BAX","BBWI","BBY","BDX","BEN","BF-B","BG","BIIB",
    "BK","BKNG","BKR","BLK","BMY","BR","BRK-B","BRO","BSX","BWA","BX",
    "C","CAG","CAH","CARR","CAT","CB","CBOE","CBRE","CCI","CCL","CDNS","CDW",
    "CE","CEG","CF","CFG","CHD","CHRW","CHTR","CI","CINF","CL","CLX","CMA",
    "CMCSA","CME","CMG","CMI","CMS","CNC","CNP","COF","COO","COP","COR","COST",
    "CPAY","CPB","CPRT","CPT","CRL","CRM","CSCO","CSGP","CSX","CTAS","CTLT",
    "CTRA","CTSH","CTVA","CVS","CVX","CZR",
    "D","DAL","DAY","DD","DE","DECK","DFS","DG","DGX","DHI","DHR","DIS","DLR",
    "DLTR","DOC","DOV","DOW","DPZ","DRI","DTE","DUK","DVA","DVN","DXCM",
    "EA","EBAY","ECL","ED","EFX","EG","EIX","EL","ELV","EMN","EMR","ENPH",
    "EOG","EPAM","EQIX","EQR","EQT","ES","ESS","ETN","ETR","EVRG","EW","EXC",
    "EXPD","EXPE","EXR",
    "F","FANG","FAST","FCX","FDS","FDX","FE","FFIV","FI","FICO","FIS","FITB",
    "FLT","FMC","FOX","FOXA","FRT","FSLR","FTNT","FTV",
    "GD","GDDY","GE","GEHC","GEN","GEV","GILD","GIS","GL","GLW","GM","GNRC",
    "GOOGL","GPC","GPN","GPS","GS","GWW",
    "HAL","HAS","HBAN","HCA","HD","HES","HIG","HII","HLT","HOLX","HON","HPE",
    "HPQ","HRL","HSIC","HST","HSY","HUBB","HUM","HWM",
    "IBM","ICE","IDXX","IEX","IFF","ILMN","INCY","INTC","INTU","INVH","IP",
    "IPG","IQV","IR","IRM","ISRG","IT","ITW","IVZ",
    "J","JBHT","JBL","JCI","JKHY","JNJ","JNPR","JPM",
    "K","KDP","KEY","KEYS","KHC","KIM","KLAC","KMB","KMI","KMX","KO","KR",
    "L","LDOS","LEN","LH","LHX","LIN","LKQ","LLY","LMT","LNT","LOW","LRCX",
    "LULU","LUV","LVS","LW","LYB","LYV",
    "MA","MAA","MAR","MAS","MCD","MCHP","MCK","MCO","MDLZ","MDT","MET","META",
    "MGM","MHK","MKC","MKTX","MLM","MMC","MMM","MNST","MO","MOH","MOS","MPC",
    "MPWR","MRK","MRNA","MRO","MS","MSCI","MSFT","MSI","MTB","MTD","MU",
    "NCLH","NDAQ","NEE","NEM","NFLX","NI","NKE","NOC","NOW","NRG","NSC","NTAP",
    "NTRS","NUE","NVDA","NVR","NWS","NWSA",
    "ODFL","OKE","OMC","ON","ORCL","ORLY","OXY",
    "PANW","PARA","PAYC","PAYX","PCAR","PCG","PEG","PEP","PFE","PFG","PG",
    "PGR","PH","PHM","PKG","PLD","PM","PNC","PNR","PNW","PODD","POOL","PPG",
    "PPL","PRU","PSA","PSX","PTC","PWR","PYPL",
    "QCOM","QRVO",
    "RCL","REG","REGN","RF","RJF","RL","RMD","ROK","ROL","ROP","ROST","RSG",
    "RTX",
    "SBAC","SBUX","SCHW","SHW","SJM","SLB","SMCI","SNA","SNPS","SO","SPG",
    "SPGI","SRE","STE","STLD","STT","STX","STZ","SWK","SWKS","SYF","SYK","SYY",
    "T","TAP","TDG","TDY","TECH","TEL","TER","TFC","TFX","TGT","TJX","TMO",
    "TMUS","TPR","TRGP","TRMB","TROW","TRV","TSCO","TSLA","TSN","TT","TTWO",
    "TXN","TXT","TYL",
    "UAL","UDR","UHS","ULTA","UNH","UNP","UPS","URI","USB",
    "V","VFC","VICI","VLO","VLTO","VMC","VRSK","VRSN","VRTX","VTR","VTRS","VZ",
    "WAB","WAT","WBA","WBD","WDC","WEC","WELL","WFC","WM","WMB","WMT","WRB",
    "WRK","WST","WTW","WY","WYNN",
    "XEL","XOM","XYL",
    "YUM",
    "ZBH","ZBRA","ZTS",
]

# Additional large-cap tickers not in S&P 500 but commonly >$20B
EXTRA_TICKERS = [
    "ABNB","ARM","AXON","COIN","CRWD","DDOG","DASH","DUOL","EXAS","HOOD",
    "MELI","NTNX","OKTA","PANW","PATH","PLTR","RBLX","RIVN","SHOP","SMCI",
    "SNOW","SOFI","SPOT","SQ","TTD","UBER","VEEV","ZM","ZS",
]

def get_ticker_universe():
    """
    Return the combined S&P 500 + extra large-cap ticker list.
    Uses a static embedded list to avoid external HTTP dependencies in CI.
    The scraper filters to >$20B market cap at fetch time.
    """
    combined = sorted(set(SP500_TICKERS + EXTRA_TICKERS))
    print(f"Ticker universe: {len(combined)} tickers (S&P 500 + extras)")
    print(f"  Will filter to >${MIN_MARKET_CAP_B}B market cap during fetch")
    return combined


# ─── Safe helpers ─────────────────────────────────────────────────────────────

def safe(val, default=None):
    """Return val if it's a real number, else default."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def safe_pct(val, default=None):
    """Convert a decimal ratio (0.25) to a percentage (25.0)."""
    v = safe(val)
    if v is None:
        return default
    return round(v * 100, 2)


def calc_growth(new_val, old_val):
    """YoY growth % given two values. Returns None if inputs are invalid."""
    n = safe(new_val)
    o = safe(old_val)
    if n is None or o is None or o == 0:
        return None
    return round((n - o) / abs(o) * 100, 2)


# ─── Per-ticker fetch ─────────────────────────────────────────────────────────

def fetch_ticker_data(symbol):
    """
    Fetch all metrics for a single ticker via yfinance.
    Returns a dict of raw values (pre-scoring), or None if fetch fails
    or market cap is below threshold.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tk = yf.Ticker(symbol)
            info = tk.info or {}

            # ── Gate on market cap ────────────────────────────────────────
            market_cap = safe(info.get("marketCap"))
            if market_cap is None or market_cap < MIN_MARKET_CAP_B * 1e9:
                return None  # Skip — below threshold or no data

            # ── Identity ──────────────────────────────────────────────────
            name     = info.get("longName") or info.get("shortName") or symbol
            sector   = info.get("sector")   or "Unknown"
            industry = info.get("industry") or "Unknown"
            currency = info.get("currency") or "USD"

            # ── Price ─────────────────────────────────────────────────────
            price          = safe(info.get("currentPrice") or info.get("regularMarketPrice"))
            target_price   = safe(info.get("targetMeanPrice"))
            analyst_upside = None
            if price and target_price and price > 0:
                analyst_upside = round((target_price - price) / price * 100, 2)

            # Analyst recommendation: yfinance gives 1.0 (Strong Buy) – 5.0 (Sell)
            analyst_rec = safe(info.get("recommendationMean"))

            # 52-week performance
            price_52w_low  = safe(info.get("fiftyTwoWeekLow"))
            price_52w_high = safe(info.get("fiftyTwoWeekHigh"))
            perf_52w = None
            if price and price_52w_low and price_52w_low > 0:
                # Use 52w low as proxy for ~1yr ago price if history unavailable
                # Better: use actual 1yr ago price from history
                try:
                    hist = tk.history(period="1y", auto_adjust=True)
                    if not hist.empty:
                        price_1y_ago = float(hist["Close"].iloc[0])
                        if price_1y_ago > 0:
                            perf_52w = round((price - price_1y_ago) / price_1y_ago * 100, 2)
                except Exception:
                    pass

            # ── Valuation ─────────────────────────────────────────────────
            forward_pe  = safe(info.get("forwardPE"))
            trailing_pe = safe(info.get("trailingPE"))
            peg_ratio   = safe(info.get("pegRatio"))
            ev_ebitda   = safe(info.get("enterpriseToEbitda"))
            price_sales = safe(info.get("priceToSalesTrailing12Months"))
            price_book  = safe(info.get("priceToBook"))
            ev          = safe(info.get("enterpriseValue"))

            # ── Profitability ─────────────────────────────────────────────
            gross_margin   = safe_pct(info.get("grossMargins"))
            operating_margin = safe_pct(info.get("operatingMargins"))
            profit_margin  = safe_pct(info.get("profitMargins"))
            roe            = safe_pct(info.get("returnOnEquity"))
            roa            = safe_pct(info.get("returnOnAssets"))
            debt_equity    = safe(info.get("debtToEquity"))
            # yfinance returns D/E as a raw ratio (e.g. 150 means 1.5x), normalize
            if debt_equity is not None:
                debt_equity = round(debt_equity / 100, 3)

            # ── Growth (TTM) ──────────────────────────────────────────────
            # Revenue growth TTM: yfinance provides revenueGrowth (YoY quarterly)
            # and earningsGrowth. These are decimal ratios.
            rev_growth_ttm = safe_pct(info.get("revenueGrowth"))   # quarterly YoY
            eps_growth_ttm = safe_pct(info.get("earningsGrowth"))  # quarterly YoY

            # For true TTM-over-TTM, pull annual financials
            rev_growth_yoy_ttm = None
            eps_growth_yoy_ttm = None
            rev_growth_qoq_accel = None  # current Q YoY vs prior Q YoY (acceleration)
            eps_growth_qoq_accel = None

            try:
                # Quarterly financials give us the last 4 quarters
                q_income = tk.quarterly_income_stmt
                if q_income is not None and not q_income.empty:
                    cols = q_income.columns  # newest first

                    # TTM revenue = sum of 4 most recent quarters
                    def ttm_sum(row_name, df):
                        if row_name in df.index and len(df.columns) >= 4:
                            vals = df.loc[row_name].iloc[:4]
                            if vals.notna().sum() >= 3:
                                return float(vals.sum(skipna=True))
                        return None

                    ttm_rev  = ttm_sum("Total Revenue", q_income)
                    prev_rev = None
                    if len(cols) >= 8:
                        prev_vals = q_income["Total Revenue"].iloc[4:8] if "Total Revenue" in q_income.index else None
                        if prev_vals is not None and prev_vals.notna().sum() >= 3:
                            prev_rev = float(prev_vals.sum(skipna=True))

                    if ttm_rev and prev_rev:
                        rev_growth_yoy_ttm = calc_growth(ttm_rev, prev_rev)

                    # Quarterly acceleration: compare most recent Q YoY to prior Q YoY
                    if "Total Revenue" in q_income.index and len(cols) >= 5:
                        r = q_income.loc["Total Revenue"]
                        q0 = safe(r.iloc[0])   # most recent quarter
                        q1 = safe(r.iloc[1])   # one quarter prior
                        q4 = safe(r.iloc[4])   # same quarter last year (for q0)
                        q5 = safe(r.iloc[5]) if len(cols) >= 6 else None  # same Q-1 last year
                        if q0 and q4:
                            cur_q_yoy = calc_growth(q0, q4)
                            if q1 and q5:
                                prior_q_yoy = calc_growth(q1, q5)
                                if cur_q_yoy is not None and prior_q_yoy is not None:
                                    rev_growth_qoq_accel = round(cur_q_yoy - prior_q_yoy, 2)

                    # EPS acceleration
                    eps_row = None
                    for candidate in ["Diluted EPS", "Basic EPS", "EPS"]:
                        if candidate in q_income.index:
                            eps_row = candidate
                            break
                    if eps_row and len(cols) >= 5:
                        e = q_income.loc[eps_row]
                        e0 = safe(e.iloc[0])
                        e1 = safe(e.iloc[1])
                        e4 = safe(e.iloc[4])
                        e5 = safe(e.iloc[5]) if len(cols) >= 6 else None
                        if e0 and e4:
                            cur_eps_yoy = calc_growth(e0, e4)
                            if e1 and e5:
                                prior_eps_yoy = calc_growth(e1, e5)
                                if cur_eps_yoy is not None and prior_eps_yoy is not None:
                                    eps_growth_qoq_accel = round(cur_eps_yoy - prior_eps_yoy, 2)

                    # TTM EPS growth
                    ttm_eps  = ttm_sum("Diluted EPS", q_income) or ttm_sum("Basic EPS", q_income)
                    prev_eps = None
                    if len(cols) >= 8:
                        for cand in ["Diluted EPS", "Basic EPS"]:
                            if cand in q_income.index:
                                pv = q_income.loc[cand].iloc[4:8]
                                if pv.notna().sum() >= 3:
                                    prev_eps = float(pv.sum(skipna=True))
                                    break
                    if ttm_eps and prev_eps:
                        eps_growth_yoy_ttm = calc_growth(ttm_eps, prev_eps)

            except Exception:
                pass  # Fall back to info-level growth figures

            # Use info-level as fallback if quarterly calc failed
            if rev_growth_yoy_ttm is None:
                rev_growth_yoy_ttm = rev_growth_ttm
            if eps_growth_yoy_ttm is None:
                eps_growth_yoy_ttm = eps_growth_ttm

            # ── Earnings surprise ─────────────────────────────────────────
            earnings_surprise_pct = None
            try:
                cal = tk.earnings_dates
                if cal is not None and not cal.empty:
                    # Find most recent past earnings with actual EPS data
                    past = cal.dropna(subset=["EPS Actual", "EPS Estimate"])
                    if not past.empty:
                        latest = past.iloc[0]
                        actual   = safe(latest.get("EPS Actual"))
                        estimate = safe(latest.get("EPS Estimate"))
                        if actual is not None and estimate is not None and estimate != 0:
                            earnings_surprise_pct = round((actual - estimate) / abs(estimate) * 100, 2)
            except Exception:
                pass

            # ── Next earnings date ────────────────────────────────────────
            next_earnings = None
            try:
                cal = tk.earnings_dates
                if cal is not None and not cal.empty:
                    now = pd.Timestamp.now(tz="UTC")
                    future = cal[cal.index > now]
                    if not future.empty:
                        next_earnings = future.index[-1].strftime("%b %d, %Y")
            except Exception:
                pass

            # ── Shares & float ────────────────────────────────────────────
            shares_outstanding = safe(info.get("sharesOutstanding"))
            float_pct = None
            shares_float = safe(info.get("floatShares"))
            if shares_outstanding and shares_float and shares_outstanding > 0:
                float_pct = round(shares_float / shares_outstanding * 100, 1)

            # ── Build raw record ──────────────────────────────────────────
            return {
                # Identity
                "ticker":         symbol,
                "name":           name,
                "sector":         sector,
                "industry":       industry,
                "currency":       currency,
                # Price / target
                "price":          price,
                "target_price":   target_price,
                "analyst_upside": analyst_upside,
                "analyst_rec":    analyst_rec,
                "perf_52w":       perf_52w,
                # Market cap (in billions, rounded)
                "market_cap_b":   round(market_cap / 1e9, 2) if market_cap else None,
                "market_cap_raw": market_cap,
                # Valuation
                "forward_pe":     forward_pe,
                "trailing_pe":    trailing_pe,
                "peg_ratio":      peg_ratio,
                "ev_ebitda":      ev_ebitda,
                "price_sales":    price_sales,
                "price_book":     price_book,
                # Growth
                "rev_growth_ttm":      rev_growth_yoy_ttm,
                "eps_growth_ttm":      eps_growth_yoy_ttm,
                "rev_accel":           rev_growth_qoq_accel,  # positive = accelerating
                "eps_accel":           eps_growth_qoq_accel,
                "earnings_surprise":   earnings_surprise_pct,
                # Profitability
                "gross_margin":    gross_margin,
                "operating_margin": operating_margin,
                "profit_margin":   profit_margin,
                "roe":             roe,
                "roa":             roa,
                "debt_equity":     debt_equity,
                # Misc
                "next_earnings":   next_earnings,
                "float_pct":       float_pct,
            }

        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"    Attempt {attempt} failed for {symbol}: {e}. Retrying...")
                time.sleep(2 ** attempt)
            else:
                print(f"    ERROR fetching {symbol}: {e}")
                return None


# ─── Scoring ──────────────────────────────────────────────────────────────────
#
# Each metric scores 0–4.  Weights are applied per category, then
# category weights are applied to get a final 0–4 score → letter grade.
#
# Sector adjustments: financials and utilities are excluded from D/E scoring
# (high structural leverage); REITs use P/FFO not P/E so we skip forward_pe.

FINANCIALS_SECTORS = {"Financial Services", "Financials"}
UTILITIES_SECTORS  = {"Utilities"}
REIT_INDUSTRIES    = {"REIT", "Real Estate Investment Trust"}

def score_metric(value, thresholds, reverse=False):
    """
    thresholds: list of 4 breakpoints [poor_cutoff, weak, fair, good]
                value >= thresholds[3] → 4
                value >= thresholds[2] → 3
                etc.
    reverse=True: lower is better (e.g. P/E, debt)
    Returns 0–4 (int) or None if value is None.
    """
    if value is None:
        return None
    if reverse:
        # Flip: high values → low scores
        if value <= thresholds[0]:   return 4
        elif value <= thresholds[1]: return 3
        elif value <= thresholds[2]: return 2
        elif value <= thresholds[3]: return 1
        else:                        return 0
    else:
        if value >= thresholds[3]:   return 4
        elif value >= thresholds[2]: return 3
        elif value >= thresholds[1]: return 2
        elif value >= thresholds[0]: return 1
        else:                        return 0


def score_acceleration(val):
    """Score revenue/EPS acceleration (percentage point change in YoY growth)."""
    if val is None:
        return None
    if val >= 5:    return 4
    if val >= 1:    return 3
    if val >= -1:   return 2  # roughly stable
    if val >= -5:   return 1
    return 0


def score_analyst_rec(val):
    """
    yfinance recommendationMean: 1=Strong Buy, 2=Buy, 3=Hold, 4=Sell, 5=Strong Sell
    Invert to 0–4 score.
    """
    if val is None:
        return None
    if val <= 1.5:  return 4
    if val <= 2.2:  return 3
    if val <= 2.8:  return 2
    if val <= 3.5:  return 1
    return 0


def score_record(raw):
    """
    Compute per-metric scores and a weighted overall grade for one stock.
    Returns the raw dict augmented with scores, weighted score, and grade.
    """
    sector   = raw.get("sector", "")
    industry = raw.get("industry", "")
    is_fin   = sector in FINANCIALS_SECTORS
    is_util  = sector in UTILITIES_SECTORS
    is_reit  = any(r in industry for r in REIT_INDUSTRIES)

    s = {}  # scores dict

    # ── Growth (weight 35%) ────────────────────────────────────────────────
    s["rev_growth_ttm"] = score_metric(
        raw["rev_growth_ttm"], [0, 5, 10, 20])
    s["eps_growth_ttm"] = score_metric(
        raw["eps_growth_ttm"], [0, 5, 15, 25])
    s["rev_accel"] = score_acceleration(raw["rev_accel"])
    s["eps_accel"] = score_acceleration(raw["eps_accel"])
    s["earnings_surprise"] = score_metric(
        raw["earnings_surprise"], [-5, 0, 2, 5])

    growth_scores = [s[k] for k in
        ["rev_growth_ttm", "eps_growth_ttm", "rev_accel", "eps_accel", "earnings_surprise"]
        if s[k] is not None]
    growth_avg = (sum(growth_scores) / len(growth_scores)) if growth_scores else None

    # ── Valuation (weight 25%) ────────────────────────────────────────────
    # Skip forward P/E for REITs; skip D/E for financials/utilities
    if not is_reit:
        s["forward_pe"] = score_metric(
            raw["forward_pe"], [15, 20, 30, 40], reverse=True)
    else:
        s["forward_pe"] = None

    s["peg_ratio"] = score_metric(
        raw["peg_ratio"], [1, 1.5, 2.5, 3.5], reverse=True)
    s["ev_ebitda"] = score_metric(
        raw["ev_ebitda"], [10, 15, 25, 35], reverse=True)
    s["price_sales"] = score_metric(
        raw["price_sales"], [3, 6, 10, 15], reverse=True)

    val_scores = [s[k] for k in
        ["forward_pe", "peg_ratio", "ev_ebitda", "price_sales"]
        if s[k] is not None]
    val_avg = (sum(val_scores) / len(val_scores)) if val_scores else None

    # ── Profitability (weight 25%) ─────────────────────────────────────────
    s["gross_margin"]     = score_metric(raw["gross_margin"],     [10, 25, 40, 60])
    s["operating_margin"] = score_metric(raw["operating_margin"], [0, 8, 15, 25])
    s["roe"]              = score_metric(raw["roe"],              [0, 8, 15, 25])
    s["roa"]              = score_metric(raw["roa"],              [0, 3, 7, 12])

    if not is_fin and not is_util:
        s["debt_equity"] = score_metric(
            raw["debt_equity"], [0.3, 0.8, 1.5, 3.0], reverse=True)
    else:
        s["debt_equity"] = None  # not meaningful for banks/utilities

    prof_scores = [s[k] for k in
        ["gross_margin", "operating_margin", "roe", "roa", "debt_equity"]
        if s[k] is not None]
    prof_avg = (sum(prof_scores) / len(prof_scores)) if prof_scores else None

    # ── Momentum & Sentiment (weight 15%) ─────────────────────────────────
    s["perf_52w"]      = score_metric(raw["perf_52w"],      [-15, 0, 15, 30])
    s["analyst_upside"]= score_metric(raw["analyst_upside"], [0, 5, 15, 30])
    s["analyst_rec"]   = score_analyst_rec(raw["analyst_rec"])

    mom_scores = [s[k] for k in
        ["perf_52w", "analyst_upside", "analyst_rec"]
        if s[k] is not None]
    mom_avg = (sum(mom_scores) / len(mom_scores)) if mom_scores else None

    # ── Weighted overall ───────────────────────────────────────────────────
    weighted_sum   = 0
    weighted_total = 0
    for avg, weight in [
        (growth_avg, 0.35),
        (val_avg,    0.25),
        (prof_avg,   0.25),
        (mom_avg,    0.15),
    ]:
        if avg is not None:
            weighted_sum   += avg * weight
            weighted_total += weight

    overall = round(weighted_sum / weighted_total, 3) if weighted_total > 0 else None

    # ── Letter grade ───────────────────────────────────────────────────────
    grade = "-"
    grade_color = "neutral"
    if overall is not None:
        if overall >= 3.3:
            grade, grade_color = "A", "grade-a"
        elif overall >= 2.6:
            grade, grade_color = "B", "grade-b"
        elif overall >= 1.9:
            grade, grade_color = "C", "grade-c"
        elif overall >= 1.2:
            grade, grade_color = "D", "grade-d"
        else:
            grade, grade_color = "F", "grade-f"

    return {
        **raw,
        "scores":       s,
        "growth_avg":   round(growth_avg, 2) if growth_avg is not None else None,
        "val_avg":      round(val_avg,    2) if val_avg    is not None else None,
        "prof_avg":     round(prof_avg,   2) if prof_avg   is not None else None,
        "mom_avg":      round(mom_avg,    2) if mom_avg    is not None else None,
        "overall":      overall,
        "grade":        grade,
        "grade_color":  grade_color,
    }


# ─── Format helpers ───────────────────────────────────────────────────────────

def fmt_pct(val, decimals=1):
    if val is None:
        return None
    return f"{val:+.{decimals}f}%"

def fmt_num(val, decimals=1):
    if val is None:
        return None
    return f"{val:.{decimals}f}x"

def fmt_cap(val_b):
    if val_b is None:
        return None
    if val_b >= 1000:
        return f"${val_b/1000:.2f}T"
    return f"${val_b:.1f}B"

def fmt_price(val):
    if val is None:
        return None
    return f"${val:,.2f}"


def format_record(rec):
    """Convert raw numeric values into display strings for the frontend."""
    r = rec
    return {
        # Identity
        "ticker":           r["ticker"],
        "name":             r["name"],
        "sector":           r["sector"],
        "industry":         r["industry"],
        # Grade
        "grade":            r["grade"],
        "grade_color":      r["grade_color"],
        "overall":          r["overall"],
        "growth_avg":       r["growth_avg"],
        "val_avg":          r["val_avg"],
        "prof_avg":         r["prof_avg"],
        "mom_avg":          r["mom_avg"],
        # Display values
        "market_cap":       fmt_cap(r["market_cap_b"]),
        "price":            fmt_price(r["price"]),
        "target_price":     fmt_price(r["target_price"]),
        "analyst_upside":   fmt_pct(r["analyst_upside"]),
        "analyst_rec_raw":  r["analyst_rec"],
        "perf_52w":         fmt_pct(r["perf_52w"]),
        "forward_pe":       fmt_num(r["forward_pe"]) if r["forward_pe"] else None,
        "peg_ratio":        fmt_num(r["peg_ratio"])  if r["peg_ratio"]  else None,
        "ev_ebitda":        fmt_num(r["ev_ebitda"])  if r["ev_ebitda"]  else None,
        "price_sales":      fmt_num(r["price_sales"]) if r["price_sales"] else None,
        "rev_growth_ttm":   fmt_pct(r["rev_growth_ttm"]),
        "eps_growth_ttm":   fmt_pct(r["eps_growth_ttm"]),
        "rev_accel":        fmt_pct(r["rev_accel"])  if r["rev_accel"] is not None else None,
        "eps_accel":        fmt_pct(r["eps_accel"])  if r["eps_accel"] is not None else None,
        "earnings_surprise":fmt_pct(r["earnings_surprise"]),
        "gross_margin":     fmt_pct(r["gross_margin"], 1),
        "operating_margin": fmt_pct(r["operating_margin"], 1),
        "profit_margin":    fmt_pct(r["profit_margin"], 1),
        "roe":              fmt_pct(r["roe"], 1),
        "roa":              fmt_pct(r["roa"], 1),
        "debt_equity":      fmt_num(r["debt_equity"], 2) if r["debt_equity"] is not None else None,
        "next_earnings":    r["next_earnings"],
        # Raw scores (for tooltip/detail)
        "scores":           r["scores"],
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    start_time = datetime.now(timezone.utc)
    print(f"=== Stock Tracker v2 | {start_time.strftime('%Y-%m-%d %H:%M UTC')} ===\n")

    tickers = get_ticker_universe()
    print(f"\nProcessing {len(tickers)} tickers (dropping those <${MIN_MARKET_CAP_B}B)...\n")

    records  = []
    skipped  = 0
    errors   = 0

    for i, symbol in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {symbol:<8}", end=" ", flush=True)
        try:
            raw = fetch_ticker_data(symbol)
            if raw is None:
                print("skip (below cap or no data)")
                skipped += 1
            else:
                scored    = score_record(raw)
                formatted = format_record(scored)
                records.append(formatted)
                cap = raw.get("market_cap_b") or 0
                print(f"✓  {raw['name'][:35]:<35} {fmt_cap(cap):>8}  grade={scored['grade']}")
        except Exception as e:
            print(f"ERROR: {e}")
            traceback.print_exc()
            errors += 1

        time.sleep(DELAY_BETWEEN)

    # Sort by overall score descending, then ticker ascending
    records.sort(key=lambda x: (-(x["overall"] or -99), x["ticker"]))

    end_time = datetime.now(timezone.utc)
    output = {
        "generated_at": end_time.strftime("%Y-%m-%d %H:%M UTC"),
        "total":        len(records),
        "min_cap_b":    MIN_MARKET_CAP_B,
        "stocks":       records,
    }

    Path(OUTPUT_FILE).write_text(json.dumps(output, indent=2, default=str))
    print(f"\n=== Done ===")
    print(f"  Kept:    {len(records)}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    print(f"  Runtime: {(end_time - start_time).seconds // 60}m {(end_time - start_time).seconds % 60}s")
    print(f"  Output:  {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
