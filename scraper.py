"""
scraper.py  —  Stock Tracker v3
Fetches raw fundamentals for all tickers and writes raw_data.json.
Does NOT score or grade — run grader.py after this to produce data.json.

Pipeline:  scraper.py  →  grader.py  →  generate_html.py
Output:    raw_data.json  (this file),  data.json + portfolio.json (grader)
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
OUTPUT_FILE     = "raw_data.json"
PORTFOLIO_FILE  = "portfolio.json"
DELAY_BETWEEN   = 1.2   # seconds between tickers (keep Yahoo rate limits happy)
MAX_RETRIES     = 4
PORTFOLIO_START = 1_000_000.0   # starting cash (used for SPY benchmark scaling)

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
    """Return list of (symbol, require_min_cap) tuples.
    SP500 tickers are fetched regardless of market cap.
    EXTRA_TICKERS require the $20B minimum cap to be included.
    """
    sp500_set = set(SP500_TICKERS)
    extra_set = set(EXTRA_TICKERS) - sp500_set   # avoid double-counting
    combined  = (
        [(t, False) for t in sorted(sp500_set)] +
        [(t, True)  for t in sorted(extra_set)]
    )
    # Sort by symbol but keep the require_min_cap flag
    combined.sort(key=lambda x: x[0])
    print(f"Ticker universe: {len(combined)} tickers "
          f"({len(sp500_set)} S&P 500 + {len(extra_set)} extras)")
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

def fetch_ticker_data(symbol, require_min_cap=True):
    # Some tickers use formats Yahoo Finance doesn't recognise directly.
    yf_symbol = {"BF-B": "BF-B", "BRK-B": "BRK-B"}.get(symbol, symbol)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tk   = yf.Ticker(yf_symbol)
            info = tk.info or {}

            # A valid info dict has 30+ keys. Fewer than 10 means Yahoo returned
            # a minimal/empty response — almost always rate limiting or a transient
            # failure. Don't silently skip: raise so the retry loop can back off.
            if len(info) < 10:
                raise ValueError(f"thin info dict ({len(info)} keys) — likely rate limited")

            market_cap = safe(info.get("marketCap"))

            # For EXTRA_TICKERS (non-index additions) enforce the $20B floor.
            # For SP500 tickers we track everything regardless of current cap —
            # many valid index members dip below $20B and are still worth grading.
            if market_cap is None:
                return None
            if require_min_cap and market_cap < 20e9:
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
            _ev_ebitda_raw = safe(info.get("enterpriseToEbitda"))
            # Negative EV/EBITDA means negative EBITDA — not a useful valuation
            # signal.  Store None so the table shows '-' rather than a confusing
            # negative number.
            ev_ebitda = (_ev_ebitda_raw
                         if (_ev_ebitda_raw is not None and _ev_ebitda_raw > 0)
                         else None)
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

            # Sanity-check ROE: yfinance returns extreme values (e.g. ±1500%)
            # for companies with near-zero or negative equity (SBUX, WYNN, LOW,
            # SBAC).  Beyond ±500% the number is a capital-structure artefact,
            # not a useful profitability signal.
            if roe is not None and abs(roe) > 500:
                roe = None

            # Balance-sheet fallback: when info-level ROE is missing (Yahoo
            # suppresses it for negative-equity companies), calculate directly
            # from TTM net income and most-recent equity.
            if roe is None:
                try:
                    _bs = tk.quarterly_balance_sheet
                    _qi = tk.quarterly_income_stmt
                    if (_bs is not None and not _bs.empty
                            and _qi is not None and not _qi.empty):
                        _bs = _bs.sort_index(axis=1, ascending=False)
                        _qi = _qi.sort_index(axis=1, ascending=False)
                        # TTM net income
                        _ni_row = None
                        for _n in ["Net Income", "Net Income Common Stockholders",
                                   "Net Income Applicable To Common Shares"]:
                            if _n in _qi.index:
                                _ni_row = _qi.loc[_n]
                                break
                        _ttm_ni = None
                        if _ni_row is not None and _qi.shape[1] >= 4:
                            _sl = _ni_row.iloc[:4].astype(float)
                            if not _sl.isna().all():
                                _ttm_ni = float(_sl.sum())
                        # Most-recent equity
                        _eq = None
                        for _en in ["Stockholders Equity", "Common Stock Equity",
                                    "Total Equity Gross Minority Interest"]:
                            if _en in _bs.index:
                                try:
                                    _v = float(_bs.loc[_en].iloc[0])
                                    if _v == _v:    # not NaN
                                        _eq = _v
                                        break
                                except Exception:
                                    pass
                        if _ttm_ni is not None and _eq is not None and _eq != 0:
                            _roe = round(_ttm_ni / abs(_eq) * 100, 2)
                            if _eq < 0:
                                _roe = -abs(_roe)   # negative equity → negative ROE
                            if abs(_roe) <= 500:
                                roe = _roe
                except Exception:
                    pass

            # ── D/E ratio ─────────────────────────────────────────────────────
            # yfinance debtToEquity is expressed as a percentage (e.g. 180 = 1.8×).
            # Yahoo suppresses it when equity is negative, and returns garbage for
            # near-zero equity.  We normalise to a ratio (/100) then validate.
            debt_equity = safe(info.get("debtToEquity"))
            if debt_equity is not None:
                debt_equity = round(debt_equity / 100, 3)
                # Negative ratio = negative equity; >30× is a data artefact.
                if debt_equity < 0 or debt_equity > 30:
                    debt_equity = None

            # Balance-sheet fallback: total debt / |equity|.
            if debt_equity is None:
                try:
                    _bs2 = tk.quarterly_balance_sheet
                    if _bs2 is not None and not _bs2.empty:
                        _bs2 = _bs2.sort_index(axis=1, ascending=False)
                        _debt = None
                        for _dn in ["Total Debt",
                                    "Long Term Debt And Capital Lease Obligation",
                                    "Long Term Debt"]:
                            if _dn in _bs2.index:
                                try:
                                    _v = float(_bs2.loc[_dn].iloc[0])
                                    if _v == _v and _v >= 0:
                                        _debt = _v
                                        break
                                except Exception:
                                    pass
                        _eq2 = None
                        for _en2 in ["Stockholders Equity", "Common Stock Equity",
                                     "Total Equity Gross Minority Interest"]:
                            if _en2 in _bs2.index:
                                try:
                                    _v = float(_bs2.loc[_en2].iloc[0])
                                    if _v == _v:
                                        _eq2 = _v
                                        break
                                except Exception:
                                    pass
                        if _debt is not None and _eq2 is not None and _eq2 != 0:
                            _de = round(_debt / abs(_eq2), 3)
                            if _de <= 30:   # cap; beyond 30× the ratio loses meaning
                                debt_equity = _de
                except Exception:
                    pass

            # ── Growth fallbacks from info ─────────────────────────────────
            # yfinance info.revenueGrowth/earningsGrowth = single-quarter YoY.
            # Treat 0.0 AND values within ±0.15% as missing — yfinance returns
            # near-zero floats as a sentinel for unavailable data on many tickers.
            def _info_growth(raw_val):
                v = safe(raw_val)
                if v is None or abs(v) < 0.0015:   # ±0.15% sentinel threshold
                    return None
                return round(v * 100, 2)

            rev_growth_info = _info_growth(info.get("revenueGrowth"))
            eps_growth_info = _info_growth(info.get("earningsGrowth"))

            # ── Quarterly financials ───────────────────────────────────────
            rev_growth_ttm = None
            eps_growth_ttm = None
            rev_accel      = None
            eps_accel      = None

            try:
                q_inc = tk.quarterly_income_stmt
                a_inc = tk.income_stmt

                if q_inc is not None and not q_inc.empty:
                    q_inc = q_inc.sort_index(axis=1, ascending=False)
                    nq    = q_inc.shape[1]

                    # ── Row finders ────────────────────────────────────────
                    def get_rev_row(df):
                        """Revenue row — explicit names only (avoid 'Cost of Revenue')."""
                        for n in ["Total Revenue", "Revenue", "Net Revenue",
                                  "Operating Revenue", "Total Net Revenue"]:
                            if n in df.index:
                                try:
                                    return df.loc[n].astype(float)
                                except Exception:
                                    pass
                        return None

                    def get_eps_row(df):
                        # Explicit EPS row names — ordered from most to least preferred
                        for n in ["Diluted EPS", "Basic EPS", "Basic And Diluted EPS",
                                  "EPS", "EPS (Diluted)", "Diluted Earnings Per Share",
                                  "Earnings Per Share", "EPS Diluted"]:
                            if n in df.index:
                                try:
                                    return df.loc[n].astype(float)
                                except Exception:
                                    pass
                        # Fuzzy fallback: any row whose name contains 'earnings per share'
                        for idx in df.index:
                            il = str(idx).lower()
                            if "earnings per share" in il:
                                try:
                                    return df.loc[idx].astype(float)
                                except Exception:
                                    pass
                        # Last resort: Net Income (YoY% ≈ EPS% when shares are stable)
                        for n in ["Net Income", "Net Income Common Stockholders",
                                  "Net Income Applicable To Common Shares"]:
                            if n in df.index:
                                try:
                                    return df.loc[n].astype(float)
                                except Exception:
                                    pass
                        return None

                    # ── Normalize timestamps: strip tz for safe naive/aware comparison ──
                    def ts_naive(ts):
                        try:
                            return ts.tz_localize(None) if ts.tzinfo else ts
                        except Exception:
                            return ts

                    # ── Safe scalar from Series ────────────────────────────
                    def sv(series, i):
                        if i >= len(series):
                            return None
                        try:
                            f = float(series.iloc[i])
                            return None if (f != f) else f   # NaN → None
                        except Exception:
                            return None

                    # ── Sum a slice, requiring ALL values present ──────────
                    # (no NaN tolerance — partial sums vs full-year bases give
                    #  false growth rates, which is worse than showing None)
                    def full_sum(series, start, end):
                        sl = series.iloc[start:end]
                        if sl.isna().any():
                            return None
                        return float(sl.sum())

                    # ── Growth from two values, None-safe ─────────────────
                    def pct_chg(new, old):
                        if new is None or old is None or old == 0:
                            return None
                        return round((new - old) / abs(old) * 100, 2)

                    rev_q = get_rev_row(q_inc)
                    eps_q = get_eps_row(q_inc)

                    # ── TTM revenue growth ─────────────────────────────────
                    # Primary: 8 quarter comparison (TTM vs prior TTM)
                    # Fallback: TTM vs annual — but ONLY use the annual whose
                    # period-end date is BEFORE our TTM window starts, to avoid
                    # comparing a fiscal year to itself (the NVDA/BKNG/MCO bug).
                    if rev_q is not None and nq >= 4:
                        ttm = full_sum(rev_q, 0, 4)
                        if ttm is not None:
                            if nq >= 8:
                                prev = full_sum(rev_q, 4, 8)
                                rev_growth_ttm = pct_chg(ttm, prev)

                            if rev_growth_ttm is None and a_inc is not None \
                                    and not a_inc.empty:
                                a_s   = a_inc.sort_index(axis=1, ascending=False)
                                rev_a = get_rev_row(a_s)
                                if rev_a is not None:
                                    # TTM ends at the most recent quarter date;
                                    # TTM starts approximately 1 year before that.
                                    ttm_end   = ts_naive(q_inc.columns[0])   # newest quarter date
                                    ttm_start = ts_naive(q_inc.columns[3])   # oldest quarter in TTM

                                    # Walk annual columns to find the first one
                                    # whose date is strictly before ttm_start.
                                    # This ensures we never compare TTM to a year
                                    # that overlaps with our TTM window.
                                    prior = None
                                    for col_i, col_date in enumerate(a_s.columns):
                                        if ts_naive(col_date) < ttm_start:
                                            prior = sv(rev_a, col_i)
                                            break

                                    rev_growth_ttm = pct_chg(ttm, prior)

                    # ── Revenue acceleration ───────────────────────────────
                    # Q0 YoY vs Q1 YoY growth rate — need year-ago values.
                    # Use exact quarterly ya when nq>=5/6; otherwise fall back
                    # to annual/4.  Key fix: BOTH ya values use the SAME prior
                    # year annual (not annual[0] for one and annual[1] for other).
                    if rev_q is not None and nq >= 2:
                        q0    = sv(rev_q, 0)
                        q1    = sv(rev_q, 1)
                        q0_ya = sv(rev_q, 4) if nq >= 5 else None
                        q1_ya = sv(rev_q, 5) if nq >= 6 else None

                        if (q0_ya is None or q1_ya is None)                                 and a_inc is not None and not a_inc.empty:
                            a_s   = a_inc.sort_index(axis=1, ascending=False)
                            rev_a = get_rev_row(a_s)
                            if rev_a is not None:
                                # Find ONE prior-year annual: most recent whose
                                # date is before the oldest quarter we have
                                oldest_q = ts_naive(q_inc.columns[min(3, nq - 1)])
                                prior_yr = None
                                for col_i, col_date in enumerate(a_s.columns):
                                    if ts_naive(col_date) < oldest_q:
                                        prior_yr = sv(rev_a, col_i)
                                        break
                                if prior_yr:
                                    avg = prior_yr / 4
                                    if q0_ya is None: q0_ya = avg
                                    if q1_ya is None: q1_ya = avg

                        if all(v is not None for v in [q0, q1, q0_ya, q1_ya])                                 and q0_ya != 0 and q1_ya != 0:
                            yoy0 = (q0 - q0_ya) / abs(q0_ya) * 100
                            yoy1 = (q1 - q1_ya) / abs(q1_ya) * 100
                            rev_accel = round(yoy0 - yoy1, 2)

                    # ── EPS TTM growth ─────────────────────────────────────
                    if eps_q is not None and nq >= 4:
                        ttm_e = full_sum(eps_q, 0, 4)
                        if ttm_e is not None:
                            if nq >= 8:
                                prev_e = full_sum(eps_q, 4, 8)
                                eps_growth_ttm = pct_chg(ttm_e, prev_e)

                            if eps_growth_ttm is None and a_inc is not None \
                                    and not a_inc.empty:
                                a_s   = a_inc.sort_index(axis=1, ascending=False)
                                eps_a = get_eps_row(a_s)
                                if eps_a is not None:
                                    ttm_start = ts_naive(q_inc.columns[3])
                                    prior_e   = None
                                    for col_i, col_date in enumerate(a_s.columns):
                                        if ts_naive(col_date) < ttm_start:
                                            prior_e = sv(eps_a, col_i)
                                            break
                                    eps_growth_ttm = pct_chg(ttm_e, prior_e)

                    # ── EPS acceleration ───────────────────────────────────
                    # Same single-prior-year fix as rev_accel.
                    if eps_q is not None and nq >= 2:
                        e0    = sv(eps_q, 0)
                        e1    = sv(eps_q, 1)
                        e0_ya = sv(eps_q, 4) if nq >= 5 else None
                        e1_ya = sv(eps_q, 5) if nq >= 6 else None

                        if (e0_ya is None or e1_ya is None)                                 and a_inc is not None and not a_inc.empty:
                            a_s   = a_inc.sort_index(axis=1, ascending=False)
                            eps_a = get_eps_row(a_s)
                            if eps_a is not None:
                                oldest_q = ts_naive(q_inc.columns[min(3, nq - 1)])
                                prior_yr_e = None
                                for col_i, col_date in enumerate(a_s.columns):
                                    if ts_naive(col_date) < oldest_q:
                                        prior_yr_e = sv(eps_a, col_i)
                                        break
                                if prior_yr_e:
                                    avg_e = prior_yr_e / 4
                                    if e0_ya is None: e0_ya = avg_e
                                    if e1_ya is None: e1_ya = avg_e

                        if all(v is not None for v in [e0, e1, e0_ya, e1_ya])                                 and e0_ya != 0 and e1_ya != 0:
                            yoy0 = (e0 - e0_ya) / abs(e0_ya) * 100
                            yoy1 = (e1 - e1_ya) / abs(e1_ya) * 100
                            eps_accel = round(yoy0 - yoy1, 2)

            except Exception as e:
                print(f"    [growth calc error {symbol}]: {e}")

            # Apply info-level fallbacks (only if quarterly calc produced nothing)
            if rev_growth_ttm is None:
                rev_growth_ttm = rev_growth_info
            if eps_growth_ttm is None:
                eps_growth_ttm = eps_growth_info


            # ── PEG: three-source cascade ─────────────────────────────────
            # Source 1: pegRatio (direct from info, fetched above)
            #
            # Source 2: trailingPegRatio — Yahoo provides this for many tickers
            #   (especially REITs and thinly-covered companies) where the forward
            #   pegRatio is absent.  Only use when positive.
            if peg_ratio is None:
                peg_ratio = safe(info.get("trailingPegRatio"))
                if peg_ratio is not None and peg_ratio <= 0:
                    peg_ratio = None

            # Source 3: Forward P/E / EPS growth rate (manual calculation).
            # Uses the TTM eps_growth_ttm (preferred — our own calculation).
            # Falls back to info-level earningsGrowth when eps_growth_ttm is
            # unavailable (e.g. newly-named tickers, cyclicals with <8 quarters).
            # Note: we bypass the ±0.15% sentinel used for the display field —
            # any positive growth rate is a valid PEG denominator.
            if peg_ratio is None and forward_pe is not None:
                growth_rate = eps_growth_ttm
                if growth_rate is None:
                    _eg_raw = safe(info.get("earningsGrowth"))
                    if _eg_raw is not None and _eg_raw > 0.005:   # > 0.5% floor
                        growth_rate = round(_eg_raw * 100, 2)
                if growth_rate and growth_rate > 0:
                    peg_ratio = round(forward_pe / growth_rate, 3)

            # Sanity clamp: PEG outside (0, 99] is a data artefact
            if peg_ratio is not None and (peg_ratio <= 0 or peg_ratio > 99):
                peg_ratio = None

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
                wait = 2 ** attempt
                print(f"retry({attempt})…", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"ERROR: {e}")
                return None



# ─── Portfolio management ─────────────────────────────────────────────────────

def load_portfolio():
    p = Path(PORTFOLIO_FILE)
    if p.exists():
        return json.loads(p.read_text())
    return None

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

    for i, (symbol, req_cap) in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {symbol:<8}", end=" ", flush=True)
        try:
            raw = fetch_ticker_data(symbol, require_min_cap=req_cap)
            if raw is None:
                print("skip")
                skipped += 1
            else:
                records.append(raw)
                b = raw.get("market_cap_b")
                cap_str = (f"${b/1000:.2f}T" if b and b >= 1000 else f"${b:.1f}B") if b else ""
                print(f"✓ {raw['name'][:32]:<32} {cap_str:>8}")
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
        time.sleep(DELAY_BETWEEN)

    # Sort by market cap descending for readability
    records.sort(key=lambda x: -(x.get("market_cap_b") or 0))

    end_time = datetime.now(timezone.utc)
    out = {
        "generated_at": end_time.strftime("%Y-%m-%d %H:%M UTC"),
        "total":        len(records),
        "stocks":       records,
    }
    Path(OUTPUT_FILE).write_text(json.dumps(out, indent=2, default=str))

    print(f"\n=== Done ===")
    print(f"  Stocks:  {len(records)} fetched, {skipped} skipped, {errors} errors")
    print(f"  Runtime: {(end_time-start_time).seconds//60}m {(end_time-start_time).seconds%60}s")
    print(f"  Output:  {OUTPUT_FILE}")
    print(f"\n  → Now run:  python grader.py")


if __name__ == "__main__":
    main()
