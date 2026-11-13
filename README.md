# Market Insight 3.0 — Adrian Vale

A market research and risk-planning desktop workspace, rebuilt with React, TypeScript and Tauri 2. The previous Python UI and application implementation are not included.

## Core features
- 50-symbol starter US stock and ETF watchlist, with editable folders and research notes
- Native Yahoo Finance chart-data retrieval through the Tauri backend
- Scanner with daily and 20-day change, EMA 20/50, RSI 14, MACD line, ATR 14 and volume versus its 20-day average
- Transparent illustrative technical checklist score, caution flags, filters and sorting
- Saved scan snapshots (latest 20)
- Price-level alerts checked when quotes are refreshed
- Position-size, risk-amount and reward-to-risk calculator
- Trade journal
- Sydney, Tokyo, London and New York forex-session references plus London, US, Tokyo and Hong Kong exchange hours
- Full JSON backup export, CSV export and a confirmed local-research-data deletion control
- Classy blue and Royal gold appearance themes

## Run locally
```bash
npm install
npm run tauri dev
```

## Test and build
```bash
npm test
npm run build
npm run tauri build
```

## Data, market data and risk
Watchlists, scan snapshots, alerts, plans and journal entries are stored locally in the app. Market prices and daily history are requested from Yahoo Finance by the native desktop backend; data may be delayed, incomplete or unavailable. No brokerage account is connected and the app does not place orders. Technical scores, indicators and position sizing are research aids, not predictions or financial advice. Confirm prices and decisions with your broker or exchange.

## Technology
React 18 · TypeScript · Vite · Tauri 2 · Rust · reqwest

Website: https://adrianvaleitl-debug.github.io/
