# Market Insight 3.0 — clean rebuild

A market research and risk-planning desktop workspace by Adrian Vale, rebuilt with React, TypeScript and Tauri 2. The legacy application UI and Python application code are not carried forward.

## Core workspace
- Personal watchlist and symbol scanner
- Native market quote retrieval and daily close history via Yahoo Finance chart data
- SMA 20 and RSI 14 technical reference indicators
- Position sizing and reward-to-risk calculator
- Price level alerts checked when quotes are refreshed
- Trade journal
- Tokyo, London and New York market session reference times
- Classy blue and Royal gold appearance modes

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
Watchlists, alerts, plans and journal entries are stored locally in the app. Market quotes are requested from Yahoo Finance by the native desktop backend; data may be delayed, incomplete or unavailable. No brokerage account is connected and the app does not place orders. Technical indicators and sizing are research aids, not financial advice. Confirm prices and all trading decisions with your broker or exchange.

## Stack
React 18 · TypeScript · Vite · Tauri 2 · Rust · reqwest

Website: https://adrianvaleitl-debug.github.io/
