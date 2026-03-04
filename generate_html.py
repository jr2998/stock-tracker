"""
generate_html.py  —  Stock Tracker v3
Reads data.json + portfolio.json, writes index.html (two-page app).
"""

import json
from pathlib import Path
from datetime import datetime

DATA_FILE      = "data.json"
PORTFOLIO_FILE = "portfolio.json"
OUTPUT_FILE    = "index.html"


def build_html(data, portfolio):
    stocks       = data.get("stocks", [])
    generated_at = data.get("generated_at", "Unknown")
    total        = data.get("total", len(stocks))
    sectors      = sorted(set(s.get("sector") or "Unknown" for s in stocks))

    sector_options = "\n".join(
        f'<option value="{s}">{s}</option>' for s in sectors)

    stocks_json    = json.dumps(stocks,    separators=(",", ":"))
    portfolio_json = json.dumps(portfolio, separators=(",", ":"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Stock Grader</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{
      --bg:#f7f5f0;--surface:#ffffff;--surface2:#f0ece4;
      --border:#e0dcd4;--border2:#ccc8c0;
      --text:#1a1a1a;--muted:#888880;--dim:#555550;
      --accent:#c41e3a;--accent-dim:#fce8eb;
      --grade-a:#1a1a1a;--grade-b:#3d3d3d;--grade-c:#c41e3a;
      --grade-d:#e8794a;--grade-f:#aaaaaa;
      --pos:#2d6e2d;--neg:#c41e3a;
      --mono:'IBM Plex Mono',monospace;--sans:'IBM Plex Sans',sans-serif;
      --r:3px;--rl:4px;
    }}
    body{{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.5;min-height:100vh}}

    /* ── Nav ── */
    .nav{{display:flex;align-items:center;gap:0;padding:0 24px;background:var(--surface);border-bottom:2px solid var(--text);position:sticky;top:0;z-index:100}}
    .nav-brand{{font-family:var(--mono);font-weight:700;font-size:16px;color:var(--text);padding:14px 20px 14px 0;margin-right:12px;border-right:1px solid var(--border)}}
    .nav-brand span{{color:var(--accent)}}
    .nav-tab{{font-family:var(--mono);font-size:12px;padding:16px 18px;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;transition:all .15s;text-transform:uppercase;letter-spacing:.06em;background:none;border-top:none;border-left:none;border-right:none}}
    .nav-tab:hover{{color:var(--text)}}
    .nav-tab.active{{color:var(--accent);border-bottom-color:var(--accent)}}
    .nav-right{{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--muted)}}

    /* ── Pages ── */
    .page{{display:none;max-width:1700px;margin:0 auto;padding:28px 24px 80px}}
    .page.active{{display:block}}

    /* ── Section header ── */
    .section-header{{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px}}
    .section-title{{font-family:var(--mono);font-size:20px;font-weight:700;color:var(--text)}}
    .section-sub{{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:4px}}
    .badge-count{{font-family:var(--mono);font-size:22px;font-weight:700;color:var(--accent)}}

    /* ── Grade legend ── */
    .legend{{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap;align-items:center}}
    .legend-label{{font-family:var(--mono);font-size:11px;color:var(--muted);margin-right:4px;text-transform:uppercase;letter-spacing:.06em}}
    .legend-item{{display:flex;align-items:center;gap:5px;font-family:var(--mono);font-size:11px;color:var(--dim)}}
    .grade-badge{{width:24px;height:24px;border-radius:4px;display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}}

    /* ── Controls ── */
    .controls{{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;align-items:flex-end}}
    .ctrl-group{{display:flex;flex-direction:column;gap:4px}}
    .ctrl-label{{font-family:var(--mono);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}
    input[type=text],select{{background:var(--surface2);border:1px solid var(--border2);color:var(--text);font-family:var(--mono);font-size:12px;padding:6px 10px;border-radius:var(--r);outline:none;height:34px;transition:border-color .15s}}
    input[type=text]{{width:200px}}
    input[type=text]:focus,select:focus{{border-color:var(--accent)}}
    select option{{background:var(--surface2)}}
    .btn-grp{{display:flex;gap:3px}}
    .btn{{height:34px;padding:0 12px;border:1px solid var(--border2);background:var(--surface2);color:var(--dim);font-family:var(--mono);font-size:11px;border-radius:var(--r);cursor:pointer;transition:all .15s}}
    .btn:hover{{border-color:var(--accent);color:var(--accent)}}
    .btn.active{{background:var(--accent-dim);border-color:var(--accent);color:var(--accent)}}

    /* ── Table ── */
    .tbl-wrap{{overflow-x:auto;border:1px solid var(--border);border-top:2px solid var(--text);border-radius:0;background:var(--surface);animation:fadeIn .4s ease both}}
    table{{width:100%;border-collapse:collapse;font-size:12px}}
    th:nth-child(1),td:nth-child(1){{position:sticky;left:0;z-index:2;background:var(--surface)}}
    th:nth-child(2),td:nth-child(2){{position:sticky;left:58px;z-index:2;background:var(--surface)}}
    thead th:nth-child(1),thead th:nth-child(2){{z-index:3;background:var(--surface)}}
    thead tr{{background:var(--surface)}}
    th{{padding:9px 12px;text-align:left;font-family:var(--mono);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none;transition:color .15s}}
    th:hover{{color:var(--accent)}}
    th.sorted-asc::after{{content:' ↑';color:var(--accent)}}
    th.sorted-desc::after{{content:' ↓';color:var(--accent)}}
    th.sec,td.sec{{border-left:2px solid var(--border)}}
    tbody tr{{border-bottom:1px solid var(--border);transition:background .1s}}
    tbody tr:last-child{{border-bottom:none}}
    tbody tr:hover{{background:var(--surface2)!important}}
    tbody tr:hover td:nth-child(1),tbody tr:hover td:nth-child(2){{background:var(--surface2)!important}}
    td{{padding:8px 12px;white-space:nowrap;font-family:var(--mono);font-size:12px;color:var(--dim)}}
    .c-ticker{{font-weight:700;color:var(--text);font-size:13px;min-width:58px}}
    .c-name{{font-family:var(--sans);font-size:12px;max-width:180px;overflow:hidden;text-overflow:ellipsis}}
    .gb{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:2px;font-family:var(--mono);font-weight:700;font-size:13px}}
    .grade-a{{background:#1a1a1a;color:#ffffff;border:none}}
    .grade-b{{background:#3d3d3d;color:#ffffff;border:none}}
    .grade-c{{background:#c41e3a;color:#ffffff;border:none}}
    .grade-d{{background:#e8794a;color:#ffffff;border:none}}
    .grade-f{{background:#e8e4dc;color:#999;border:1px solid var(--border2)}}
    .pos{{color:var(--pos)}}.neg{{color:var(--neg)}}.neutral{{color:var(--muted)}}
    .spill{{display:inline-block;padding:2px 7px;border-radius:2px;background:var(--surface2);border:1px solid var(--border);font-size:10px;color:var(--dim);font-family:var(--mono);}}
    .scbar{{display:flex;align-items:center;gap:5px}}
    .scbar-wrap{{width:32px;height:4px;background:var(--border2);border-radius:2px;overflow:hidden}}
    .scbar-fill{{height:100%;border-radius:2px}}
    .empty{{text-align:center;padding:50px 20px;color:var(--muted);font-family:var(--mono)}}
    /* ── Column group headers ── */
    .th-group{{background:var(--surface)!important;font-family:var(--mono);font-size:9px;font-weight:700;
      text-transform:uppercase;letter-spacing:.12em;color:var(--muted);padding:5px 12px 4px;
      border-bottom:2px solid var(--border);text-align:center;cursor:default}}
    .th-group.grp-info{{color:var(--dim)}}
    .th-group.grp-growth{{color:#1a1a1a;border-bottom-color:#1a1a1a}}
    .th-group.grp-val{{color:#c41e3a;border-bottom-color:#c41e3a}}
    .th-group.grp-quality{{color:#0057a8;border-bottom-color:#0057a8}}
    .th-group.grp-momentum{{color:#2d6e2d;border-bottom-color:#2d6e2d}}
    /* ── Tooltips ── */
    .th-tip{{position:relative}}
    .th-tip::after{{
      content:attr(data-tip);
      position:absolute;top:calc(100% + 6px);left:50%;transform:translateX(-50%);
      background:#ffffff;color:var(--text);border:1px solid var(--border2);
      border-top:2px solid var(--text);
      border-radius:0;padding:8px 10px;font-size:11px;font-family:var(--sans);
      font-weight:400;letter-spacing:0;text-transform:none;white-space:normal;
      width:200px;line-height:1.45;z-index:200;
      opacity:0;pointer-events:none;transition:opacity .15s;
      box-shadow:0 4px 12px rgba(0,0,0,.12);
    }}
    .th-tip:hover::after{{opacity:1}}
    .empty span{{font-size:28px;display:block;margin-bottom:10px}}

    /* ── Performance page ── */
    .perf-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}}
    .kpi{{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--text);border-radius:0;padding:18px 20px}}
    .kpi-label{{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:6px}}
    .kpi-value{{font-family:var(--mono);font-size:24px;font-weight:700;color:var(--text)}}
    .kpi-sub{{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:4px}}
    .chart-card{{background:var(--surface);border:1px solid var(--border);border-top:2px solid var(--text);border-radius:0;padding:20px;margin-bottom:24px}}
    .chart-title{{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--text);margin-bottom:16px}}
    .chart-legend{{display:flex;gap:16px;margin-bottom:12px}}
    .chart-legend-item{{display:flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;color:var(--dim)}}
    .chart-legend-dot{{width:10px;height:10px;border-radius:50%}}
    .chart-wrap{{position:relative;height:320px}}
    .holdings-title{{font-family:var(--mono);font-size:14px;font-weight:700;color:var(--text);margin-bottom:14px}}

    /* ── Footer ── */
    .footer{{margin-top:32px;padding-top:16px;border-top:1px solid var(--border);font-family:var(--mono);font-size:11px;color:var(--muted);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}}

    @keyframes fadeIn{{from{{opacity:0;transform:translateY(5px)}}to{{opacity:1;transform:translateY(0)}}}}
    ::-webkit-scrollbar{{width:5px;height:5px}}
    ::-webkit-scrollbar-track{{background:var(--bg)}}
    ::-webkit-scrollbar-thumb{{background:var(--border2);border-radius:0}}
    ::-webkit-scrollbar-thumb:hover{{background:var(--text)}}
  </style>
</head>
<body>

<!-- ── Nav ────────────────────────────────────────────────────────────── -->
<nav class="nav">
  <div class="nav-brand">Stock<span>Grader</span></div>
  <button class="nav-tab active" data-page="stock-data">Stock Data</button>
  <button class="nav-tab" data-page="performance">Performance Tracker</button>
  <div class="nav-right">Updated {generated_at}</div>
</nav>

<!-- ════════════════════════════════════════════════════════════════════ -->
<!-- PAGE 1: STOCK DATA                                                   -->
<!-- ════════════════════════════════════════════════════════════════════ -->
<div class="page active" id="page-stock-data">
  <div class="section-header" style="margin-top:24px">
    <div>
      <div class="section-title">Stock Data</div>
      <div class="section-sub">S&P 500 + Large Cap Universe · Yahoo Finance</div>
    </div>
    <div style="text-align:right">
      <span class="badge-count" id="visible-count">{total}</span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--muted)"> companies</span>
    </div>
  </div>

  <div class="legend">
    <span class="legend-label">Grade:</span>
    <div class="legend-item"><span class="gb grade-a">A</span><span>≥78 Exceptional</span></div>
    <div class="legend-item"><span class="gb grade-b">B</span><span>65–77 Good</span></div>
    <div class="legend-item"><span class="gb grade-c">C</span><span>52–64 Average</span></div>
    <div class="legend-item"><span class="gb grade-d">D</span><span>38–51 Weak</span></div>
    <div class="legend-item"><span class="gb grade-f">F</span><span>&lt;38 Poor</span></div>
  </div>

  <div class="controls">
    <div class="ctrl-group">
      <span class="ctrl-label">Search</span>
      <input type="text" id="search" placeholder="Ticker or name…">
    </div>
    <div class="ctrl-group">
      <span class="ctrl-label">Sector</span>
      <select id="sector-filter">
        <option value="">All Sectors</option>
        {sector_options}
      </select>
    </div>
    <div class="ctrl-group">
      <span class="ctrl-label">Grade</span>
      <div class="btn-grp" id="grade-filter">
        <button class="btn active" data-grade="">All</button>
        <button class="btn" data-grade="A">A</button>
        <button class="btn" data-grade="B">B</button>
        <button class="btn" data-grade="C">C</button>
        <button class="btn" data-grade="D">D</button>
        <button class="btn" data-grade="F">F</button>
      </div>
    </div>
  </div>

  <div class="tbl-wrap">
    <table id="stock-table">
      <thead>
        <tr>
          <th colspan="8" class="th-group grp-info">Info</th>
          <th colspan="5" class="th-group grp-growth sec">▲ Growth</th>
          <th colspan="4" class="th-group grp-val sec">$ Valuation</th>
          <th colspan="5" class="th-group grp-quality sec">◆ Quality</th>
          <th colspan="4" class="th-group grp-momentum sec">→ Momentum</th>
        </tr>
        <tr>
          <th data-col="ticker" class="th-tip" data-tip="Stock ticker symbol">Ticker</th>
          <th data-col="name" class="th-tip" data-tip="Company name">Name</th>
          <th data-col="grade" class="sec th-tip" data-tip="Overall letter grade: A (≥78) B (≥65) C (≥52) D (≥38) F (&lt;38)">Grade</th>
          <th data-col="overall" class="th-tip" data-tip="Composite score 0–100 across Growth, Quality, Valuation and Momentum">Score</th>
          <th data-col="sector" class="sec th-tip" data-tip="GICS sector classification">Sector</th>
          <th data-col="market_cap_b" class="th-tip" data-tip="Market capitalisation (price × shares outstanding)">Mkt Cap</th>
          <th data-col="price_raw" class="th-tip" data-tip="Current share price">Price</th>
          <th data-col="perf_52w" class="th-tip" data-tip="Price return over the trailing 52 weeks">52W Perf</th>
          <th data-col="rev_growth_ttm" class="sec th-tip" data-tip="Trailing-twelve-month revenue growth year-over-year. Primary growth signal (14% of score).">Rev Grwth</th>
          <th data-col="eps_growth_ttm" class="th-tip" data-tip="Trailing-twelve-month EPS growth year-over-year. Primary earnings signal (14% of score).">EPS Grwth</th>
          <th data-col="rev_accel" class="th-tip" data-tip="Change in revenue YoY growth rate vs the prior quarter (pp). Positive = growth is speeding up. Key differentiator (10% of score).">Rev Accel</th>
          <th data-col="eps_accel" class="th-tip" data-tip="Change in EPS YoY growth rate vs the prior quarter (pp). Markets pay a premium for accelerating earnings (8% of score).">EPS Accel</th>
          <th data-col="earnings_surprise" class="th-tip" data-tip="Most recent quarter EPS beat vs analyst consensus (%). Beaten-and-raised is a near-term catalyst.">EPS Surpr</th>
          <th data-col="forward_pe" class="sec th-tip" data-tip="Next-twelve-month P/E ratio. High values are tolerated for high-growth stocks — use PEG for growth-adjusted view.">Fwd P/E</th>
          <th data-col="peg_ratio" class="th-tip" data-tip="Price/Earnings-to-Growth. Adjusts P/E for expected growth rate. &lt;1 = cheap vs growth, 1–2.5 = fair, &gt;3.5 = expensive. Highest-weight valuation metric (7.5% of score).">PEG</th>
          <th data-col="ev_ebitda" class="th-tip" data-tip="Enterprise Value / EBITDA. Accounts for debt; useful for capital-intensive companies. Lower = cheaper.">EV/EBITDA</th>
          <th data-col="price_sales" class="th-tip" data-tip="Price / trailing-twelve-month sales. Useful for pre-profit or low-margin companies where P/E is not meaningful.">P/S</th>
          <th data-col="gross_margin" class="sec th-tip" data-tip="Gross profit as % of revenue. Reflects pricing power and cost structure. Note: highly sector-dependent.">Gross Mgn</th>
          <th data-col="operating_margin" class="th-tip" data-tip="Operating income as % of revenue. Best cross-sector profitability signal — most heavily weighted quality metric (9.8% of score).">Op Mgn</th>
          <th data-col="roe" class="th-tip" data-tip="Return on Equity: net income / shareholders equity. Measures how efficiently management generates profit from equity. (7% of score)">ROE</th>
          <th data-col="roa" class="th-tip" data-tip="Return on Assets: net income / total assets. Measures overall asset efficiency.">ROA</th>
          <th data-col="debt_equity" class="th-tip" data-tip="Total debt / total equity. Lower = stronger balance sheet. Excluded for Financials and Utilities where leverage is structural.">D/E</th>
          <th data-col="analyst_upside" class="sec th-tip" data-tip="Consensus analyst price target upside from current price (%).">Analyst ↑</th>
          <th data-col="analyst_rec_label" class="th-tip" data-tip="Analyst consensus recommendation (Strong Buy → Sell) based on mean recommendation score.">Consensus</th>
          <th data-col="target_price" class="th-tip" data-tip="Mean analyst 12-month price target.">Target</th>
          <th data-col="next_earnings" class="th-tip" data-tip="Next scheduled earnings announcement date.">Earnings</th>
        </tr>
      </thead>
      <tbody id="tbl-body"><tr><td colspan="26" class="empty"><span>⟳</span>Loading…</td></tr></tbody>
    </table>
  </div>
  <div class="footer">
    <span>Data from Yahoo Finance · Not financial advice</span>
    <span id="footer-count"></span>
  </div>
</div>

<!-- ════════════════════════════════════════════════════════════════════ -->
<!-- PAGE 2: PERFORMANCE TRACKER                                          -->
<!-- ════════════════════════════════════════════════════════════════════ -->
<div class="page" id="page-performance">
  <div style="margin-top:24px;margin-bottom:22px">
    <div class="section-title">Performance Tracker</div>
    <div class="section-sub">Simulated portfolio · Buys A &amp; B grades (≥65) · Sells at C (&lt;52) · Started <span id="port-start-date">—</span></div>
  </div>

  <!-- KPI Cards -->
  <div class="perf-grid">
    <div class="kpi">
      <div class="kpi-label">Portfolio Value</div>
      <div class="kpi-value" id="kpi-value">—</div>
      <div class="kpi-sub" id="kpi-gain">vs $1,000,000 start</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Total Return</div>
      <div class="kpi-value" id="kpi-return">—</div>
      <div class="kpi-sub" id="kpi-vs-spy">vs S&P 500: —</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Holdings</div>
      <div class="kpi-value" id="kpi-holdings">—</div>
      <div class="kpi-sub" id="kpi-cash">Cash: —</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Total Trades</div>
      <div class="kpi-value" id="kpi-trades">—</div>
      <div class="kpi-sub" id="kpi-updated">Last updated: —</div>
    </div>
  </div>

  <!-- Chart -->
  <div class="chart-card">
    <div class="chart-title">Portfolio vs S&P 500</div>
    <div class="chart-legend">
      <div class="chart-legend-item">
        <div class="chart-legend-dot" style="background:#1a1a1a"></div>
        <span>Portfolio</span>
      </div>
      <div class="chart-legend-item">
        <div class="chart-legend-dot" style="background:#c41e3a"></div>
        <span>S&P 500 (SPY)</span>
      </div>
    </div>
    <div class="chart-wrap"><canvas id="perf-chart"></canvas></div>
  </div>

  <!-- Holdings table -->
  <div class="holdings-title">Current Holdings</div>
  <div class="tbl-wrap" style="margin-bottom:24px">
    <table>
      <thead><tr>
        <th data-col="ticker">Ticker</th>
        <th data-col="name">Name</th>
        <th data-col="sector">Sector</th>
        <th data-col="grade" class="sec">Grade</th>
        <th data-col="overall">Score</th>
        <th data-col="shares" class="sec">Shares</th>
        <th data-col="cost_basis">Cost Basis</th>
        <th data-col="last_price">Cur Price</th>
        <th data-col="mkt_value">Mkt Value</th>
        <th data-col="gain_pct">Gain %</th>
        <th data-col="gain_usd">Gain $</th>
        <th data-col="weight">Weight</th>
        <th data-col="target">Target</th>
        <th data-col="drift">Drift</th>
        <th data-col="days_held">Days</th>
        <th data-col="bought_date">Bought</th>
      </tr></thead>
      <tbody id="holdings-body"><tr><td colspan="16" class="empty"><span>—</span>No holdings yet</td></tr></tbody>
    </table>
  </div>

  <!-- Trade log -->
  <div class="holdings-title">Trade History</div>
  <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th>Date</th>
        <th>Action</th>
        <th>Ticker</th>
        <th>Shares</th>
        <th>Price</th>
        <th>Value</th>
        <th>Gain %</th>
      </tr></thead>
      <tbody id="trades-body"><tr><td colspan="7" class="empty"><span>—</span>No trades yet</td></tr></tbody>
    </table>
  </div>

  <div class="footer">
    <span>Simulated portfolio for informational purposes only · Not financial advice</span>
    <span id="port-footer-updated"></span>
  </div>
</div>

<!-- ── Scripts ─────────────────────────────────────────────────────────── -->
<script>
const STOCKS    = {stocks_json};
const PORTFOLIO = {portfolio_json};

// ── Nav ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('page-' + tab.dataset.page).classList.add('active');
    if (tab.dataset.page === 'performance') renderPerformance();
  }});
}});

// ── Helpers ──────────────────────────────────────────────────────────────────
function parseNum(v) {{
  if (v == null || v === '' || v === '—') return null;
  const n = parseFloat(String(v).replace(/[^0-9.+\u002D]/g, ''));
  return isNaN(n) ? null : n;
}}
function colorCls(v) {{
  const n = (typeof v === 'number') ? v : parseNum(v);
  if (n == null) return 'neutral';
  return n > 0 ? 'pos' : n < 0 ? 'neg' : 'neutral';
}}
function fmtUsd(v) {{
  if (v == null) return '—';
  return '$' + v.toLocaleString('en-US', {{minimumFractionDigits:2,maximumFractionDigits:2}});
}}
function fmtPct(v, plus=true) {{
  if (v == null) return '—';
  return (plus && v > 0 ? '+' : '') + v.toFixed(2) + '%';
}}
function scoreBarColor(a) {{
  if (a == null) return '#ccc8c0';
  if (a>=78) return '#1a1a1a';
  if (a>=65) return '#3d3d3d';
  if (a>=52) return '#c41e3a';
  if (a>=38) return '#e8794a';
  return '#aaaaaa';
}}
function scoreBar(avg) {{
  if (avg == null) return `<td class="neutral">—</td>`;
  const pct = Math.round(avg);   // already 0-100
  const col = scoreBarColor(avg);
  return `<td><div class="scbar"><span style="color:${{col}};font-size:11px">${{avg.toFixed(1)}}</span><div class="scbar-wrap"><div class="scbar-fill" style="width:${{pct}}%;background:${{col}}"></div></div></div></td>`;
}}
function cell(v, color=false, sec=false) {{
  const val = (v != null && v !== '') ? v : '—';
  const cls = color ? colorCls(v) : '';
  const s   = sec ? ' sec' : '';
  return `<td class="${{cls}}${{s}}">${{val}}</td>`;
}}

// ════════════════════════════════════════════════════════════════════════════
// STOCK DATA TABLE
// ════════════════════════════════════════════════════════════════════════════
const NUM_COLS = new Set([
  'overall','growth_avg','val_avg','prof_avg','mom_avg','market_cap_b','price_raw',
  'perf_52w','rev_growth_ttm','eps_growth_ttm','rev_accel','eps_accel',
  'earnings_surprise','forward_pe','peg_ratio','ev_ebitda','price_sales',
  'gross_margin','operating_margin','roe','roa','debt_equity','analyst_upside'
]);

let sortCol='overall', sortDir='desc';
let filterGrade='', filterSector='', filterSearch='';

function extractSort(s, col) {{
  const raw = s[col];
  if (NUM_COLS.has(col)) {{
    const n = (typeof raw==='number') ? raw : parseNum(raw);
    return n ?? (sortDir==='asc' ? Infinity : -Infinity);
  }}
  return String(raw??'').toLowerCase();
}}

function applySort(data) {{
  return [...data].sort((a,b) => {{
    const av=extractSort(a,sortCol), bv=extractSort(b,sortCol);
    if (av<bv) return sortDir==='asc'?-1:1;
    if (av>bv) return sortDir==='asc'?1:-1;
    return 0;
  }});
}}

function applyFilters() {{
  let d = STOCKS;
  if (filterSearch) {{
    const q=filterSearch.toLowerCase();
    d=d.filter(s=>(s.ticker||'').toLowerCase().includes(q)||(s.name||'').toLowerCase().includes(q));
  }}
  if (filterSector) d=d.filter(s=>s.sector===filterSector);
  if (filterGrade)  d=d.filter(s=>s.grade===filterGrade);
  renderStockTable(applySort(d));
}}

function renderStockTable(data) {{
  const tbody = document.getElementById('tbl-body');
  if (!data.length) {{
    tbody.innerHTML=`<tr><td colspan="26" class="empty"><span>∅</span>No results.</td></tr>`;
    return;
  }}
  tbody.innerHTML = data.map(s => `<tr>
    <td class="c-ticker">${{s.ticker}}</td>
    <td class="c-name" title="${{s.name||''}}">${{s.name||'—'}}</td>
    <td class="sec"><span class="gb ${{s.grade_color||''}}">${{s.grade||'—'}}</span></td>
    ${{scoreBar(s.overall)}}
    <td class="sec"><span class="spill">${{s.sector||'—'}}</span></td>
    ${{cell(s.market_cap)}}
    ${{cell(s.price)}}
    ${{cell(s.perf_52w,true)}}
    ${{cell(s.rev_growth_ttm,true,true)}}
    ${{cell(s.eps_growth_ttm,true)}}
    ${{cell(s.rev_accel,true)}}
    ${{cell(s.eps_accel,true)}}
    ${{cell(s.earnings_surprise,true)}}
    ${{cell(s.forward_pe,false,true)}}
    ${{cell(s.peg_ratio)}}
    ${{cell(s.ev_ebitda)}}
    ${{cell(s.price_sales)}}
    ${{cell(s.gross_margin,true,true)}}
    ${{cell(s.operating_margin,true)}}
    ${{cell(s.roe,true)}}
    ${{cell(s.roa,true)}}
    ${{cell(s.debt_equity)}}
    ${{cell(s.analyst_upside,true,true)}}
    ${{cell(s.analyst_rec_label)}}
    ${{cell(s.target_price)}}
    ${{cell(s.next_earnings)}}
  </tr>`).join('');
  document.getElementById('visible-count').textContent = data.length.toLocaleString();
  document.getElementById('footer-count').textContent  =
    `Showing ${{data.length.toLocaleString()}} of ${{STOCKS.length.toLocaleString()}}`;
}}

// Sort click
document.querySelectorAll('#stock-table th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col=th.dataset.col;
    sortDir = sortCol===col ? (sortDir==='asc'?'desc':'asc') : (NUM_COLS.has(col)?'desc':'asc');
    sortCol = col;
    document.querySelectorAll('#stock-table th').forEach(t=>t.classList.remove('sorted-asc','sorted-desc'));
    th.classList.add(sortDir==='asc'?'sorted-asc':'sorted-desc');
    applyFilters();
  }});
}});

document.getElementById('search').addEventListener('input', e => {{ filterSearch=e.target.value.trim(); applyFilters(); }});
document.getElementById('sector-filter').addEventListener('change', e => {{ filterSector=e.target.value; applyFilters(); }});
document.querySelectorAll('#grade-filter .btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('#grade-filter .btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    filterGrade=btn.dataset.grade;
    applyFilters();
  }});
}});

document.querySelector('#stock-table th[data-col="overall"]')?.classList.add('sorted-desc');
applyFilters();

// ════════════════════════════════════════════════════════════════════════════
// PERFORMANCE TRACKER
// ════════════════════════════════════════════════════════════════════════════
let perfChartInstance = null;

function renderPerformance() {{
  if (!PORTFOLIO || !PORTFOLIO.start_date) {{
    document.getElementById('kpi-value').textContent = 'No data';
    return;
  }}

  const P         = PORTFOLIO;
  const startVal  = P.start_value || 1000000;
  const curVal    = P.total_value || startVal;
  const totalRet  = (curVal - startVal) / startVal * 100;
  const holdings  = P.holdings  || {{}};
  const trades    = P.trades    || [];
  const history   = P.history   || [];
  const spyHist   = P.spy_history || [];

  // KPIs
  document.getElementById('port-start-date').textContent = P.start_date || '—';
  document.getElementById('kpi-value').textContent   = fmtUsd(curVal);
  document.getElementById('kpi-value').className     = 'kpi-value ' + (totalRet>=0?'pos':'neg');
  document.getElementById('kpi-return').textContent  = fmtPct(totalRet);
  document.getElementById('kpi-return').className    = 'kpi-value ' + (totalRet>=0?'pos':'neg');
  document.getElementById('kpi-gain').textContent    = `${{fmtUsd(curVal-startVal)}} gain`;
  document.getElementById('kpi-holdings').textContent= Object.keys(holdings).length;
  document.getElementById('kpi-cash').textContent    = 'Cash: ' + fmtUsd(P.cash);
  document.getElementById('kpi-trades').textContent  = trades.length;
  document.getElementById('kpi-updated').textContent = 'Updated: ' + (P.updated_at||'—');

  // SPY return for comparison
  if (spyHist.length >= 2) {{
    const spyStart = spyHist[0].value;
    const spyEnd   = spyHist[spyHist.length-1].value;
    const spyRet   = (spyEnd - spyStart) / spyStart * 100;
    const diff     = totalRet - spyRet;
    document.getElementById('kpi-vs-spy').textContent =
      `vs S&P 500: ${{fmtPct(spyRet)}} (${{diff>=0?'+':''}}${{diff.toFixed(2)}}pp)`;
  }}

  document.getElementById('port-footer-updated').textContent =
    `Portfolio updated ${{P.updated_at||'—'}}`;

  // ── Chart ──────────────────────────────────────────────────────────────
  // Merge portfolio history and SPY history onto common dates
  const portMap = Object.fromEntries(history.map(h=>[h.date, h.value]));
  const spyMap  = Object.fromEntries(spyHist.map(h=>[h.date, h.value]));
  const allDates = [...new Set([...Object.keys(portMap),...Object.keys(spyMap)])].sort();

  // Convert to % return from start
  const portVals = allDates.map(d => portMap[d] != null
    ? ((portMap[d]-startVal)/startVal*100) : null);
  const spyVals  = allDates.map(d => spyMap[d] != null
    ? ((spyMap[d]-startVal)/startVal*100) : null);

  const ctx = document.getElementById('perf-chart').getContext('2d');
  if (perfChartInstance) perfChartInstance.destroy();
  perfChartInstance = new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: allDates,
      datasets: [
        {{
          label: 'Portfolio',
          data: portVals,
          borderColor: '#1a1a1a',
          backgroundColor: 'rgba(26,26,26,0.05)',
          borderWidth: 2,
          pointRadius: allDates.length > 60 ? 0 : 3,
          pointHoverRadius: 5,
          tension: 0.3,
          fill: true,
          spanGaps: true,
        }},
        {{
          label: 'S&P 500',
          data: spyVals,
          borderColor: '#c41e3a',
          backgroundColor: 'rgba(196,30,58,0.04)',
          borderWidth: 2,
          pointRadius: allDates.length > 60 ? 0 : 3,
          pointHoverRadius: 5,
          tension: 0.3,
          fill: true,
          spanGaps: true,
        }},
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode:'index', intersect:false }},
      plugins: {{
        legend: {{ display:false }},
        tooltip: {{
          backgroundColor: '#ffffff',
          borderColor: '#1a1a1a',
          borderWidth: 1,
          titleColor: '#1a1a1a',
          bodyColor: '#555550',
          titleFont: {{ family:"'IBM Plex Mono',monospace", size:11 }},
          bodyFont:  {{ family:"'IBM Plex Mono',monospace", size:11 }},
          callbacks: {{
            label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.y!=null?fmtPct(ctx.parsed.y):'—'}}`
          }}
        }}
      }},
      scales: {{
        x: {{
          grid: {{ color:'rgba(224,220,212,0.8)' }},
          ticks: {{ color:'#888880', font:{{family:"'IBM Plex Mono',monospace",size:10}},
                   maxTicksLimit:12, maxRotation:0 }}
        }},
        y: {{
          grid: {{ color:'rgba(224,220,212,0.8)' }},
          ticks: {{
            color:'#888880',
            font:{{family:"'IBM Plex Mono',monospace",size:10}},
            callback: v => (v>=0?'+':'')+v.toFixed(1)+'%'
          }}
        }}
      }}
    }}
  }});

  // ── Holdings table ─────────────────────────────────────────────────────
  const stockMap = Object.fromEntries(STOCKS.map(s=>[s.ticker,s]));

  // Mirror grader.py _target_weights() so the table shows live targets
  function computeTargetWeights(stocks) {{
    const CONV = 1.5, MAX_P = 0.10, MIN_P = 0.015;
    const elig = stocks.filter(s => (s.overall||0) >= 65 && s.price_raw > 0);
    if (!elig.length) return {{}};
    const raw = {{}};
    elig.forEach(s => {{ raw[s.ticker] = Math.pow(s.overall, CONV); }});
    const tot = Object.values(raw).reduce((a,b)=>a+b,0) || 1;
    const w = {{}};
    for (const [t,v] of Object.entries(raw)) w[t] = Math.max(MIN_P, Math.min(MAX_P, v/tot));
    const totW = Object.values(w).reduce((a,b)=>a+b,0) || 1;
    for (const t in w) w[t] /= totW;
    return w;
  }}
  const targetW = computeTargetWeights(STOCKS);

  const holdArr  = Object.entries(holdings).map(([ticker,pos]) => {{
    const st       = stockMap[ticker] || {{}};
    const curPrice = pos.last_price || pos.cost_basis;
    const mv       = pos.shares * curPrice;
    const gainUsd  = pos.shares * (curPrice - pos.cost_basis);
    const gainPct  = (curPrice - pos.cost_basis) / pos.cost_basis * 100;
    const weight   = curVal > 0 ? mv / curVal * 100 : 0;
    const target   = targetW[ticker] != null ? targetW[ticker] * 100 : null;
    const drift    = target != null ? weight - target : null;
    const daysHeld = pos.bought_date
      ? Math.floor((Date.now() - new Date(pos.bought_date)) / 86400000) : null;
    return {{ ticker, pos, st, curPrice, mv, gainUsd, gainPct, weight, target, drift, daysHeld }};
  }}).sort((a,b) => b.mv - a.mv);

  const hbody = document.getElementById('holdings-body');
  if (!holdArr.length) {{
    hbody.innerHTML = `<tr><td colspan="16" class="empty"><span>—</span>No current holdings</td></tr>`;
  }} else {{
    hbody.innerHTML = holdArr.map(h => {{
      const driftCls = h.drift == null ? '' : h.drift > 3 ? 'neg' : h.drift < -3 ? 'pos' : 'neutral';
      const driftStr = h.drift != null ? (h.drift>=0?'+':'')+h.drift.toFixed(1)+'pp' : '—';
      const targetStr = h.target != null ? h.target.toFixed(1)+'%' : '—';
      const daysStr  = h.daysHeld != null ? h.daysHeld+'d' : '—';
      const daysCls  = h.daysHeld != null && h.daysHeld < 365 ? 'neutral' : '';
      return `<tr>
        <td class="c-ticker">${{h.ticker}}</td>
        <td class="c-name" title="${{h.st.name||''}}">${{h.st.name||'—'}}</td>
        <td><span class="spill">${{h.st.sector||'—'}}</span></td>
        <td class="sec"><span class="gb ${{h.st.grade_color||''}}">${{h.st.grade||'—'}}</span></td>
        ${{scoreBar(h.st.overall)}}
        <td class="sec">${{h.pos.shares.toFixed(4)}}</td>
        <td>${{h.pos.cost_basis.toFixed(2)}}</td>
        <td>${{h.curPrice.toFixed(2)}}</td>
        <td>${{fmtUsd(h.mv)}}</td>
        <td class="${{h.gainPct>=0?'pos':'neg'}}">${{fmtPct(h.gainPct)}}</td>
        <td class="${{h.gainUsd>=0?'pos':'neg'}}">${{fmtUsd(h.gainUsd)}}</td>
        <td>${{h.weight.toFixed(1)}}%</td>
        <td>${{targetStr}}</td>
        <td class="${{driftCls}}">${{driftStr}}</td>
        <td class="${{daysCls}}">${{daysStr}}</td>
        <td>${{h.pos.bought_date||'—'}}</td>
      </tr>`;
    }}).join('');
  }}

  // ── Trade history ──────────────────────────────────────────────────────
  const tbody = document.getElementById('trades-body');
  const tradesSorted = [...trades].reverse();
  if (!tradesSorted.length) {{
    tbody.innerHTML=`<tr><td colspan="7" class="empty"><span>—</span>No trades yet</td></tr>`;
  }} else {{
    tbody.innerHTML = tradesSorted.map(t => {{
      const isBuy  = t.action==='BUY' || t.action==='TOP';
      const isTrim = t.action==='TRIM';
      const val    = isBuy ? t.cost : t.proceeds;
      const gainPct= t.gain_pct != null ? fmtPct(t.gain_pct) : '—';
      const gainCls= t.gain_pct != null ? (t.gain_pct>=0?'pos':'neg') : '';
      const acColor= isBuy ? 'var(--pos)' : isTrim ? '#b05800' : 'var(--neg)';
      const acLabel= t.action;
      return `<tr>
        <td>${{t.date}}</td>
        <td style="color:${{acColor}};font-weight:700">${{acLabel}}</td>
        <td class="c-ticker">${{t.ticker}}</td>
        <td>${{t.shares.toFixed(4)}}</td>
        <td>${{t.price.toFixed(2)}}</td>
        <td>${{fmtUsd(val)}}</td>
        <td class="${{gainCls}}">${{gainPct}}</td>
      </tr>`;
    }}).join('');
  }}
}}
</script>
</body>
</html>"""


def main():
    data_path = Path(DATA_FILE)
    port_path = Path(PORTFOLIO_FILE)

    if not data_path.exists():
        print(f"ERROR: {DATA_FILE} not found. Run scraper.py first.")
        return

    print(f"Reading {DATA_FILE}...")
    data = json.loads(data_path.read_text())
    print(f"  {data.get('total','?')} stocks, generated {data.get('generated_at','?')}")

    portfolio = {}
    if port_path.exists():
        print(f"Reading {PORTFOLIO_FILE}...")
        portfolio = json.loads(port_path.read_text())
        print(f"  Portfolio value: ${portfolio.get('total_value',0):,.0f} | "
              f"{len(portfolio.get('holdings',{}))} holdings")
    else:
        print(f"  No {PORTFOLIO_FILE} found — portfolio section will be empty until scraper runs")

    html = build_html(data, portfolio)
    Path(OUTPUT_FILE).write_text(html, encoding="utf-8")
    print(f"Written {OUTPUT_FILE} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
