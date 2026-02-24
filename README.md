# Stock Tracker

A self-updating stock dashboard that tracks all companies with a market cap > $2B.
Data is sourced from [Finviz](https://finviz.com) and the page updates automatically
every **Sunday at 8 PM Eastern** via GitHub Actions.

## Features

- **Covers all tickers** with market cap > $2B from the Finviz screener
- **Cap category badges**: Mid Cap ($2B–$20B), Large Cap ($20B–$200B), Mega Cap ($200B+)
- **Click any column header to sort** (ascending/descending, numeric-aware)
- **Filter by cap category** or search by ticker symbol
- **Columns**: Ticker, Market Cap, Category, Next Earnings Date, EPS Y/Y TTM, Sales Y/Y TTM,
  EPS/Sales Surprise, EPS & Revenue Quarterly YoY (Est. & Rep.), Revenue Annual (Est. & Rep.),
  EPS & Sales Up/Down Revisions, Avg Target Price
