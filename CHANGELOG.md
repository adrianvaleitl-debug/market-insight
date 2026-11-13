# Changelog

## 3.0.0 — clean React + TypeScript rebuild
- Replaced the desktop interface with a new React, TypeScript and Tauri 2 application.
- Rebuilt watchlists, scanner, trade planner, alerts and journal.
- Added a 50-symbol starter universe and editable watchlist folders.
- Added native Yahoo Finance daily OHLCV retrieval through the Rust backend.
- Added EMA 20/50, RSI 14, MACD line, ATR 14, 20-day change and relative-volume calculations.
- Added filterable and sortable scanner results, caution flags and a transparent illustrative score.
- Added saved scan snapshots and JSON backup export.
- Expanded forex-session and major exchange-hour references.
- Matched the Adrian Vale website surfaces, typography and Classy blue / Royal gold themes.
- Added automated tests and Windows installer build checks.
- No brokerage connection, trade execution or legacy Python application code is included.
