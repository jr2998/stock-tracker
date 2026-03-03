"""
scraper.py  —  Stock Tracker v3
Fetches fundamentals for all tickers in the universe via yfinance,
scores each metric, assigns an A–F grade, writes data.json.
Also manages portfolio.json (simulated portfolio based on grades).

Run:  python scraper.py
Output: data.json, portfolio.json
"""

import json
import math
import time
import traceback
from datetime import datetime, timezone, date
from pathlib import Path

import yfinance as yf
import pandas as pd
import numpy as np

# ─── Config ───────────────────────────────────────────────────────────────────
OUTPUT_FILE     = "data.json"
PORTFOLIO_FILE  = "portfolio.json"
DELAY_BETWEEN   = 0.8   # seconds between tickers
MAX_RETRIES     = 3
PORTFOLIO_START = 1_000_000.0   # starting cash
BUY_THRESHOLD   = 70.0          # buy stocks with overall >= 70 (≈ C or better)
SELL_THRESHOLD  = 65.0          # sell stocks with overall < 65

# ─── Ticker universe ──────────────────────────────────────────────────────────

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

EXTRA_TICKERS = [
    "ABNB","ARM","AXON","COIN","CRWD","DDOG","DASH","DUOL","EXAS","HOOD",
    "MELI","NTNX","OKTA","PANW","PATH","PLTR","RBLX","RIVN","SHOP","SMCI",
    "SNOW","SOFI","SPOT","SQ","TTD","UBER","VEEV","ZM","ZS",
]

def get_ticker_universe():
    combined = sorted(set(SP500_TICKERS + EXTRA_TICKERS))
    print(f"Ticker universe: {len(combined)} tickers")
    return combined


# ─── Safe helpers ─────────────────────────────────────────────────────────────

def safe(val, default=None):
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
    v = safe(val)
    if v is None:
        return default
    return round(v * 100, 2)

def calc_growth(new_val, old_val):
    n = safe(new_val)
    o = safe(old_val)
    if n is None or o is None or o == 0:
        return None
    return round((n - o) / abs(o) * 100, 2)


# ─── Per-ticker fetch ─────────────────────────────────────────────────────────

def fetch_ticker_data(symbol):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tk   = yf.Ticker(symbol)
            info = tk.info or {}

            market_cap = safe(info.get("marketCap"))
            if market_cap is None or market_cap < 20e9:   # require >$20B market cap
                return None

            name     = info.get("longName") or info.get("shortName") or symbol
            sector   = info.get("sector")   or "Unknown"
            industry = info.get("industry") or "Unknown"

            # ── Price ─────────────────────────────────────────────────────
            price        = safe(info.get("currentPrice") or info.get("regularMarketPrice"))
            target_price = safe(info.get("targetMeanPrice"))
            analyst_upside = None
            if price and target_price and price > 0:
                analyst_upside = round((target_price - price) / price * 100, 2)

            # 52-week performance via actual history
            perf_52w = None
            try:
                hist = tk.history(period="1y", auto_adjust=True)
                if not hist.empty and price:
                    price_1y_ago = float(hist["Close"].iloc[0])
                    if price_1y_ago > 0:
                        perf_52w = round((price - price_1y_ago) / price_1y_ago * 100, 2)
            except Exception:
                pass

            # ── Valuation ─────────────────────────────────────────────────
            forward_pe  = safe(info.get("forwardPE"))
            peg_ratio   = safe(info.get("pegRatio"))
            ev_ebitda   = safe(info.get("enterpriseToEbitda"))
            price_sales = safe(info.get("priceToSalesTrailing12Months"))

            # ── Analyst rec label ──────────────────────────────────────────
            analyst_rec = safe(info.get("recommendationMean"))
            analyst_rec_label = None
            if analyst_rec is not None:
                if analyst_rec <= 1.5:   analyst_rec_label = "Strong Buy"
                elif analyst_rec <= 2.2: analyst_rec_label = "Buy"
                elif analyst_rec <= 2.8: analyst_rec_label = "Hold"
                elif analyst_rec <= 3.5: analyst_rec_label = "Underperform"
                else:                    analyst_rec_label = "Sell"

            # ── Profitability ─────────────────────────────────────────────
            gross_margin     = safe_pct(info.get("grossMargins"))
            operating_margin = safe_pct(info.get("operatingMargins"))
            profit_margin    = safe_pct(info.get("profitMargins"))
            roe              = safe_pct(info.get("returnOnEquity"))
            roa              = safe_pct(info.get("returnOnAssets"))
            debt_equity      = safe(info.get("debtToEquity"))
            if debt_equity is not None:
                debt_equity = round(debt_equity / 100, 3)

            # ── Growth fallbacks from info ─────────────────────────────────
            rev_growth_info = safe_pct(info.get("revenueGrowth"))
            eps_growth_info = safe_pct(info.get("earningsGrowth"))

            # ── Quarterly financials ───────────────────────────────────────
            rev_growth_ttm       = None
            eps_growth_ttm       = None
            rev_accel            = None
            eps_accel            = None

            try:
                # yfinance returns quarterly_income_stmt with rows as metrics,
                # columns as quarter-end dates (newest first after sort).
                q_inc = tk.quarterly_income_stmt
                a_inc = tk.income_stmt   # annual, newest first

                if q_inc is not None and not q_inc.empty:
                    # Ensure newest-first column order
                    q_inc = q_inc.sort_index(axis=1, ascending=False)
                    nq    = q_inc.shape[1]

                    def get_row(df, *names):
                        for n in names:
                            if n in df.index:
                                return df.loc[n].astype(float)
                        return None

                    rev_q = get_row(q_inc, "Total Revenue", "Revenue", "Net Revenue")
                    eps_q = get_row(q_inc, "Diluted EPS", "Basic EPS",
                                    "Basic And Diluted EPS")

                    # ── TTM revenue growth ─────────────────────────────────
                    # Method 1: 8 quarters available — compare TTM to prior TTM
                    if rev_q is not None and nq >= 8:
                        ttm  = rev_q.iloc[:4].sum()
                        prev = rev_q.iloc[4:8].sum()
                        if ttm and prev and prev != 0:
                            rev_growth_ttm = round((ttm - prev) / abs(prev) * 100, 2)

                    # Method 2: compare TTM to most recent full fiscal year
                    if rev_growth_ttm is None and rev_q is not None and nq >= 4 \
                            and a_inc is not None and not a_inc.empty:
                        a_inc_s = a_inc.sort_index(axis=1, ascending=False)
                        rev_a   = get_row(a_inc_s, "Total Revenue", "Revenue", "Net Revenue")
                        if rev_a is not None and len(rev_a) >= 1:
                            ttm      = rev_q.iloc[:4].sum()
                            prior_yr = safe(rev_a.iloc[0])
                            if ttm and prior_yr:
                                rev_growth_ttm = round((ttm - prior_yr) / abs(prior_yr) * 100, 2)

                    # ── Revenue acceleration ───────────────────────────────
                    # Q0 YoY vs Q1 YoY  (need year-ago quarters)
                    # Prefer exact year-ago from 8-qtr data; fallback to annual/4
                    if rev_q is not None and nq >= 2:
                        q0 = safe(rev_q.iloc[0])
                        q1 = safe(rev_q.iloc[1])

                        # Exact year-ago quarters
                        q0_ya = safe(rev_q.iloc[4]) if nq >= 5 else None
                        q1_ya = safe(rev_q.iloc[5]) if nq >= 6 else None

                        # Annual/4 fallback
                        if (q0_ya is None or q1_ya is None) \
                                and a_inc is not None and not a_inc.empty:
                            a_inc_s = a_inc.sort_index(axis=1, ascending=False)
                            rev_a   = get_row(a_inc_s, "Total Revenue", "Revenue", "Net Revenue")
                            if rev_a is not None and len(rev_a) >= 2:
                                # Use most recent and prior fiscal year /4
                                yr0 = safe(rev_a.iloc[0])
                                yr1 = safe(rev_a.iloc[1])
                                if q0_ya is None and yr0:
                                    q0_ya = yr0 / 4
                                if q1_ya is None and yr1:
                                    q1_ya = yr1 / 4

                        if q0 and q0_ya and q1 and q1_ya and q0_ya != 0 and q1_ya != 0:
                            yoy0 = (q0 - q0_ya) / abs(q0_ya) * 100
                            yoy1 = (q1 - q1_ya) / abs(q1_ya) * 100
                            rev_accel = round(yoy0 - yoy1, 2)

                    # ── EPS TTM growth ─────────────────────────────────────
                    if eps_q is not None and nq >= 8:
                        ttm  = eps_q.iloc[:4].sum()
                        prev = eps_q.iloc[4:8].sum()
                        if ttm and prev and prev != 0:
                            eps_growth_ttm = round((ttm - prev) / abs(prev) * 100, 2)

                    if eps_growth_ttm is None and eps_q is not None and nq >= 4 \
                            and a_inc is not None and not a_inc.empty:
                        a_inc_s = a_inc.sort_index(axis=1, ascending=False)
                        eps_a   = get_row(a_inc_s, "Diluted EPS", "Basic EPS",
                                          "Basic And Diluted EPS")
                        if eps_a is not None and len(eps_a) >= 1:
                            ttm      = eps_q.iloc[:4].sum()
                            prior_yr = safe(eps_a.iloc[0])
                            if ttm and prior_yr:
                                eps_growth_ttm = round((ttm - prior_yr) / abs(prior_yr) * 100, 2)

                    # ── EPS acceleration ───────────────────────────────────
                    if eps_q is not None and nq >= 2:
                        e0 = safe(eps_q.iloc[0])
                        e1 = safe(eps_q.iloc[1])
                        e0_ya = safe(eps_q.iloc[4]) if nq >= 5 else None
                        e1_ya = safe(eps_q.iloc[5]) if nq >= 6 else None

                        if (e0_ya is None or e1_ya is None) \
                                and a_inc is not None and not a_inc.empty:
                            a_inc_s = a_inc.sort_index(axis=1, ascending=False)
                            eps_a   = get_row(a_inc_s, "Diluted EPS", "Basic EPS",
                                              "Basic And Diluted EPS")
                            if eps_a is not None and len(eps_a) >= 2:
                                yr0 = safe(eps_a.iloc[0])
                                yr1 = safe(eps_a.iloc[1])
                                if e0_ya is None and yr0:
                                    e0_ya = yr0 / 4
                                if e1_ya is None and yr1:
                                    e1_ya = yr1 / 4

                        if e0 and e0_ya and e1 and e1_ya and e0_ya != 0 and e1_ya != 0:
                            yoy0 = (e0 - e0_ya) / abs(e0_ya) * 100
                            yoy1 = (e1 - e1_ya) / abs(e1_ya) * 100
                            eps_accel = round(yoy0 - yoy1, 2)

            except Exception:
                pass

            # Apply info-level fallbacks
            if rev_growth_ttm is None:
                rev_growth_ttm = rev_growth_info
            if eps_growth_ttm is None:
                eps_growth_ttm = eps_growth_info

            # ── PEG: manual fallback if yfinance pegRatio is None ─────────
            # PEG = Forward P/E  /  expected EPS growth rate (as %)
            if peg_ratio is None and forward_pe is not None and eps_growth_ttm is not None:
                growth_rate = eps_growth_ttm   # already a percentage, e.g. 25.0
                if growth_rate and growth_rate > 0:
                    peg_ratio = round(forward_pe / growth_rate, 3)

            # ── Earnings surprise ──────────────────────────────────────────
            # yfinance earnings_dates column names vary by version:
            # v0.2.x: "EPS Estimate", "Reported EPS"
            # Some builds: "EPS Actual", "EPS Estimate"
            # We search for any column containing "estimate" and any containing
            # "report" or "actual" (case-insensitive).
            earnings_surprise = None
            next_earnings     = None
            try:
                ed = tk.earnings_dates
                if ed is not None and not ed.empty:
                    now = pd.Timestamp.now(tz="UTC")
                    cols_lower = {c: c.lower() for c in ed.columns}

                    est_col = next((c for c, cl in cols_lower.items()
                                    if "estimate" in cl), None)
                    act_col = next((c for c, cl in cols_lower.items()
                                    if "reported" in cl or "actual" in cl), None)

                    # Fallback: if only two numeric columns, use them
                    if est_col is None or act_col is None:
                        num_cols = [c for c in ed.columns
                                    if pd.api.types.is_numeric_dtype(ed[c])]
                        if len(num_cols) >= 2 and est_col is None:
                            est_col = num_cols[0]
                        if len(num_cols) >= 2 and act_col is None:
                            act_col = num_cols[1]

                    if est_col and act_col:
                        past = ed[ed.index <= now].dropna(subset=[est_col, act_col])
                        if not past.empty:
                            row = past.iloc[0]
                            actual   = safe(row[act_col])
                            estimate = safe(row[est_col])
                            if actual is not None and estimate is not None and estimate != 0:
                                earnings_surprise = round(
                                    (actual - estimate) / abs(estimate) * 100, 2)

                    future = ed[ed.index > now]
                    if not future.empty:
                        next_earnings = future.index[-1].strftime("%b %d, %Y")

            except Exception:
                pass

            return {
                "ticker":           symbol,
                "name":             name,
                "sector":           sector,
                "industry":         industry,
                "price":            price,
                "target_price":     target_price,
                "analyst_upside":   analyst_upside,
                "analyst_rec":      analyst_rec,
                "analyst_rec_label": analyst_rec_label,
                "perf_52w":         perf_52w,
                "market_cap_b":     round(market_cap / 1e9, 2),
                "market_cap_raw":   market_cap,
                "forward_pe":       forward_pe,
                "peg_ratio":        peg_ratio,
                "ev_ebitda":        ev_ebitda,
                "price_sales":      price_sales,
                "rev_growth_ttm":   rev_growth_ttm,
                "eps_growth_ttm":   eps_growth_ttm,
                "rev_accel":        rev_accel,
                "eps_accel":        eps_accel,
                "earnings_surprise":earnings_surprise,
                "gross_margin":     gross_margin,
                "operating_margin": operating_margin,
                "profit_margin":    profit_margin,
                "roe":              roe,
                "roa":              roa,
                "debt_equity":      debt_equity,
                "next_earnings":    next_earnings,
            }

        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                print(f"    ERROR {symbol}: {e}")
                return None


# ─── Scoring ──────────────────────────────────────────────────────────────────
#
# Each metric scores 0–10 via interpolation (not stepped buckets).
# Category averages are weighted:
#   Growth       55%  (heavily favored — this is a growth stock model)
#   Profitability 20%
#   Valuation    15%
#   Momentum     10%
#
# Final score = 0–100.  Grades: A=90-100, B=80-89, C=70-79, D=60-69, F<60.

FINANCIALS_SECTORS = {"Financial Services", "Financials"}
UTILITIES_SECTORS  = {"Utilities"}

def score_interp(value, breakpoints, reverse=False):
    """
    Smoothly interpolate a 0–10 score from a list of (threshold, score) pairs.
    breakpoints: list of (value, score) sorted by value ascending.
    reverse=True: lower value → higher score (clamp and invert).
    Returns None if value is None.
    """
    if value is None:
        return None
    bp = breakpoints
    if reverse:
        # Mirror: high raw value → low score
        v = value
        # Clamp to range
        if v <= bp[0][0]:  return 10.0
        if v >= bp[-1][0]: return 0.0
        for i in range(len(bp)-1):
            lo_v, lo_s = bp[i]
            hi_v, hi_s = bp[i+1]
            if lo_v <= v <= hi_v:
                t = (v - lo_v) / (hi_v - lo_v)
                return round(lo_s + t * (hi_s - lo_s), 3)
    else:
        v = value
        if v <= bp[0][0]:  return 0.0
        if v >= bp[-1][0]: return 10.0
        for i in range(len(bp)-1):
            lo_v, lo_s = bp[i]
            hi_v, hi_s = bp[i+1]
            if lo_v <= v <= hi_v:
                t = (v - lo_v) / (hi_v - lo_v)
                return round(lo_s + t * (hi_s - lo_s), 3)
    return None

# Growth metric breakpoints  (value → score 0–10)
BP_REV_GROWTH  = [(-20,0),(0,2),(5,4),(10,6),(20,8),(40,10)]    # Rev YoY %
BP_EPS_GROWTH  = [(-20,0),(0,2),(5,4),(15,6),(25,8),(50,10)]    # EPS YoY %
BP_ACCEL       = [(-20,0),(-5,2),(-1,4),(1,6),(5,8),(15,10)]    # pp acceleration
BP_SURPRISE    = [(-10,0),(-2,3),(0,5),(2,7),(5,9),(10,10)]     # EPS surprise %

# Valuation (reverse=True — lower is better for growth stocks)
BP_FWD_PE      = [(5,10),(15,9),(25,7),(35,5),(45,3),(60,1),(80,0)]
BP_PEG         = [(0.5,10),(1.0,9),(1.5,7),(2.0,5),(3.0,3),(4.0,1),(6.0,0)]
BP_EV_EBITDA   = [(5,10),(10,8),(15,7),(20,6),(30,4),(45,2),(60,0)]
BP_PS          = [(0.5,10),(2,8),(5,6),(8,5),(12,3),(20,1),(30,0)]

# Profitability
BP_GROSS_MGN   = [(0,0),(10,2),(25,4),(40,6),(55,8),(70,10)]
BP_OP_MGN      = [(-20,0),(0,2),(8,4),(15,6),(25,8),(40,10)]
BP_ROE         = [(-20,0),(0,2),(8,4),(15,6),(25,8),(40,10)]
BP_ROA         = [(-10,0),(0,2),(3,4),(7,6),(12,8),(20,10)]
BP_DE          = [(0,10),(0.3,9),(0.8,7),(1.5,5),(3.0,3),(5.0,1),(10,0)]  # reverse

# Momentum
BP_PERF_52W    = [(-40,0),(-15,2),(0,4),(15,6),(30,8),(60,10)]
BP_UPSIDE      = [(-20,0),(0,4),(5,5),(15,7),(30,9),(50,10)]

def score_analyst_rec(val):
    if val is None: return None
    # 1=Strong Buy→10, 5=Strong Sell→0
    return round(max(0, min(10, (5 - val) / 4 * 10)), 2)

def score_record(raw):
    sector = raw.get("sector", "")
    is_fin  = sector in FINANCIALS_SECTORS
    is_util = sector in UTILITIES_SECTORS
    s = {}

    # ── Growth (55%) ──────────────────────────────────────────────────────
    s["rev_growth_ttm"]    = score_interp(raw["rev_growth_ttm"],  BP_REV_GROWTH)
    s["eps_growth_ttm"]    = score_interp(raw["eps_growth_ttm"],  BP_EPS_GROWTH)
    s["rev_accel"]         = score_interp(raw["rev_accel"],       BP_ACCEL)
    s["eps_accel"]         = score_interp(raw["eps_accel"],       BP_ACCEL)
    s["earnings_surprise"] = score_interp(raw["earnings_surprise"], BP_SURPRISE)

    # Within growth: weight rev/eps growth more heavily than accel/surprise
    growth_weights = {
        "rev_growth_ttm":  0.30,
        "eps_growth_ttm":  0.30,
        "rev_accel":       0.15,
        "eps_accel":       0.15,
        "earnings_surprise": 0.10,
    }
    gw_sum = gw_total = 0
    for k, w in growth_weights.items():
        if s[k] is not None:
            gw_sum   += s[k] * w
            gw_total += w
    growth_avg = round(gw_sum / gw_total, 3) if gw_total > 0 else None

    # ── Valuation (15%) ───────────────────────────────────────────────────
    # For growth stocks, P/S and EV/EBITDA matter more than raw P/E;
    # PEG is the most important because it normalises price for growth.
    s["peg_ratio"]  = score_interp(raw["peg_ratio"],   BP_PEG,      reverse=True)
    s["forward_pe"] = score_interp(raw["forward_pe"],  BP_FWD_PE,   reverse=True)
    s["ev_ebitda"]  = score_interp(raw["ev_ebitda"],   BP_EV_EBITDA,reverse=True)
    s["price_sales"]= score_interp(raw["price_sales"], BP_PS,       reverse=True)

    val_weights = {"peg_ratio":0.40, "forward_pe":0.25,
                   "ev_ebitda":0.20, "price_sales":0.15}
    vw_sum = vw_total = 0
    for k, w in val_weights.items():
        if s[k] is not None:
            vw_sum   += s[k] * w
            vw_total += w
    val_avg = round(vw_sum / vw_total, 3) if vw_total > 0 else None

    # ── Profitability (20%) ───────────────────────────────────────────────
    s["gross_margin"]     = score_interp(raw["gross_margin"],     BP_GROSS_MGN)
    s["operating_margin"] = score_interp(raw["operating_margin"], BP_OP_MGN)
    s["roe"]              = score_interp(raw["roe"],              BP_ROE)
    s["roa"]              = score_interp(raw["roa"],              BP_ROA)
    # D/E not meaningful for banks/utilities
    s["debt_equity"] = None if (is_fin or is_util) else \
                       score_interp(raw["debt_equity"], BP_DE, reverse=True)

    prof_weights = {"gross_margin":0.30, "operating_margin":0.30,
                    "roe":0.20, "roa":0.10, "debt_equity":0.10}
    pw_sum = pw_total = 0
    for k, w in prof_weights.items():
        if s[k] is not None:
            pw_sum   += s[k] * w
            pw_total += w
    prof_avg = round(pw_sum / pw_total, 3) if pw_total > 0 else None

    # ── Momentum (10%) ────────────────────────────────────────────────────
    s["perf_52w"]       = score_interp(raw["perf_52w"],       BP_PERF_52W)
    s["analyst_upside"] = score_interp(raw["analyst_upside"], BP_UPSIDE)
    s["analyst_rec"]    = score_analyst_rec(raw["analyst_rec"])

    mom_weights = {"perf_52w":0.40, "analyst_upside":0.35, "analyst_rec":0.25}
    mw_sum = mw_total = 0
    for k, w in mom_weights.items():
        if s[k] is not None:
            mw_sum   += s[k] * w
            mw_total += w
    mom_avg = round(mw_sum / mw_total, 3) if mw_total > 0 else None

    # ── Weighted overall → 0–100 ──────────────────────────────────────────
    weighted_sum = weighted_total = 0
    for avg, w in [(growth_avg, 0.55), (prof_avg, 0.20),
                   (val_avg, 0.15),    (mom_avg, 0.10)]:
        if avg is not None:
            weighted_sum   += avg * w
            weighted_total += w

    # Each category avg is 0–10; multiply by 10 to get 0–100
    overall_raw = (weighted_sum / weighted_total * 10) if weighted_total > 0 else None
    overall     = round(overall_raw, 1) if overall_raw is not None else None

    grade = "-"
    if overall is not None:
        if overall >= 90:   grade = "A"
        elif overall >= 80: grade = "B"
        elif overall >= 70: grade = "C"
        elif overall >= 60: grade = "D"
        else:               grade = "F"

    grade_color = {"A":"grade-a","B":"grade-b","C":"grade-c",
                   "D":"grade-d","F":"grade-f"}.get(grade, "neutral")

    return {
        **raw,
        "scores":      s,
        "growth_avg":  round(growth_avg * 10, 1) if growth_avg is not None else None,
        "val_avg":     round(val_avg    * 10, 1) if val_avg    is not None else None,
        "prof_avg":    round(prof_avg   * 10, 1) if prof_avg   is not None else None,
        "mom_avg":     round(mom_avg    * 10, 1) if mom_avg    is not None else None,
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


# ─── Portfolio management ─────────────────────────────────────────────────────

def load_portfolio():
    p = Path(PORTFOLIO_FILE)
    if p.exists():
        return json.loads(p.read_text())
    return None

RESET_PORTFOLIO = True   # ← set to False after first run to preserve history

def save_portfolio(portfolio):
    Path(PORTFOLIO_FILE).write_text(json.dumps(portfolio, indent=2, default=str))

def get_sp500_history(start_date):
    """Fetch SPY price history from start_date to today for benchmark."""
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(start=start_date, auto_adjust=True)
        if hist.empty:
            return []
        start_price = float(hist["Close"].iloc[0])
        result = []
        for dt, row in hist.iterrows():
            result.append({
                "date":  dt.strftime("%Y-%m-%d"),
                "value": round(PORTFOLIO_START * float(row["Close"]) / start_price, 2)
            })
        return result
    except Exception as e:
        print(f"  WARNING: Could not fetch SPY history: {e}")
        return []

def update_portfolio(records, portfolio):
    """
    Given current stock records and existing portfolio state,
    buy/sell based on grade thresholds and update holdings.
    Returns updated portfolio dict.
    """
    today_str = date.today().isoformat()

    # Build lookup by ticker
    stock_map = {r["ticker"]: r for r in records}

    holdings  = portfolio.get("holdings", {})
    cash      = portfolio.get("cash", PORTFOLIO_START)
    history   = portfolio.get("history", [])
    trades    = portfolio.get("trades", [])

    # ── Step 1: Sell anything that fell below threshold ────────────────────
    to_sell = []
    for ticker, pos in holdings.items():
        stock = stock_map.get(ticker)
        if stock is None:
            to_sell.append(ticker)   # no longer in universe
            continue
        overall = stock.get("overall")
        if overall is None or overall < SELL_THRESHOLD:
            to_sell.append(ticker)

    for ticker in to_sell:
        pos   = holdings[ticker]
        stock = stock_map.get(ticker)
        price = stock["price_raw"] if stock else pos.get("last_price", pos["cost_basis"])
        if price is None:
            price = pos.get("last_price", pos["cost_basis"])
        proceeds = pos["shares"] * price
        cash += proceeds
        gain_pct = round((price - pos["cost_basis"]) / pos["cost_basis"] * 100, 2) \
                   if pos["cost_basis"] else 0
        trades.append({
            "date":      today_str,
            "action":    "SELL",
            "ticker":    ticker,
            "shares":    pos["shares"],
            "price":     round(price, 2),
            "proceeds":  round(proceeds, 2),
            "gain_pct":  gain_pct,
        })
        print(f"    SELL {ticker}: {pos['shares']:.4f} sh @ ${price:.2f}  gain={gain_pct:+.1f}%")
        del holdings[ticker]

    # ── Step 2: Determine buy candidates ──────────────────────────────────
    buy_candidates = [
        r for r in records
        if r.get("overall") is not None
        and r["overall"] >= BUY_THRESHOLD
        and r["ticker"] not in holdings
        and r.get("price_raw") is not None
        and r["price_raw"] > 0
    ]

    # Weight by overall score (proportional)
    if buy_candidates:
        total_score = sum(r["overall"] for r in buy_candidates)
        # Also include existing holdings in the allocation pool
        existing_tickers = list(holdings.keys())
        existing_scores  = [
            stock_map[t]["overall"]
            for t in existing_tickers
            if stock_map.get(t) and stock_map[t].get("overall") is not None
        ]
        all_scores = [r["overall"] for r in buy_candidates] + existing_scores
        total_score_all = sum(all_scores)

        # Target portfolio value (current holdings MV + cash)
        holdings_mv = sum(
            h["shares"] * (stock_map[t]["price_raw"] if stock_map.get(t) and
                           stock_map[t].get("price_raw") else h["last_price"])
            for t, h in holdings.items()
        )
        total_portfolio = holdings_mv + cash

        # Buy each new candidate up to its target weight
        for r in buy_candidates:
            weight       = r["overall"] / total_score_all
            target_value = total_portfolio * weight
            price        = r["price_raw"]
            if price is None or price <= 0:
                continue
            affordable = min(target_value, cash * 0.98)   # leave 2% buffer
            if affordable < price:
                continue   # can't afford even 1 share
            shares = affordable / price
            cost   = shares * price
            cash  -= cost
            holdings[r["ticker"]] = {
                "shares":      round(shares, 6),
                "cost_basis":  round(price, 4),
                "last_price":  round(price, 4),
                "bought_date": today_str,
            }
            trades.append({
                "date":    today_str,
                "action":  "BUY",
                "ticker":  r["ticker"],
                "shares":  round(shares, 6),
                "price":   round(price, 2),
                "cost":    round(cost, 2),
            })
            print(f"    BUY  {r['ticker']}: {shares:.4f} sh @ ${price:.2f}")

    # ── Step 3: Update last prices for all holdings ────────────────────────
    holdings_mv = 0
    for ticker, pos in holdings.items():
        stock = stock_map.get(ticker)
        if stock and stock.get("price_raw"):
            pos["last_price"] = round(stock["price_raw"], 4)
        holdings_mv += pos["shares"] * pos["last_price"]

    total_value = holdings_mv + cash

    # ── Step 4: Append today's portfolio value to history ─────────────────
    # Avoid duplicate date entries
    if not history or history[-1]["date"] != today_str:
        history.append({
            "date":  today_str,
            "value": round(total_value, 2),
            "cash":  round(cash, 2),
        })

    portfolio.update({
        "holdings":    holdings,
        "cash":        round(cash, 2),
        "total_value": round(total_value, 2),
        "history":     history,
        "trades":      trades,
        "updated_at":  today_str,
    })

    return portfolio

def init_portfolio(records):
    """Create a fresh portfolio from current records."""
    today_str    = date.today().isoformat()
    print(f"  Initialising new portfolio on {today_str} with ${PORTFOLIO_START:,.0f}")

    # Fetch SPY history from today (will just be 1 point at start)
    spy_history = get_sp500_history(today_str)

    portfolio = {
        "start_date":   today_str,
        "start_value":  PORTFOLIO_START,
        "cash":         PORTFOLIO_START,
        "holdings":     {},
        "history":      [],
        "spy_history":  spy_history,
        "trades":       [],
        "updated_at":   today_str,
    }
    portfolio = update_portfolio(records, portfolio)

    # Extend spy history to cover full period on future runs
    # (history starts today so spy_history also starts today)
    return portfolio

def refresh_spy_history(portfolio):
    """Extend SPY benchmark history to today."""
    start = portfolio.get("start_date", date.today().isoformat())
    spy_h = get_sp500_history(start)
    if spy_h:
        portfolio["spy_history"] = spy_h
    return portfolio


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    start_time = datetime.now(timezone.utc)
    print(f"=== Stock Tracker v3 | {start_time.strftime('%Y-%m-%d %H:%M UTC')} ===\n")

    tickers = get_ticker_universe()
    print(f"\nProcessing {len(tickers)} tickers...\n")

    records = []
    skipped = errors = 0

    for i, symbol in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {symbol:<8}", end=" ", flush=True)
        try:
            raw = fetch_ticker_data(symbol)
            if raw is None:
                print("skip")
                skipped += 1
            else:
                scored    = score_record(raw)
                formatted = format_record(scored)
                records.append(formatted)
                print(f"✓ {raw['name'][:32]:<32} {fmt_cap(raw['market_cap_b']):>8}  "
                      f"grade={scored['grade']}({scored['overall'] or '-'})")
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
        time.sleep(DELAY_BETWEEN)

    records.sort(key=lambda x: (-(x["overall"] or -99), x["ticker"]))

    end_time = datetime.now(timezone.utc)
    out = {
        "generated_at": end_time.strftime("%Y-%m-%d %H:%M UTC"),
        "total":        len(records),
        "stocks":       records,
    }
    Path(OUTPUT_FILE).write_text(json.dumps(out, indent=2, default=str))

    # ── Portfolio ──────────────────────────────────────────────────────────
    print("\n── Portfolio update ──────────────────────────────────────────────")
    portfolio = load_portfolio()
    if portfolio is None or RESET_PORTFOLIO:
        if RESET_PORTFOLIO and portfolio is not None:
            print("  Resetting portfolio (RESET_PORTFOLIO=True)")
        portfolio = init_portfolio(records)
    else:
        portfolio = refresh_spy_history(portfolio)
        portfolio = update_portfolio(records, portfolio)
    save_portfolio(portfolio)

    print(f"\n=== Done ===")
    print(f"  Stocks:  {len(records)} kept, {skipped} skipped, {errors} errors")
    print(f"  Runtime: {(end_time-start_time).seconds//60}m {(end_time-start_time).seconds%60}s")
    holdings_count = len(portfolio.get("holdings", {}))
    print(f"  Portfolio: ${portfolio['total_value']:,.0f} | "
          f"{holdings_count} holdings | ${portfolio['cash']:,.0f} cash")


if __name__ == "__main__":
    main()
