# Market Insight

## What's New

### V1.5 — Research workspace upgrades

The V1.5 update adds five new research and organisation tools:

- **Watchlist folders:** group tickers into custom lists such as Tech, ETFs and Long-term without removing them from the main scan.
- **Scan history:** keep the latest 20 completed scan summaries and compare the strongest results from each run.
- **Ticker research notes:** save and reload personal notes against individual ticker symbols on your computer.
- **Custom scan presets:** save and reuse your watchlist, score threshold, sort order and result filter.
- **Daily market briefing:** review the latest scan leaders, advancing/declining breadth and caution flags in one summary.

Existing V1.4 tools remain included: scan snapshots, searchable and sortable results, filters, CSV export, live scan progress, five font families, optional bold typography and the Economic Calendar, Price Alerts and Trading Journal.

Follow Market Insight on both platforms: [YouTube @Adrianvaleitl](https://www.youtube.com/@Adrianvaleitl) · [TikTok @adrianvaleitl](https://www.tiktok.com/@adrianvaleitl).

[View all releases](https://github.com/adrianvaleitl-debug/market-insight/releases) · [Open the website](https://adrianvaleitl-debug.github.io/market-insight/)

---

A Windows desktop market scanner for watchlists, technical indicators, and market research using Alpaca IEX snapshots and Yahoo Finance historical data.

## Overview

Market Insight helps you review a selected list of stocks and ETFs from one desktop application.
It calculates technical indicators and assigns each scanned symbol an illustrative score from 0 to 100.
The app also highlights caution signals so that you can investigate unusual or weaker conditions.
It is a research aid, not an automated trading system.

## Features

- Watchlist folders for organising symbols into named groups.\n- Local scan history with up to 20 recent summaries.\n- Ticker-specific research notes saved in app settings.\n- Reusable scan presets for watchlists, score thresholds, sorting and filters.\n- Daily briefing with scan leaders, market breadth and caution flags.\n- Scan snapshot showing average score, strongest and weakest daily moves, and highest-volume result.
- Search scan results by ticker symbol or company name.
- Sort results by score, biggest daily gain, biggest daily loss, highest RSI, or highest volume.
- Filter results by all stocks, positive or negative daily move, score 70+, or caution warnings.
- Export scan results to CSV, including prices, changes, indicators, volume data, and warnings.
- Live scan progress: add each stock to the results list immediately after it has been checked.
- In-app What's New page with version-by-version release notes.
- Five selectable font families in Settings: Segoe UI, Arial, Verdana, Trebuchet MS, and Georgia.
- Optional bold typography setting to switch between bold and regular text throughout the app, including the sidebar and smaller labels.
- Market overview with the strongest result from the latest scan.
- Dedicated Market Hours section with UK-local forex sessions, session overlaps and major stock-exchange hours.
- Automatic GMT/BST and overseas daylight-saving time conversion for the market timetable.
- Educational reference windows for commonly active trading periods.
- Watchlist editor with support for up to 100 ticker symbols.
- 50 starter US stock and ETF symbols included.
- Technical indicators including EMA 20, EMA 50, RSI, MACD, and ATR.
- Volume comparison against a 20-day average.
- Daily and 20-day price-change calculations.
- An illustrative technical score and caution warnings.
- Alpaca IEX latest-trade snapshots when valid credentials are connected.
- Yahoo Finance daily historical prices for technical indicator calculations.
- Trading-platform preference for stock links: TradingView, MetaTrader 5, Interactive Brokers, Robinhood, eToro, or Other.
- Optional custom stock URL template for the Other platform choice, using `{symbol}`.
- Optional confirmation before opening a stock link.
- Dark, Light, and System appearance choices.
- Automatic scanning controls and configurable scan intervals.
- ATR-based position-sizing and example risk calculations.
- Secure storage of Alpaca credentials through Windows Credential Manager when supported by the system keyring.

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer is recommended.
- An internet connection.
- An Alpaca account and API credentials for Alpaca IEX snapshots.
- The Python packages listed in `requirements.txt`.

## Installation

1. Download the latest release ZIP and extract the **Market_Insight** folder.
2. Double-click **SETUP_AND_START.bat**. This is the only file you need to run for setup.
3. It installs the required packages and opens Market Insight without leaving a command window running. Opening `market_insight.py` directly runs in the current Python window; use `START_IN_DIAGNOSTIC_MODE.bat` to see startup errors. Normal setup and desktop shortcut launches remain windowless.

The first time the app opens, it asks whether you want a desktop shortcut. Your answer is remembered, so it will not ask again. You can turn the shortcut on or off later in **Settings → Desktop shortcut**.

Python 3 must be installed on the computer. If setup cannot find it, install Python from https://www.python.org/downloads/ and run the setup again.

If Windows displays a security prompt, check that you downloaded the ZIP from the official repository before choosing whether to continue.

## First-time setup

1. On first launch, enter your Alpaca API Key ID and Secret Key.
2. Use the Alpaca dashboard link shown in the app to create or find your API credentials.
3. Market Insight checks the credentials before allowing setup to continue.
4. After successful validation, choose the trading platform you use.
5. The main scanner opens after the setup steps are complete.

Your Alpaca credentials are stored using Windows Credential Manager via the Python `keyring` package. App preferences and diagnostic logs are stored in your Windows user AppData folder, separately from the program files. The app icon is loaded automatically when the Python file starts and is generated if it is missing. Do not share your API keys or include them in screenshots, support messages, or public posts.

## Market Hours

Open **Market Hours** in the left-hand navigation to view the Sydney, Tokyo, London and New York forex sessions, key session overlaps, and regular trading hours for the London, New York, Tokyo and Hong Kong stock exchanges. Times are converted to UK local time and refreshed using the relevant time-zone rules, including daylight-saving changes. The timetable shows standard weekday hours; exchange holidays, special sessions and early closes can differ. Suggested active windows are educational context, not trading signals or guarantees.

## Using the scanner

1. Open Overview and run a scan, or leave automatic scanning enabled.
2. Review the top watchlist result and the snapshot of stronger results.
3. Open Watchlist to add or remove ticker symbols; separate symbols with commas.
4. Review the latest scan results and any caution warnings.
5. Use the stock-opening action to open a symbol using your selected platform preference.
6. Open Settings to change appearance, scanning options, platform preference, or calculator inputs.

The selected platform affects the destination used by stock links. Some destinations may open a web page or search result rather than launching a native desktop trading application. For Other, enter a URL template containing `{symbol}` in Settings.

## Market data and limitations

Alpaca snapshots use the IEX feed. IEX is not the full consolidated US market, and a latest trade may not be available for every symbol at every moment.
The app does not silently replace a missing Alpaca snapshot with another live or delayed quote.
Technical indicators are calculated from historical daily data retrieved through Yahoo Finance.
Price availability, timestamps, market sessions, and third-party service behaviour can vary.
The technical score is a simple rule-based calculation; it is not a prediction or a guarantee of future performance.

## Privacy and security

Alpaca credentials are saved locally through the operating system's credential storage integration.
The application needs an internet connection to request market data and historical prices.
Never publish your API credentials or commit them to this GitHub repository.
You can remove saved Alpaca credentials from the Live market data section in Settings.

## Troubleshooting

- If credentials are rejected, check that both the Key ID and Secret Key were copied correctly.
- If a scan fails, check your internet connection and whether the data providers are responding.
- If a symbol has no available IEX snapshot, try again later or review another symbol.
- If the app closes unexpectedly, run `START_IN_DIAGNOSTIC_MODE.bat` from the extracted folder. It keeps the console open and displays startup errors. Logs are saved as `startup_error.log` in AppData, with a fallback beside the app.
- If setup cannot install a dependency, check that Python is installed and available to the setup script.
- Restart the app after changing system or Python installation settings.

## Disclaimer

Market Insight is provided for educational and informational purposes only.
It does not provide financial, investment, tax, or legal advice.
Scores, indicators, warnings, and calculator outputs are estimates for research and learning.
The application does not connect to a broker to place, manage, or execute trades.
You are responsible for your own research and decisions. Past market behaviour does not guarantee future results.

## Project links

- **Website:** https://adrianvaleitl-debug.github.io/market-insight/
- **Latest download:** https://github.com/adrianvaleitl-debug/market-insight/releases/latest
- **Source code:** https://github.com/adrianvaleitl-debug/market-insight
- **YouTube:** https://www.youtube.com/@Adrianvaleitl
- **TikTok:** https://www.tiktok.com/@adrianvaleitl


## Support Market Insight

Market Insight is free to download and use. If you find the project useful and would like to support its continued development, you can make an optional contribution through Ko-fi.

- **Support the project:** https://ko-fi.com/marketinsight
- Contributions are voluntary; using the application does not require a payment.
- Support helps with ongoing maintenance, improvements, and future development.

Thank you for checking out Market Insight and supporting independent development.

## Credits

Created by Adrian Vale.
