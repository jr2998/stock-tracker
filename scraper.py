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
DELAY_BETWEEN   = 0.8   # seconds between tickers
MAX_RETRIES     = 3
PORTFOLIO_START = 1_000_000.0   # starting cash
BUY_THRESHOLD   = 65.0          # buy A and B rated stocks (score >= 65)
SELL_THRESHOLD  = 52.0          # sell when grade drops to C (score < 52)

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
            # Treat 0.0 as None — yfinance returns 0.0 (not None) for many
            # tickers where the field is actually unavailable (e.g. NVDA).
            _rg = info.get("revenueGrowth")
            _eg = info.get("earningsGrowth")
            rev_growth_info = safe_pct(_rg) if (_rg is not None and _rg != 0.0) else None
            eps_growth_info = safe_pct(_eg) if (_eg is not None and _eg != 0.0) else None

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

                    def get_row(df, *names):
                        """Find a row by name; fall back to any row containing 'revenue'."""
                        for n in names:
                            if n in df.index:
                                try:
                                    return df.loc[n].astype(float)
                                except Exception:
                                    pass
                        for idx in df.index:
                            if "revenue" in str(idx).lower():
                                try:
                                    return df.loc[idx].astype(float)
                                except Exception:
                                    pass
                        return None

                    def get_eps_row(df):
                        for n in ["Diluted EPS", "Basic EPS",
                                  "Basic And Diluted EPS", "EPS"]:
                            if n in df.index:
                                try:
                                    return df.loc[n].astype(float)
                                except Exception:
                                    pass
                        return None

                    def sv(series, i):
                        """Safe scalar: return float or None (handles NaN)."""
                        if i >= len(series):
                            return None
                        try:
                            f = float(series.iloc[i])
                            return None if (f != f) else f   # NaN → None
                        except Exception:
                            return None

                    def safe_sum(series, start, end):
                        """Sum a slice; return None if too many NaNs."""
                        sl = series.iloc[start:end].dropna()
                        needed = end - start
                        if len(sl) < needed - 1:   # allow at most 1 missing
                            return None
                        return float(sl.sum())

                    rev_q = get_row(q_inc, "Total Revenue", "Revenue",
                                    "Net Revenue", "Operating Revenue",
                                    "Total Net Revenue")
                    eps_q = get_eps_row(q_inc)

                    # ── TTM revenue growth ─────────────────────────────────
                    if rev_q is not None:
                        ttm = safe_sum(rev_q, 0, 4)
                        if ttm is not None:
                            if nq >= 8:
                                prev = safe_sum(rev_q, 4, 8)
                                if prev and prev != 0:
                                    rev_growth_ttm = round(
                                        (ttm - prev) / abs(prev) * 100, 2)
                            if rev_growth_ttm is None and a_inc is not None \
                                    and not a_inc.empty:
                                a_s   = a_inc.sort_index(axis=1, ascending=False)
                                rev_a = get_row(a_s, "Total Revenue", "Revenue",
                                                "Net Revenue", "Operating Revenue")
                                if rev_a is not None and len(rev_a) >= 1:
                                    prior = sv(rev_a, 0)
                                    if prior and prior != 0:
                                        rev_growth_ttm = round(
                                            (ttm - prior) / abs(prior) * 100, 2)

                    # ── Revenue acceleration ───────────────────────────────
                    if rev_q is not None and nq >= 2:
                        q0    = sv(rev_q, 0)
                        q1    = sv(rev_q, 1)
                        q0_ya = sv(rev_q, 4) if nq >= 5 else None
                        q1_ya = sv(rev_q, 5) if nq >= 6 else None

                        if (q0_ya is None or q1_ya is None) \
                                and a_inc is not None and not a_inc.empty:
                            a_s   = a_inc.sort_index(axis=1, ascending=False)
                            rev_a = get_row(a_s, "Total Revenue", "Revenue",
                                            "Net Revenue", "Operating Revenue")
                            if rev_a is not None and len(rev_a) >= 2:
                                yr0 = sv(rev_a, 0)
                                yr1 = sv(rev_a, 1)
                                if q0_ya is None and yr0:
                                    q0_ya = yr0 / 4
                                if q1_ya is None and yr1:
                                    q1_ya = yr1 / 4

                        if q0 and q1 and q0_ya and q1_ya \
                                and q0_ya != 0 and q1_ya != 0:
                            yoy0 = (q0 - q0_ya) / abs(q0_ya) * 100
                            yoy1 = (q1 - q1_ya) / abs(q1_ya) * 100
                            rev_accel = round(yoy0 - yoy1, 2)

                    # ── EPS TTM growth ─────────────────────────────────────
                    if eps_q is not None:
                        ttm_e = safe_sum(eps_q, 0, 4)
                        if ttm_e is not None:
                            if nq >= 8:
                                prev_e = safe_sum(eps_q, 4, 8)
                                if prev_e and prev_e != 0:
                                    eps_growth_ttm = round(
                                        (ttm_e - prev_e) / abs(prev_e) * 100, 2)
                            if eps_growth_ttm is None and a_inc is not None \
                                    and not a_inc.empty:
                                a_s   = a_inc.sort_index(axis=1, ascending=False)
                                eps_a = get_eps_row(a_s)
                                if eps_a is not None and len(eps_a) >= 1:
                                    prior_e = sv(eps_a, 0)
                                    if prior_e and prior_e != 0:
                                        eps_growth_ttm = round(
                                            (ttm_e - prior_e) / abs(prior_e) * 100, 2)

                    # ── EPS acceleration ───────────────────────────────────
                    if eps_q is not None and nq >= 2:
                        e0    = sv(eps_q, 0)
                        e1    = sv(eps_q, 1)
                        e0_ya = sv(eps_q, 4) if nq >= 5 else None
                        e1_ya = sv(eps_q, 5) if nq >= 6 else None

                        if (e0_ya is None or e1_ya is None) \
                                and a_inc is not None and not a_inc.empty:
                            a_s   = a_inc.sort_index(axis=1, ascending=False)
                            eps_a = get_eps_row(a_s)
                            if eps_a is not None and len(eps_a) >= 2:
                                yr0 = sv(eps_a, 0)
                                yr1 = sv(eps_a, 1)
                                if e0_ya is None and yr0:
                                    e0_ya = yr0 / 4
                                if e1_ya is None and yr1:
                                    e1_ya = yr1 / 4

                        if e0 and e1 and e0_ya and e1_ya \
                                and e0_ya != 0 and e1_ya != 0:
                            yoy0 = (e0 - e0_ya) / abs(e0_ya) * 100
                            yoy1 = (e1 - e1_ya) / abs(e1_ya) * 100
                            eps_accel = round(yoy0 - yoy1, 2)

            except Exception as e:
                print(f"    [growth calc error {symbol}]: {e}")

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
                records.append(raw)
                cap_str = fmt_cap(raw.get("market_cap_b"))
                print(f"✓ {raw['name'][:32]:<32} {cap_str or '':>8}")
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
