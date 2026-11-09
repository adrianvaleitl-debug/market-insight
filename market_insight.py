import json
import math
import os
import sys
import threading
import webbrowser
import requests
import keyring
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import pandas as pd
import yfinance as yf

APP_NAME = "Market Insight"
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "settings.json"

DEFAULT_TICKERS = [
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "XLK", "XLF", "XLE", "XLV",
    "XLI", "XLY", "XLP", "XLU", "GLD", "TLT", "AAPL", "MSFT", "NVDA", "AMZN",
    "GOOGL", "META", "BRK-B", "JPM", "BAC", "WFC", "GS", "V", "MA", "COST",
    "WMT", "HD", "MCD", "KO", "PEP", "PG", "JNJ", "LLY", "UNH", "ABBV",
    "XOM", "CVX", "CAT", "GE", "AMD", "AVGO", "TSLA", "NFLX", "ORCL", "CRM"
]

DEFAULTS = {
    "appearance": "Dark",
    "auto_scan": True,
    "scan_interval": 5,
    "auto_open_tradingview": False,
    "confirm_tradingview": False,
    "threshold": 70,
    "watchlist": DEFAULT_TICKERS,
    "balance": 1000.0,
    "risk_percent": 1.0,
    "selected_platform": "",
    "custom_platform_url": "",
    "auto_open_platform": False,
}

def load_settings():
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        merged = DEFAULTS.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULTS.copy()

def save_settings(settings):
    CONFIG_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")

def safe_num(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except Exception:
        return default

def calculate_indicators(df):
    df = df.copy().dropna()
    if len(df) < 55:
        raise ValueError("Not enough price history")
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float)

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    tr = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    avg_vol = volume.rolling(20).mean()

    last = len(df) - 1
    price = safe_num(close.iloc[last])
    e20 = safe_num(ema20.iloc[last])
    e50 = safe_num(ema50.iloc[last])
    rsi_now = safe_num(rsi.iloc[last], 50)
    macd_now = safe_num(macd.iloc[last])
    atr_now = safe_num(atr.iloc[last])
    vol_ratio = safe_num(volume.iloc[last] / avg_vol.iloc[last]) if safe_num(avg_vol.iloc[last]) else 0
    day_change = ((price / safe_num(close.iloc[-2], price)) - 1) * 100 if len(close) > 1 else 0
    change20 = ((price / safe_num(close.iloc[-21], price)) - 1) * 100 if len(close) > 21 else 0

    score = 0
    score += 20 if price > e20 else 0
    score += 20 if e20 > e50 else 0
    score += 20 if 50 <= rsi_now <= 68 else (8 if 40 <= rsi_now < 50 else 0)
    score -= 10 if rsi_now > 75 else (5 if rsi_now < 30 else 0)
    score += 15 if macd_now > 0 else 0
    score += 15 if vol_ratio >= 1.5 else (7 if vol_ratio >= 1.1 else 0)
    score += 10 if change20 > 0 else (-5 if change20 < 0 else 0)
    score = max(0, min(100, int(score)))

    warnings = []
    if score < 40: warnings.append("Low score")
    if rsi_now > 75: warnings.append("Overbought RSI")
    if rsi_now < 30: warnings.append("Oversold RSI")
    if vol_ratio > 2.5: warnings.append("Unusual volume")
    if day_change <= -3: warnings.append("Sharp daily fall")
    if change20 <= -8: warnings.append("Weak 20-day trend")

    return {
        "price": price, "score": score, "rsi": rsi_now, "macd": macd_now,
        "atr": atr_now, "volume_ratio": vol_ratio, "day_change": day_change,
        "change20": change20, "ema20": e20, "ema50": e50,
        "warnings": warnings, "date": str(df.index[-1].date())
    }

def get_alpaca_credentials():
    try:
        return (keyring.get_password("Market Insight", "alpaca_api_key"),
                keyring.get_password("Market Insight", "alpaca_secret_key"))
    except Exception:
        return None, None


def get_alpaca_snapshot(symbol, api_key, secret_key):
    """Fetch an IEX latest-trade snapshot. Never silently substitutes delayed data."""
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/snapshot"
    response = requests.get(url, headers={
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }, params={"feed": "iex"}, timeout=15)
    if response.status_code in (401, 403):
        raise ValueError("Alpaca rejected the API keys. Check your Key ID and Secret Key.")
    if response.status_code == 404:
        raise ValueError("Alpaca returned no snapshot for this symbol.")
    response.raise_for_status()
    payload = response.json()
    trade = payload.get("latestTrade") or {}
    previous = payload.get("prevDailyBar") or {}
    live_price = safe_num(trade.get("p"))
    if live_price <= 0:
        raise ValueError("Alpaca did not return a latest IEX trade for this symbol.")
    previous_close = safe_num(previous.get("c"))
    day_change = ((live_price / previous_close) - 1) * 100 if previous_close > 0 else None
    return {"price": live_price, "day_change": day_change, "trade_time": trade.get("t", "Unknown"), "feed": "IEX"}


def scan_symbol(symbol, api_key, secret_key):
    if not api_key or not secret_key:
        raise ValueError("Add your Alpaca API Key ID and Secret Key in Settings → Live market data.")
    data = yf.download(symbol, period="6mo", interval="1d", auto_adjust=True, progress=False, threads=False)
    if data is None or data.empty:
        raise ValueError("No historical indicator data returned by Yahoo Finance.")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    indicators = calculate_indicators(data)
    live = get_alpaca_snapshot(symbol, api_key, secret_key)
    indicators["historical_price"] = indicators["price"]
    indicators["price"] = live["price"]
    if live["day_change"] is not None:
        indicators["day_change"] = live["day_change"]
    indicators["live_feed"] = live["feed"]
    indicators["trade_time"] = live["trade_time"]
    return indicators

class MarketInsightApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        ctk.set_appearance_mode(self.settings["appearance"].lower())
        ctk.set_default_color_theme("green")
        self.title(APP_NAME)
        self.geometry("1180x760")
        self.minsize(960, 640)
        self.configure(fg_color=("#F4F6F5", "#171B1A"))
        self.results = {}
        self.scanning = False
        self.after_id = None
        self._build_ui()
        self._refresh_watchlist_text()
        if self.settings.get("auto_scan"):
            self.after(900, self.start_scan)

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=205, corner_radius=0, fg_color=("#E9EFEC", "#202725"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="MARKET\nINSIGHT", font=ctk.CTkFont(size=23, weight="bold"),
                     text_color=("#263C34", "#D8E8E0"), justify="left").pack(anchor="w", padx=22, pady=(28, 30))
        self.nav_buttons = {}
        for label in ["Overview", "Watchlist", "Settings", "About"]:
            btn = ctk.CTkButton(self.sidebar, text=label, anchor="w", height=42, corner_radius=12,
                                fg_color="transparent", text_color=("#35443D", "#D8E3DE"),
                                hover_color=("#D7E5DD", "#303B36"),
                                command=lambda name=label: self.show_page(name))
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[label] = btn
        ctk.CTkLabel(self.sidebar, text="Live IEX prices when connected\n· Educational use only.",
                     font=ctk.CTkFont(size=11), text_color=("#75827B", "#87958E"),
                     justify="left").pack(side="bottom", anchor="w", padx=20, pady=20)

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=24, pady=22)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(header, text="Market overview", font=ctk.CTkFont(size=28, weight="bold"),
                                       text_color=("#26342D", "#E5EEE9"))
        self.page_title.grid(row=0, column=0, sticky="w")
        self.status = ctk.CTkLabel(header, text="Ready", corner_radius=10, padx=12, pady=7,
                                   fg_color=("#E1EEE6", "#273B31"), text_color=("#397653", "#A9D9B9"))
        self.status.grid(row=0, column=1, sticky="e")

        self.pages = {}
        for name in ["Overview", "Watchlist", "Settings", "About"]:
            frame = ctk.CTkScrollableFrame(self.main, corner_radius=18, fg_color=("#FFFFFF", "#202624"))
            frame.grid(row=1, column=0, sticky="nsew")
            self.pages[name] = frame
        self._build_overview()
        self._build_watchlist()
        self._build_settings()
        self._build_about()
        self.show_page("Overview")

    def card(self, parent, title, subtitle=None):
        frame = ctk.CTkFrame(parent, corner_radius=16, fg_color=("#F5F8F6", "#29312D"))
        frame.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=("#2B3B33", "#E2ECE6")).pack(anchor="w", padx=18, pady=(15, 2))
        if subtitle:
            ctk.CTkLabel(frame, text=subtitle, font=ctk.CTkFont(size=11),
                         text_color=("#718078", "#9BAAA2")).pack(anchor="w", padx=18, pady=(0, 8))
        return frame

    def _build_overview(self):
        page = self.pages["Overview"]
        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkButton(actions, text="Scan markets now", height=40, corner_radius=12,
                      command=self.start_scan).pack(side="left")
        ctk.CTkButton(actions, text="Open top result in TradingView", height=40, corner_radius=12,
                      fg_color=("#E8F0EB", "#35443C"), text_color=("#315B43", "#D6E8DC"),
                      command=self.open_top_result).pack(side="left", padx=8)
        self.scan_info = ctk.CTkLabel(actions, text="50 starter symbols", text_color=("#738078", "#9BAAA2"))
        self.scan_info.pack(side="right", padx=8)

        top = self.card(page, "Top watchlist result", "The highest scoring symbol from your latest scan")
        self.top_symbol = ctk.CTkLabel(top, text="No scan yet", font=ctk.CTkFont(size=30, weight="bold"))
        self.top_symbol.pack(anchor="w", padx=18, pady=(6, 0))
        self.top_details = ctk.CTkLabel(top, text="Connect Alpaca in Settings, then run a scan to view live IEX prices.",
                                        text_color=("#718078", "#A6B3AC"))
        self.top_details.pack(anchor="w", padx=18, pady=(2, 16))

        self.watch_card = self.card(page, "Watchlist snapshot", "A quick look at the strongest scan results")
        self.watch_table = ctk.CTkTextbox(self.watch_card, height=190, corner_radius=10,
                                          fg_color=("#FFFFFF", "#202624"), text_color=("#33433A", "#DCE8E1"))
        self.watch_table.pack(fill="x", padx=16, pady=(8, 16))
        self.watch_table.insert("1.0", "Run a scan to populate this list.")
        self.watch_table.configure(state="disabled")

        caution = self.card(page, "Caution list", "Symbols with two or more warning signs. This is not a sell instruction.")
        self.caution_text = ctk.CTkTextbox(caution, height=125, corner_radius=10,
                                           fg_color=("#FFFFFF", "#202624"), text_color=("#8B5555", "#E6A5A5"))
        self.caution_text.pack(fill="x", padx=16, pady=(8, 16))
        self.caution_text.insert("1.0", "No caution results yet.")
        self.caution_text.configure(state="disabled")

    def _build_watchlist(self):
        page = self.pages["Watchlist"]
        card = self.card(page, "Edit watchlist", "Enter ticker symbols separated by commas. Up to 100 symbols.")
        self.watch_input = ctk.CTkTextbox(card, height=120, corner_radius=10)
        self.watch_input.pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(card, text="Save watchlist", command=self.save_watchlist).pack(anchor="e", padx=16, pady=(0, 14))
        results = self.card(page, "Latest scan results")
        self.results_text = ctk.CTkTextbox(results, height=330, corner_radius=10,
                                           fg_color=("#FFFFFF", "#202624"), text_color=("#33433A", "#DCE8E1"))
        self.results_text.pack(fill="x", padx=16, pady=(8, 16))
        self.results_text.insert("1.0", "Scan results will appear here.")
        self.results_text.configure(state="disabled")

    def _build_settings(self):
        page = self.pages["Settings"]
        card = self.card(page, "Appearance", "Choose how the app looks.")
        self.appearance_menu = ctk.CTkOptionMenu(card, values=["System", "Dark", "Light"], command=self.change_appearance)
        self.appearance_menu.set(self.settings["appearance"])
        self.appearance_menu.pack(anchor="w", padx=18, pady=(8, 16))

        card = self.card(page, "Scanning", "Live latest-trade snapshots from Alpaca IEX; technical indicators use Yahoo Finance daily history.")
        self.auto_scan_var = ctk.BooleanVar(value=self.settings["auto_scan"])
        ctk.CTkCheckBox(card, text="Scan automatically", variable=self.auto_scan_var,
                        command=self.save_general_settings).pack(anchor="w", padx=18, pady=8)
        self.interval_menu = ctk.CTkOptionMenu(card, values=["5", "15", "30", "60"])
        self.interval_menu.set(str(self.settings["scan_interval"]))
        self.interval_menu.pack(anchor="w", padx=18, pady=(4, 16))

        self.auto_tv_var = ctk.BooleanVar(value=self.settings["auto_open_tradingview"])
        ctk.CTkCheckBox(card, text="Automatically open new top result in TradingView",
                        variable=self.auto_tv_var, command=self.save_general_settings).pack(anchor="w", padx=18, pady=8)
        self.confirm_tv_var = ctk.BooleanVar(value=self.settings["confirm_tradingview"])
        ctk.CTkCheckBox(card, text="Ask before opening TradingView",
                        variable=self.confirm_tv_var, command=self.save_general_settings).pack(anchor="w", padx=18, pady=8)
        self.threshold_menu = ctk.CTkOptionMenu(card, values=["60", "70", "80", "90"])
        self.threshold_menu.set(str(self.settings["threshold"]))
        self.threshold_menu.pack(anchor="w", padx=18, pady=(4, 16))
        ctk.CTkButton(card, text="Save scanning settings", command=self.save_general_settings).pack(anchor="e", padx=18, pady=(0, 14))

        card = self.card(page, "Live market data — Alpaca", "Enter your Alpaca API credentials. Keys are stored in Windows Credential Manager.")
        self.alpaca_key_entry = ctk.CTkEntry(card, placeholder_text="Alpaca API Key ID", show="•")
        self.alpaca_key_entry.pack(fill="x", padx=18, pady=(8, 6))
        self.alpaca_secret_entry = ctk.CTkEntry(card, placeholder_text="Alpaca Secret Key", show="•")
        self.alpaca_secret_entry.pack(fill="x", padx=18, pady=6)
        key_status = "Credentials are saved." if all(get_alpaca_credentials()) else "No Alpaca credentials saved yet."
        self.alpaca_status = ctk.CTkLabel(card, text=key_status, text_color=("#397653", "#A9D9B9"))
        self.alpaca_status.pack(anchor="w", padx=18, pady=(4, 4))
        alpaca_actions = ctk.CTkFrame(card, fg_color="transparent")
        alpaca_actions.pack(fill="x", padx=18, pady=(4, 8))
        ctk.CTkButton(alpaca_actions, text="Save Alpaca keys securely", command=self.save_alpaca_keys).pack(side="left")
        ctk.CTkButton(alpaca_actions, text="Remove saved keys", fg_color=("#E9E2E2", "#493333"),
                      text_color=("#8B4545", "#F0CACA"), command=self.remove_alpaca_keys).pack(side="left", padx=8)
        ctk.CTkLabel(card, text="Feed: IEX (not the full consolidated US market). Live prices require an active market session and available IEX trades. Historical indicators still come from Yahoo Finance. No delayed-price fallback is used if Alpaca fails.",
                     wraplength=760, justify="left", font=ctk.CTkFont(size=11),
                     text_color=("#8A6B42", "#D7B98B")).pack(anchor="w", padx=18, pady=(0, 14))

        card = self.card(page, "Position calculator", "Illustrative sizing using ATR. This does not place trades.")
        self.balance_entry = ctk.CTkEntry(card, placeholder_text="Account balance (USD)")
        self.balance_entry.insert(0, str(self.settings["balance"]))
        self.balance_entry.pack(fill="x", padx=18, pady=(8, 6))
        self.risk_entry = ctk.CTkEntry(card, placeholder_text="Risk per trade (%)")
        self.risk_entry.insert(0, str(self.settings["risk_percent"]))
        self.risk_entry.pack(fill="x", padx=18, pady=6)
        ctk.CTkButton(card, text="Save calculator settings", command=self.save_calculator_settings).pack(anchor="e", padx=18, pady=8)
        self.calc_output = ctk.CTkLabel(card, text="Scan a symbol, then select it in the results to view its example levels.",
                                        text_color=("#718078", "#9BAAA2"), justify="left")
        self.calc_output.pack(anchor="w", padx=18, pady=(0, 16))

    def _build_about(self):
        page = self.pages["About"]
        card = self.card(page, "About Market Insight")
        ctk.CTkLabel(card, text="A simple market research and watchlist tool.",
                     font=ctk.CTkFont(size=15), text_color=("#53635A", "#C5D3CB")).pack(anchor="w", padx=18, pady=(6, 8))
        ctk.CTkLabel(card, text="Latest prices use Alpaca IEX snapshots when credentials are connected. Historical technical indicators use Yahoo Finance daily history. IEX coverage is not the full consolidated US market; availability and timing can vary.",
                     wraplength=700, justify="left", text_color=("#718078", "#9BAAA2")).pack(anchor="w", padx=18, pady=5)
        ctk.CTkLabel(card, text="Educational information only. Scores and indicators are estimates, not financial advice. The app does not connect to a broker or execute trades.",
                     wraplength=700, justify="left", text_color=("#9B6868", "#E0A6A6")).pack(anchor="w", padx=18, pady=5)
        ctk.CTkLabel(card, text="Credits: Created by Adrian Vale",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=("#53635A", "#C5D3CB")).pack(anchor="w", padx=18, pady=(14, 18))

    def show_page(self, name):
        for frame in self.pages.values():
            frame.grid_remove()
        self.pages[name].grid()
        self.page_title.configure(text={"Overview":"Market overview","Watchlist":"Watchlist","Settings":"Settings","About":"About"}[name])
        for label, button in self.nav_buttons.items():
            button.configure(fg_color=("#D6E7DC", "#34443B") if label == name else "transparent")

    def _refresh_watchlist_text(self):
        if hasattr(self, "watch_input"):
            self.watch_input.delete("1.0", "end")
            self.watch_input.insert("1.0", ", ".join(self.settings["watchlist"]))

    def save_watchlist(self):
        symbols = [s.strip().upper() for s in self.watch_input.get("1.0", "end").replace("\n", ",").split(",") if s.strip()]
        symbols = list(dict.fromkeys(symbols))[:100]
        if not symbols:
            self.status.configure(text="Enter at least one symbol")
            return
        self.settings["watchlist"] = symbols
        save_settings(self.settings)
        self.scan_info.configure(text=f"{len(symbols)} symbols in watchlist")
        self.status.configure(text="Watchlist saved")

    def change_appearance(self, value):
        self.settings["appearance"] = value
        ctk.set_appearance_mode(value.lower())
        save_settings(self.settings)

    def save_general_settings(self):
        self.settings["auto_scan"] = bool(self.auto_scan_var.get())
        self.settings["scan_interval"] = int(self.interval_menu.get())
        self.settings["auto_open_tradingview"] = bool(self.auto_tv_var.get())
        self.settings["confirm_tradingview"] = bool(self.confirm_tv_var.get())
        self.settings["threshold"] = int(self.threshold_menu.get())
        save_settings(self.settings)
        self.status.configure(text="Settings saved")
        self.schedule_next_scan()

    def save_alpaca_keys(self):
        api_key = self.alpaca_key_entry.get().strip()
        secret_key = self.alpaca_secret_entry.get().strip()
        if not api_key or not secret_key:
            self.alpaca_status.configure(text="Enter both the API Key ID and Secret Key.")
            return
        try:
            keyring.set_password("Market Insight", "alpaca_api_key", api_key)
            keyring.set_password("Market Insight", "alpaca_secret_key", secret_key)
            self.alpaca_key_entry.delete(0, "end")
            self.alpaca_secret_entry.delete(0, "end")
            self.alpaca_status.configure(text="Alpaca credentials saved securely in Windows Credential Manager.")
            self.status.configure(text="Live data credentials saved")
        except Exception as exc:
            self.alpaca_status.configure(text=f"Could not save credentials securely: {exc}")

    def remove_alpaca_keys(self):
        for account in ("alpaca_api_key", "alpaca_secret_key"):
            try:
                keyring.delete_password("Market Insight", account)
            except Exception:
                pass
        self.alpaca_status.configure(text="Saved Alpaca credentials removed.")
        self.status.configure(text="Alpaca keys removed")

    def save_calculator_settings(self):
        balance = safe_num(self.balance_entry.get(), 1000)
        risk = safe_num(self.risk_entry.get(), 1)
        if balance <= 0 or not 0 < risk <= 5:
            self.status.configure(text="Use balance > 0 and risk up to 5%")
            return
        self.settings["balance"] = balance
        self.settings["risk_percent"] = risk
        save_settings(self.settings)
        self.status.configure(text="Calculator settings saved")

    def start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.status.configure(text="Scanning…")
        self.scan_info.configure(text="Downloading daily market data…")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        output = {}
        symbols = list(self.settings.get("watchlist", DEFAULT_TICKERS))
        api_key, secret_key = get_alpaca_credentials()
        for i, symbol in enumerate(symbols):
            try:
                output[symbol] = scan_symbol(symbol, api_key, secret_key)
            except Exception as exc:
                output[symbol] = {"error": str(exc)}
            self.after(0, lambda n=i+1, total=len(symbols): self.scan_info.configure(text=f"Scanned {n}/{total}"))
        self.after(0, lambda: self._finish_scan(output))

    def _finish_scan(self, output):
        self.results = output
        self.scanning = False
        valid = [(s, d) for s, d in output.items() if "error" not in d]
        valid.sort(key=lambda item: item[1]["score"], reverse=True)
        if valid:
            symbol, data = valid[0]
            self.top_symbol.configure(text=f"{symbol}  ·  {data['score']}/100")
            self.top_details.configure(text=f"${data['price']:.2f}   |   Day {data['day_change']:+.2f}%   |   RSI {data['rsi']:.1f}   |   Live IEX · {data['trade_time']}")
        else:
            self.top_symbol.configure(text="No results available")
            self.top_details.configure(text="Check your internet connection or ticker symbols.")
        lines = ["SYMBOL     PRICE       DAY       SCORE     RSI"]
        for symbol, d in valid[:12]:
            lines.append(f"{symbol:<10} ${d['price']:<10.2f} {d['day_change']:+.2f}%    {d['score']:>3}/100   {d['rsi']:.1f}")
        self._set_text(self.watch_table, "\n".join(lines) if lines else "No market data returned.")
        caution_lines = []
        for symbol, d in valid:
            if len(d["warnings"]) >= 2:
                caution_lines.append(f"{symbol}: {', '.join(d['warnings'])}")
        self._set_text(self.caution_text, "\n".join(caution_lines[:6]) if caution_lines else "No symbols currently meet the caution threshold.")
        detail_lines = ["SYMBOL | PRICE | DAY CHANGE | 20-DAY CHANGE | SCORE | RSI | VOLUME RATIO"]
        for symbol, d in valid:
            detail_lines.append(f"{symbol} | ${d['price']:.2f} | {d['day_change']:+.2f}% | {d['change20']:+.2f}% | {d['score']}/100 | {d['rsi']:.1f} | {d['volume_ratio']:.2f}x")
        errors = [f"{s}: {d['error']}" for s, d in output.items() if "error" in d]
        if errors:
            detail_lines.extend(["", "DATA ISSUES"] + errors[:12])
        self._set_text(self.results_text, "\n".join(detail_lines))
        self.status.configure(text=f"Scan complete · {len(valid)} symbols")
        self.scan_info.configure(text=f"Last scan: {datetime.now().strftime('%H:%M')}")
        if valid:
            self._update_calculator(valid[0][0], valid[0][1])
            if self.settings.get("auto_open_tradingview") and valid[0][1]["score"] >= self.settings.get("threshold", 70):
                self._open_tradingview(valid[0][0], ask=self.settings.get("confirm_tradingview", True))
        self.schedule_next_scan()

    def _set_text(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _update_calculator(self, symbol, data):
        price, atr = data["price"], data["atr"]
        if price <= 0 or atr <= 0:
            return
        stop_distance = 1.5 * atr
        stop = max(0, price - stop_distance)
        target = price + 2 * stop_distance
        balance = safe_num(self.settings["balance"], 1000)
        risk_pct = safe_num(self.settings["risk_percent"], 1)
        risk_cash = balance * risk_pct / 100
        shares = min(risk_cash / stop_distance, balance / price)
        self.calc_output.configure(text=f"{symbol} example levels\nStop loss: ${stop:.2f}  |  Take profit: ${target:.2f}\nApprox. shares: {math.floor(shares)}  |  Risk budget: ${risk_cash:.2f}\nUses 1.5 × ATR stop and 2:1 potential reward-to-risk.")

    def _open_tradingview(self, symbol, ask=True):
        if ask:
            from tkinter import messagebox
            if not messagebox.askyesno("Open TradingView", f"Open {symbol} in TradingView?"):
                return
        webbrowser.open(f"https://www.tradingview.com/chart/?symbol={symbol}")

    def open_top_result(self):
        valid = [(s, d) for s, d in self.results.items() if "error" not in d]
        if not valid:
            self.status.configure(text="Run a scan first")
            return
        symbol, _ = max(valid, key=lambda item: item[1]["score"])
        self._open_tradingview(symbol, ask=self.settings.get("confirm_tradingview", True))

    def schedule_next_scan(self):
        if self.after_id:
            try: self.after_cancel(self.after_id)
            except Exception: pass
            self.after_id = None
        if self.settings.get("auto_scan"):
            self.after_id = self.after(int(self.settings["scan_interval"]) * 60 * 1000, self.start_scan)

if __name__ == "__main__":
    app = MarketInsightApp()
    app.mainloop()
