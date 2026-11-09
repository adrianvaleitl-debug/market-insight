import json
import math
import os
import sys
import subprocess
import threading
import traceback
import webbrowser
import requests
import keyring
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import pandas as pd
import yfinance as yf
import ctypes

APP_NAME = "Market Insight"
APP_DIR = Path(__file__).resolve().parent
APP_DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "Market Insight"
CONFIG_FILE = APP_DATA_DIR / "settings.json"

def write_diagnostic(details):
    """Persist startup and callback errors, with a fallback beside the app."""
    for path in (APP_DATA_DIR / "startup_error.log", APP_DIR / "startup_error.log"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as log:
                log.write("\n" + "=" * 72 + "\n")
                log.write(datetime.now().isoformat(timespec="seconds") + "\n")
                log.write(str(details) + "\n")
            return path
        except Exception:
            continue
    return None

def show_startup_error(details):
    path = write_diagnostic(details)
    message = "Market Insight couldn't start because something went wrong."
    if path:
        message += "\n\nA diagnostic report was saved to:\n" + str(path)
    else:
        message += "\n\nThe diagnostic report could not be saved."
    try:
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
    except Exception:
        print(message)
        print(details)

DEFAULT_TICKERS = [
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "XLK", "XLF", "XLE", "XLV",
    "XLI", "XLY", "XLP", "XLU", "GLD", "TLT", "AAPL", "MSFT", "NVDA", "AMZN",
    "GOOGL", "META", "BRK-B", "JPM", "BAC", "WFC", "GS", "V", "MA", "COST",
    "WMT", "HD", "MCD", "KO", "PEP", "PG", "JNJ", "LLY", "UNH", "ABBV",
    "XOM", "CVX", "CAT", "GE", "AMD", "AVGO", "TSLA", "NFLX", "ORCL", "CRM"
]

STOCK_NAMES = {
    "SPY":"SPDR S&P 500 ETF","QQQ":"Invesco QQQ Trust","DIA":"SPDR Dow Jones ETF","IWM":"iShares Russell 2000 ETF",
    "VTI":"Vanguard Total Stock Market ETF","VOO":"Vanguard S&P 500 ETF","XLK":"Technology Select Sector SPDR",
    "XLF":"Financial Select Sector SPDR","XLE":"Energy Select Sector SPDR","XLV":"Health Care Select Sector SPDR",
    "AAPL":"Apple Inc.","MSFT":"Microsoft Corporation","NVDA":"NVIDIA Corporation","AMZN":"Amazon.com, Inc.",
    "GOOGL":"Alphabet Inc.","META":"Meta Platforms, Inc.","BRK-B":"Berkshire Hathaway Inc.","JPM":"JPMorgan Chase & Co.",
    "BAC":"Bank of America","WFC":"Wells Fargo & Company","GS":"Goldman Sachs Group","V":"Visa Inc.",
    "MA":"Mastercard Incorporated","COST":"Costco Wholesale","WMT":"Walmart Inc.","HD":"The Home Depot",
    "MCD":"McDonald's Corporation","KO":"The Coca-Cola Company","PEP":"PepsiCo, Inc.","PG":"Procter & Gamble",
    "JNJ":"Johnson & Johnson","LLY":"Eli Lilly and Company","UNH":"UnitedHealth Group","ABBV":"AbbVie Inc.",
    "XOM":"Exxon Mobil Corporation","CVX":"Chevron Corporation","CAT":"Caterpillar Inc.","GE":"GE Aerospace",
    "AMD":"Advanced Micro Devices","AVGO":"Broadcom Inc.","TSLA":"Tesla, Inc.","NFLX":"Netflix, Inc.",
    "ORCL":"Oracle Corporation","CRM":"Salesforce, Inc."
}

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
    "shortcut_prompted": False,
    "create_desktop_shortcut": False,
}

def load_settings():
    data = {}
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        else:
            # Preserve preferences from older versions that stored settings beside the app.
            legacy_file = APP_DIR / "settings.json"
            if legacy_file.exists():
                data = json.loads(legacy_file.read_text(encoding="utf-8"))
    except Exception:
        write_diagnostic("Settings could not be loaded; defaults will be used.\n" + traceback.format_exc())
        data = {}
    merged = DEFAULTS.copy()
    if isinstance(data, dict):
        merged.update(data)
    return merged

def save_settings(settings):
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")

def ensure_app_icon():
    """Create the bundled-style Windows icon automatically when running the .py directly."""
    icon_path = APP_DIR / "market_insight.ico"
    if icon_path.exists():
        return icon_path
    try:
        from PIL import Image, ImageDraw
        size = 256
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        draw.rounded_rectangle((8, 8, 248, 248), radius=54, fill=(8, 20, 16, 255), outline=(40, 190, 118, 255), width=5)
        for x, top in [(54, 157), (91, 128), (128, 96), (165, 65)]:
            draw.rounded_rectangle((x, top, x + 24, 198), radius=5, fill=(40, 205, 130, 255))
        draw.line([(42, 151), (91, 118), (126, 135), (198, 59)], fill=(151, 255, 194, 255), width=13, joint="curve")
        draw.polygon([(198, 34), (221, 70), (181, 65)], fill=(151, 255, 194, 255))
        im.save(icon_path, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    except Exception:
        return None
    return icon_path

def safe_num(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except Exception:
        return default

def calculate_indicators(df):
    df = df.copy().dropna()
    if len(df) < 55:
        raise ValueError("There isn't enough past price data to analyse this stock.")
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
    if score < 40: warnings.append("Low market score")
    if rsi_now > 75: warnings.append("RSI is high (the stock may have risen too quickly)")
    if rsi_now < 30: warnings.append("RSI is low (the stock may have fallen too quickly)")
    if vol_ratio > 2.5: warnings.append("Unusually high trading volume")
    if day_change <= -3: warnings.append("Large price drop today")
    if change20 <= -8: warnings.append("Price has fallen over the past 20 trading days")

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
        raise ValueError("Alpaca couldn't verify these details. Check that your API Key ID and Secret Access Key are correct.")
    if response.status_code == 404:
        raise ValueError("Alpaca couldn't find live price data for this stock.")
    response.raise_for_status()
    payload = response.json()
    trade = payload.get("latestTrade") or {}
    previous = payload.get("prevDailyBar") or {}
    live_price = safe_num(trade.get("p"))
    if live_price <= 0:
        raise ValueError("There isn't a recent IEX trade available for this stock right now.")
    previous_close = safe_num(previous.get("c"))
    day_change = ((live_price / previous_close) - 1) * 100 if previous_close > 0 else None
    return {"price": live_price, "day_change": day_change, "trade_time": trade.get("t", "Unknown"), "feed": "IEX"}


def scan_symbol(symbol, api_key, secret_key):
    if not api_key or not secret_key:
        raise ValueError("Add your Alpaca API Key ID and Secret Access Key in Settings under Live market data.")
    data = yf.download(symbol, period="6mo", interval="1d", auto_adjust=True, progress=False, threads=False)
    if data is None or data.empty:
        raise ValueError("Yahoo Finance didn't provide enough past price data to analyse this stock.")
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
        ensure_app_icon()
        self.settings = load_settings()
        ctk.set_appearance_mode(self.settings["appearance"].lower())
        ctk.set_default_color_theme("green")
        self.title(APP_NAME)
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AdrianVale.MarketInsight")
        except Exception:
            pass
        icon_path = APP_DIR / "market_insight.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(default=str(icon_path))
            except Exception:
                pass
        self.geometry("1180x760")
        self.minsize(960, 640)
        self.configure(fg_color=("#F4F6F5", "#171B1A"))
        self.results = {}
        self.scanning = False
        self.after_id = None
        # Keep the root window mapped while onboarding dialogs are displayed.
        # Withdrawing the parent can also hide its CTkToplevel setup dialog on Windows.
        api_key, secret_key = get_alpaca_credentials()
        valid = self._validate_alpaca_credentials(api_key, secret_key)[0] if api_key and secret_key else False
        if valid and self.settings.get("selected_platform"):
            self._launch_main_ui()
        elif valid:
            self._show_platform_setup()
        else:
            self._show_alpaca_setup()

    def report_callback_exception(self, exc, value, tb):
        """Capture errors raised by Tkinter commands and scheduled callbacks."""
        details = "".join(traceback.format_exception(exc, value, tb))
        path = write_diagnostic("Tkinter callback error:\n" + details)
        try:
            from tkinter import messagebox
            message = "That action didn't work. Please try again."
            if path:
                message += "\n\nDetails saved to:\n" + str(path)
            messagebox.showerror(APP_NAME, message, parent=self)
        except Exception:
            print(details)

    def _fit_text_to_width(self, label, parent, horizontal_padding=36, minimum=150):
        """Wrap paragraph-style labels to the space actually available in their parent."""
        def update_wrap(_event=None):
            try:
                available = max(minimum, parent.winfo_width() - horizontal_padding)
                label.configure(wraplength=available)
            except Exception:
                pass
        parent.bind("<Configure>", update_wrap, add="+")
        label.after(100, update_wrap)

    def _validate_alpaca_credentials(self, api_key, secret_key):
        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
        endpoint = "https://data.alpaca.markets/v2/stocks/SPY/snapshot"
        try:
            response = requests.get(endpoint, headers=headers, params={"feed": "iex"}, timeout=12)
            if response.status_code == 200:
                return True, ""
            if response.status_code in (401, 403):
                return False, "Alpaca rejected these keys. Check the Key ID and Secret Access Key."
            return False, "Alpaca returned an error (HTTP {}). Please try again.".format(response.status_code)
        except requests.RequestException:
            return False, "Couldn't connect to Alpaca. Check your internet connection and try again."

    def _setup_window(self, title, subtitle):
        win = ctk.CTkToplevel(self)
        self.setup_window = win
        win.title("Welcome to Market Insight")
        icon_path = APP_DIR / "market_insight.ico"
        if icon_path.exists():
            try:
                win.iconbitmap(default=str(icon_path))
            except Exception:
                pass
        win.geometry("650x590")
        win.minsize(560, 520)
        win.configure(fg_color=("#F4F7F5", "#171D1A"))
        win.protocol("WM_DELETE_WINDOW", self.destroy)
        win.grab_set()
        panel = ctk.CTkFrame(win, corner_radius=24, fg_color=("#FFFFFF", "#222B26"))
        panel.pack(fill="both", expand=True, padx=22, pady=22)
        ctk.CTkLabel(panel, text="MARKET INSIGHT", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=30, pady=(25, 8))
        ctk.CTkLabel(panel, text=title, font=ctk.CTkFont(size=25, weight="bold"),
                     wraplength=540, justify="left").pack(anchor="w", fill="x", padx=30)
        setup_description = ctk.CTkLabel(panel, text=subtitle, font=ctk.CTkFont(size=11),
                                         justify="left")
        setup_description.pack(anchor="w", fill="x", padx=30, pady=(8, 18))
        self._fit_text_to_width(setup_description, panel, 60)
        return win, panel

    def _show_alpaca_setup(self):
        win, panel = self._setup_window("Connect your Alpaca account", "To get live market prices, connect your Alpaca account. Enter your API details below and we'll check that they work before continuing.")
        ctk.CTkLabel(panel, text="API Key ID").pack(anchor="w", padx=30, pady=(0, 5))
        self.setup_key_entry = ctk.CTkEntry(panel, height=44, placeholder_text="Paste your Alpaca API Key ID here")
        self.setup_key_entry.pack(fill="x", padx=30, pady=(0, 13))
        ctk.CTkLabel(panel, text="Secret Access Key").pack(anchor="w", padx=30, pady=(0, 5))
        self.setup_secret_entry = ctk.CTkEntry(panel, height=44, show="•", placeholder_text="Paste your Alpaca Secret Access Key")
        self.setup_secret_entry.pack(fill="x", padx=30)
        ctk.CTkButton(panel, text="Get your API keys from Alpaca ↗", fg_color="transparent",
                      text_color=("#367653", "#A9D9B9"),
                      command=lambda: webbrowser.open("https://app.alpaca.markets/")).pack(anchor="w", padx=25, pady=12)
        self.setup_status = ctk.CTkLabel(panel, text="Your keys are saved securely in Windows Credential Manager on this computer.",
                                         font=ctk.CTkFont(size=10), justify="left")
        self.setup_status.pack(anchor="w", fill="x", padx=30, pady=8)
        self._fit_text_to_width(self.setup_status, panel, 60)
        ctk.CTkButton(panel, text="Check keys and continue", height=45, command=self._validate_setup_keys).pack(fill="x", padx=30, pady=18)
        win.focus_force()

    def _validate_setup_keys(self):
        api_key = self.setup_key_entry.get().strip()
        secret_key = self.setup_secret_entry.get().strip()
        if not api_key or not secret_key:
            self.setup_status.configure(text="Enter both the API Key ID and Secret Access Key.")
            return
        self.setup_status.configure(text="Checking your details with Alpaca…")
        self.update_idletasks()
        valid, message = self._validate_alpaca_credentials(api_key, secret_key)
        if not valid:
            self.setup_status.configure(text=message)
            return
        try:
            keyring.set_password("Market Insight", "alpaca_api_key", api_key)
            keyring.set_password("Market Insight", "alpaca_secret_key", secret_key)
        except Exception as exc:
            self.setup_status.configure(text="We couldn't save your keys securely: {}".format(exc))
            return
        self.setup_window.grab_release()
        self.setup_window.destroy()
        self._show_platform_setup()

    def _show_platform_setup(self):
        win, panel = self._setup_window("Choose your trading platform", "Choose the platform you use. When you open a stock, Market Insight will take you to this platform.")
        self.setup_platform_var = ctk.StringVar(value=self.settings.get("selected_platform") or "TradingView")
        choices = [
            ("TradingView", "Charts and stock analysis"),
            ("MetaTrader 5", "Your trading platform for desktop"),
            ("Interactive Brokers", "Your trading platform and investing"),
            ("Robinhood", "Stock trading and investing"),
            ("eToro", "Investing in different types of assets"),
            ("Other", "Use your own platform link (you can add it in Settings)"),
        ]
        for name, detail in choices:
            row = ctk.CTkFrame(panel, corner_radius=12, fg_color=("#F3F7F4", "#2A342E"))
            row.pack(fill="x", padx=30, pady=3)
            ctk.CTkRadioButton(row, text=name, value=name, variable=self.setup_platform_var).pack(anchor="w", padx=14, pady=(7, 0))
            ctk.CTkLabel(row, text=detail, font=ctk.CTkFont(size=10)).pack(anchor="w", padx=39, pady=(0, 6))
        ctk.CTkButton(panel, text="Save choice and continue", height=44, command=self._finish_first_run).pack(fill="x", padx=30, pady=16)
        win.focus_force()

    def _finish_first_run(self):
        self.settings["selected_platform"] = self.setup_platform_var.get()
        save_settings(self.settings)
        self.setup_window.grab_release()
        self.setup_window.destroy()
        self._launch_main_ui()

    def _launch_main_ui(self):
        self.deiconify()
        self._build_ui()
        self._refresh_watchlist_text()
        self.after(700, self._maybe_prompt_shortcut)
        if self.settings.get("auto_scan"):
            self.after(900, self.start_scan)

    def _maybe_prompt_shortcut(self):
        if self.settings.get("shortcut_prompted"):
            return
        from tkinter import messagebox
        self.settings["shortcut_prompted"] = True
        wants_shortcut = messagebox.askyesno(
            "Desktop shortcut",
            "Would you like a Market Insight shortcut on your desktop?\n\nThis makes the app easier to open. You can change this later in Settings."
        )
        self.settings["create_desktop_shortcut"] = bool(wants_shortcut)
        save_settings(self.settings)
        # Remove a shortcut that may have been created automatically by an older release.
        if not wants_shortcut:
            self._apply_desktop_shortcut(False)
        elif not self._apply_desktop_shortcut(True, show_feedback=True):
            self.settings["create_desktop_shortcut"] = False
            save_settings(self.settings)

    def _apply_desktop_shortcut(self, enabled, show_feedback=False):
        script = APP_DIR / "Create_Desktop_Shortcut.ps1"
        if not script.exists():
            if show_feedback and hasattr(self, "status"):
                self.status.configure(text="Couldn't find the desktop shortcut tool.")
            return False
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
        if not enabled:
            command.append("-Remove")
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=20,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            success = result.returncode == 0
        except Exception:
            success = False
        if show_feedback and hasattr(self, "status"):
            self.status.configure(text="Desktop shortcut preference updated." if success else "Couldn't update the desktop shortcut. Please try again.")
        return success

    def save_shortcut_preference(self):
        enabled = bool(self.shortcut_var.get())
        if self._apply_desktop_shortcut(enabled, show_feedback=True):
            self.settings["create_desktop_shortcut"] = enabled
            save_settings(self.settings)
        else:
            self.shortcut_var.set(not enabled)

    def _platform_url(self, symbol):
        symbol = symbol.upper().strip()
        platform = self.settings.get("selected_platform", "")
        urls = {
            "TradingView": "https://www.tradingview.com/chart/?symbol=" + symbol,
            "Robinhood": "https://robinhood.com/stocks/" + symbol,
            "eToro": "https://www.etoro.com/markets/" + symbol.lower(),
            "Interactive Brokers": "https://www.google.com/search?q=" + symbol + "+stock+Interactive+Brokers",
            "MetaTrader 5": "https://www.google.com/search?q=" + symbol + "+stock+MetaTrader+5",
        }
        if platform == "Other":
            template = self.settings.get("custom_platform_url", "").strip()
            return template.replace("{symbol}", symbol) if "{symbol}" in template else None
        return urls.get(platform)

    def open_selected_platform(self, symbol, ask=True):
        url = self._platform_url(symbol)
        if not url:
            self.status.configure(text="To use your own platform, add a custom link in Settings. Include {symbol} where the stock ticker should go.")
            return
        if ask:
            from tkinter import messagebox
            if not messagebox.askyesno("Open stock on your platform", "Would you like to open {} on {}?".format(symbol, self.settings.get("selected_platform"))):
                return
        webbrowser.open(url)

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=205, corner_radius=0, fg_color=("#E9EFEC", "#202725"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="MARKET\nINSIGHT", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=("#263C34", "#D8E8E0"), justify="left").pack(anchor="w", padx=22, pady=(28, 30))
        self.nav_buttons = {}
        for label in ["Overview", "Watchlist", "Settings", "About"]:
            btn = ctk.CTkButton(self.sidebar, text=label, anchor="w", height=42, corner_radius=12,
                                fg_color="transparent", text_color=("#35443D", "#D8E3DE"),
                                hover_color=("#D7E5DD", "#303B36"),
                                command=lambda name=label: self.show_page(name))
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[label] = btn
        ctk.CTkLabel(self.sidebar, text="Live prices when connected\nFor research and learning only.",
                     font=ctk.CTkFont(size=10), text_color=("#75827B", "#87958E"),
                     justify="left").pack(side="bottom", anchor="w", padx=20, pady=20)

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=24, pady=22)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(header, text="Market overview", font=ctk.CTkFont(size=26, weight="bold"),
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

    def card(self, parent, title, subtitle=None, wraplength=None):
        frame = ctk.CTkFrame(parent, corner_radius=16, fg_color=("#F5F8F6", "#29312D"))
        frame.pack(fill="x", padx=14, pady=10)
        heading = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=16, weight="bold"),
                               text_color=("#2B3B33", "#E2ECE6"), justify="left")
        heading.pack(anchor="w", fill="x", padx=18, pady=(14, 3))
        self._fit_text_to_width(heading, frame, 40)
        if subtitle:
            description = ctk.CTkLabel(frame, text=subtitle, font=ctk.CTkFont(size=10),
                                       text_color=("#718078", "#9BAAA2"), justify="left")
            description.pack(anchor="w", fill="x", padx=18, pady=(0, 9))
            self._fit_text_to_width(description, frame, 40)
        return frame

    def _build_overview(self):
        page = self.pages["Overview"]
        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkButton(actions, text="Scan watchlist", height=40, corner_radius=12,
                      command=self.start_scan).pack(side="left")
        ctk.CTkButton(actions, text="Open highest-rated stock", height=40, corner_radius=12,
                      fg_color=("#E8F0EB", "#35443C"), text_color=("#315B43", "#D6E8DC"),
                      command=self.open_top_result).pack(side="left", padx=8)
        self.scan_info = ctk.CTkLabel(
            actions, text="50 stocks included",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#E7E9EC", "#E7E9EC"),
            fg_color=("#454A50", "#30343A"),
            corner_radius=18, padx=16, pady=9
        )
        self.scan_info.pack(side="right", padx=8)

        # Two-column overview: market results on the left, calculator always visible on the right.
        content = ctk.CTkFrame(page, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=4)
        left_column = ctk.CTkFrame(content, fg_color="transparent")
        left_column.pack(side="left", fill="both", expand=True)
        right_column = ctk.CTkFrame(content, width=320, fg_color="transparent")
        right_column.pack(side="right", fill="y", padx=(4, 10), pady=10)
        right_column.pack_propagate(False)

        top = self.card(left_column, "Highest market score", "The stock with the highest score in your latest scan")
        self.top_symbol = ctk.CTkLabel(top, text="No scan has been run yet",
                                       font=ctk.CTkFont(size=28, weight="bold"))
        self.top_symbol.pack(anchor="w", fill="x", padx=18, pady=(6, 0))
        self._fit_text_to_width(self.top_symbol, top, 40)
        self.top_details = ctk.CTkLabel(top, text="Connect Alpaca in Settings, then scan your watchlist to see available live prices.",
                                        font=ctk.CTkFont(size=10),
                                        text_color=("#718078", "#A6B3AC"), justify="left")
        self.top_details.pack(anchor="w", fill="x", padx=18, pady=(2, 16))
        self._fit_text_to_width(self.top_details, top, 40)

        self.watch_card = self.card(left_column, "Watchlist highlights", "The highest-scoring stocks from your latest scan")
        self.watch_table = ctk.CTkScrollableFrame(self.watch_card, height=260, corner_radius=12, fg_color=("#FFFFFF", "#202624"))
        self.watch_table.pack(fill="x", padx=16, pady=(8, 16))

        caution = self.card(left_column, "Stocks to review", "Stocks showing two or more warning signs. These are prompts to take a closer look, not instructions to buy or sell.")
        self.caution_text = ctk.CTkScrollableFrame(caution, height=170, corner_radius=12, fg_color=("#FFFFFF", "#202624"))
        self.caution_text.pack(fill="x", padx=16, pady=(8, 16))

        calculator = self.card(right_column, "Position size calculator",
                               "Estimate how many shares may fit your balance and risk limit. This is a guide only; it does not place trades.",
                               wraplength=270)
        ctk.CTkLabel(calculator, text="Account balance (USD)",
                     text_color=("#53635A", "#C5D3CB")).pack(anchor="w", padx=14, pady=(8, 3))
        self.balance_entry = ctk.CTkEntry(calculator, placeholder_text="e.g. 1000")
        self.balance_entry.insert(0, str(self.settings["balance"]))
        self.balance_entry.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(calculator, text="Risk per trade (%)",
                     text_color=("#53635A", "#C5D3CB")).pack(anchor="w", padx=14, pady=(2, 3))
        self.risk_entry = ctk.CTkEntry(calculator, placeholder_text="e.g. 1")
        self.risk_entry.insert(0, str(self.settings["risk_percent"]))
        self.risk_entry.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(calculator, text="Save calculator settings",
                      command=self.save_calculator_settings).pack(fill="x", padx=14, pady=(4, 10))
        self.calc_output = ctk.CTkLabel(
            calculator,
            text="Run a scan to see example position size and price levels for the highest-scoring stock.",
            font=ctk.CTkFont(size=10), text_color=("#718078", "#9BAAA2"), justify="left"
        )
        self.calc_output.pack(anchor="w", fill="x", padx=14, pady=(0, 16))
        self._fit_text_to_width(self.calc_output, calculator, 32)

    def _build_watchlist(self):
        page = self.pages["Watchlist"]
        card = self.card(page, "Your watchlist", "Add the stock ticker symbols you want to track. Separate each symbol with a comma. You can add up to 100.")
        self.watch_input = ctk.CTkTextbox(card, height=120, corner_radius=10)
        self.watch_input.pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(card, text="Save watchlist", command=self.save_watchlist).pack(anchor="e", padx=16, pady=(0, 14))
        results = self.card(page, "Results from your latest scan")
        self.results_text = ctk.CTkScrollableFrame(results, height=520, corner_radius=12, fg_color=("#FFFFFF", "#202624"))
        self.results_text.pack(fill="x", padx=16, pady=(8, 16))

    def _build_settings(self):
        page = self.pages["Settings"]
        card = self.card(page, "App appearance", "Choose Light, Dark or match your Windows setting.")
        self.appearance_menu = ctk.CTkOptionMenu(card, values=["System", "Dark", "Light"], command=self.change_appearance)
        self.appearance_menu.set(self.settings["appearance"])
        self.appearance_menu.pack(anchor="w", padx=18, pady=(8, 16))

        card = self.card(page, "Desktop shortcut", "Choose whether to keep a Market Insight icon on your desktop. You can change this whenever you like.")
        self.shortcut_var = ctk.BooleanVar(value=self.settings.get("create_desktop_shortcut", False))
        ctk.CTkCheckBox(card, text="Show a Market Insight shortcut on my desktop", variable=self.shortcut_var,
                        command=self.save_shortcut_preference).pack(anchor="w", padx=18, pady=(8, 14))

        card = self.card(page, "Automatic scanning", "Market Insight gets the latest available prices from Alpaca IEX. It uses Yahoo Finance past prices to calculate stock indicators.")
        self.auto_scan_var = ctk.BooleanVar(value=self.settings["auto_scan"])
        ctk.CTkCheckBox(card, text="Scan my watchlist automatically", variable=self.auto_scan_var,
                        command=self.save_general_settings).pack(anchor="w", padx=18, pady=8)
        self.interval_menu = ctk.CTkOptionMenu(card, values=["5", "15", "30", "60"])
        self.interval_menu.set(str(self.settings["scan_interval"]))
        self.interval_menu.pack(anchor="w", padx=18, pady=(4, 16))

        ctk.CTkLabel(card, text="Your trading platform", text_color=("#53635A", "#C5D3CB")).pack(anchor="w", padx=18, pady=(8, 4))
        self.platform_menu = ctk.CTkOptionMenu(card, values=["TradingView", "MetaTrader 5", "Interactive Brokers", "Robinhood", "eToro", "Other"], command=self.change_platform)
        self.platform_menu.set(self.settings.get("selected_platform") or "TradingView")
        self.platform_menu.pack(anchor="w", padx=18, pady=(0, 8))
        self.custom_platform_entry = ctk.CTkEntry(card, placeholder_text="Your platform's stock link (put {symbol} where the ticker goes)")
        self.custom_platform_entry.insert(0, self.settings.get("custom_platform_url", ""))
        self.custom_platform_entry.pack(fill="x", padx=18, pady=6)
        self.auto_platform_var = ctk.BooleanVar(value=self.settings.get("auto_open_platform", False))
        ctk.CTkCheckBox(card, text="Automatically open the highest-scoring stock on my platform",
                        variable=self.auto_platform_var, command=self.save_general_settings).pack(anchor="w", padx=18, pady=8)
        self.threshold_menu = ctk.CTkOptionMenu(card, values=["60", "70", "80", "90"])
        self.threshold_menu.set(str(self.settings["threshold"]))
        self.threshold_menu.pack(anchor="w", padx=18, pady=(4, 16))
        ctk.CTkButton(card, text="Save scan settings", command=self.save_general_settings).pack(anchor="e", padx=18, pady=(0, 14))

        card = self.card(page, "Live prices — Alpaca", "Add your Alpaca API Key ID and Secret Access Key to use live price data. Your keys are stored securely in Windows Credential Manager.")
        self.alpaca_key_entry = ctk.CTkEntry(card, placeholder_text="Alpaca API Key ID", show="•")
        self.alpaca_key_entry.pack(fill="x", padx=18, pady=(8, 6))
        self.alpaca_secret_entry = ctk.CTkEntry(card, placeholder_text="Alpaca Secret Access Key", show="•")
        self.alpaca_secret_entry.pack(fill="x", padx=18, pady=6)
        key_status = "Your Alpaca keys are saved securely." if all(get_alpaca_credentials()) else "No Alpaca keys have been saved yet."
        self.alpaca_status = ctk.CTkLabel(card, text=key_status, text_color=("#397653", "#A9D9B9"))
        self.alpaca_status.pack(anchor="w", padx=18, pady=(4, 4))
        alpaca_actions = ctk.CTkFrame(card, fg_color="transparent")
        alpaca_actions.pack(fill="x", padx=18, pady=(4, 8))
        ctk.CTkButton(alpaca_actions, text="Save Alpaca keys", command=self.save_alpaca_keys).pack(side="left")
        ctk.CTkButton(alpaca_actions, text="Remove saved keys", fg_color=("#E9E2E2", "#493333"),
                      text_color=("#8B4545", "#F0CACA"), command=self.remove_alpaca_keys).pack(side="left", padx=8)
        price_note = ctk.CTkLabel(card, text="Price data comes from IEX, which does not cover every US market trade. Live prices are available only when the market is open and an IEX trade is available. Past-price indicators come from Yahoo Finance. If Alpaca can't provide a live price, the app will show an error rather than silently using delayed data.",
                                  justify="left", font=ctk.CTkFont(size=10),
                                  text_color=("#8A6B42", "#D7B98B"))
        price_note.pack(anchor="w", fill="x", padx=18, pady=(0, 14))
        self._fit_text_to_width(price_note, card, 40)

    def _build_about(self):
        page = self.pages["About"]
        card = self.card(page, "About Market Insight")
        intro = ctk.CTkLabel(card, text="A straightforward tool for researching stocks and keeping track of the ones you're interested in.",
                             font=ctk.CTkFont(size=14, weight="bold"),
                             text_color=("#53635A", "#C5D3CB"), justify="left")
        intro.pack(anchor="w", fill="x", padx=18, pady=(6, 8))
        self._fit_text_to_width(intro, card, 40)
        data_note = ctk.CTkLabel(card, text="When connected, live prices come from Alpaca's IEX data feed. Stock indicators are calculated using past daily prices from Yahoo Finance. IEX does not include every US market trade, so some prices may not be available.",
                                 font=ctk.CTkFont(size=10), justify="left",
                                 text_color=("#718078", "#9BAAA2"))
        data_note.pack(anchor="w", fill="x", padx=18, pady=5)
        self._fit_text_to_width(data_note, card, 40)
        disclaimer = ctk.CTkLabel(card, text="For education and research only. Scores and indicators are estimates, not financial advice or a guarantee of future results. Market Insight does not connect to your broker and cannot place trades.",
                                  font=ctk.CTkFont(size=10), justify="left",
                                  text_color=("#9B6868", "#E0A6A6"))
        disclaimer.pack(anchor="w", fill="x", padx=18, pady=5)
        self._fit_text_to_width(disclaimer, card, 40)
        ctk.CTkLabel(card, text="Created by Adrian Vale",
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
            self.status.configure(text="Please add at least one stock ticker to your watchlist.")
            return
        self.settings["watchlist"] = symbols
        save_settings(self.settings)
        self.scan_info.configure(
            text=f"{len(symbols)} symbols in watchlist",
            fg_color=("#454A50", "#30343A"),
            text_color=("#E7E9EC", "#E7E9EC")
        )
        self.status.configure(text="Your watchlist has been saved.")

    def change_appearance(self, value):
        self.settings["appearance"] = value
        ctk.set_appearance_mode(value.lower())
        save_settings(self.settings)

    def change_platform(self, value):
        self.settings["selected_platform"] = value
        save_settings(self.settings)
        self.status.configure(text="Your platform is set to " + value)

    def save_general_settings(self):
        self.settings["auto_scan"] = bool(self.auto_scan_var.get())
        self.settings["scan_interval"] = int(self.interval_menu.get())
        self.settings["selected_platform"] = self.platform_menu.get()
        self.settings["custom_platform_url"] = self.custom_platform_entry.get().strip()
        self.settings["auto_open_platform"] = bool(self.auto_platform_var.get())
        self.settings["threshold"] = int(self.threshold_menu.get())
        save_settings(self.settings)
        self.status.configure(text="Your settings have been saved.")
        self.schedule_next_scan()

    def save_alpaca_keys(self):
        api_key = self.alpaca_key_entry.get().strip()
        secret_key = self.alpaca_secret_entry.get().strip()
        if not api_key or not secret_key:
            self.alpaca_status.configure(text="Enter both the API Key ID and Secret Access Key.")
            return
        try:
            keyring.set_password("Market Insight", "alpaca_api_key", api_key)
            keyring.set_password("Market Insight", "alpaca_secret_key", secret_key)
            self.alpaca_key_entry.delete(0, "end")
            self.alpaca_secret_entry.delete(0, "end")
            self.alpaca_status.configure(text="Your Alpaca keys have been saved securely in Windows Credential Manager.")
            self.status.configure(text="Your live price data keys have been saved.")
        except Exception as exc:
            self.alpaca_status.configure(text=f"Could not save credentials securely: {exc}")

    def remove_alpaca_keys(self):
        for account in ("alpaca_api_key", "alpaca_secret_key"):
            try:
                keyring.delete_password("Market Insight", account)
            except Exception:
                pass
        self.alpaca_status.configure(text="Your saved Alpaca keys have been removed.")
        self.status.configure(text="Your Alpaca keys have been removed.")

    def save_calculator_settings(self):
        balance = safe_num(self.balance_entry.get(), 1000)
        risk = safe_num(self.risk_entry.get(), 1)
        if balance <= 0 or not 0 < risk <= 5:
            self.status.configure(text="Enter an account balance above 0 and a risk amount between 0% and 5%.")
            return
        self.settings["balance"] = balance
        self.settings["risk_percent"] = risk
        save_settings(self.settings)
        valid = [(symbol, data) for symbol, data in self.results.items() if "error" not in data]
        if valid:
            best_symbol, best_data = max(valid, key=lambda item: item[1]["score"])
            self._update_calculator(best_symbol, best_data)
        self.status.configure(text="Your calculator settings have been saved.")

    def start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.status.configure(text="Automatic scanning…")
        self.scan_info.configure(
            text="Getting recent stock price data…",
            fg_color=("#454A50", "#30343A"),
            text_color=("#E7E9EC", "#E7E9EC")
        )
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

    def _render_stock_cards(self, parent, rows, limit=None, caution=False):
        for child in parent.winfo_children():
            child.destroy()
        rows = rows if limit is None else rows[:limit]
        if not rows:
            ctk.CTkLabel(parent, text="No stocks to show yet. Run a scan to see results here.", text_color=("#78857D", "#A2B0A7")).pack(anchor="w", padx=12, pady=14)
            return
        for symbol, data in rows:
            tile = ctk.CTkFrame(parent, corner_radius=14, fg_color=("#F5F8F6", "#29332E"))
            tile.pack(fill="x", padx=5, pady=5)
            head = ctk.CTkFrame(tile, fg_color="transparent")
            head.pack(fill="x", padx=13, pady=(9, 2))
            title_area = ctk.CTkFrame(head, fg_color="transparent")
            title_area.pack(side="left", fill="x", expand=True)
            company_name = ctk.CTkLabel(title_area, text=STOCK_NAMES.get(symbol, symbol),
                                        font=ctk.CTkFont(size=12, weight="bold"), justify="left")
            company_name.pack(anchor="w", fill="x")
            self._fit_text_to_width(company_name, title_area, 12)
            ctk.CTkLabel(title_area, text=symbol, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=("#718078", "#A2B0A8")).pack(anchor="w")
            if caution:
                warning_text = ctk.CTkLabel(tile, text=", ".join(data.get("warnings", [])) or "Needs a closer look",
                                            font=ctk.CTkFont(size=10), text_color=("#A45B5B", "#E4A4A4"),
                                            justify="left")
                warning_text.pack(anchor="w", fill="x", padx=13, pady=(2, 9))
                self._fit_text_to_width(warning_text, tile, 30)
            else:
                tone = ("#38845A", "#91D4A8") if data["day_change"] >= 0 else ("#B65D5D", "#E5A0A0")
                info = ctk.CTkFrame(tile, fg_color="transparent")
                info.pack(fill="x", padx=13, pady=(5, 10))
                ctk.CTkLabel(info, text="USD {:.2f}".format(data["price"]), font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
                ctk.CTkLabel(info, text="{:+.2f}%".format(data["day_change"]), font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=tone).pack(side="left", padx=(10, 0))
                ctk.CTkLabel(info, text="Score: {}/100 · RSI: {:.0f} · Vol: {:.1f}x".format(data["score"], data["rsi"], data["volume_ratio"]),
                             font=ctk.CTkFont(size=9, weight="bold"),
                             text_color=("#65746C", "#B5C2BA")).pack(side="left", padx=(10, 0))
                ctk.CTkButton(info, text="View on {} ↗".format(self.settings.get("selected_platform", "platform")),
                              width=145, height=28, corner_radius=9, font=ctk.CTkFont(size=10),
                              command=lambda sym=symbol: self.open_selected_platform(sym, ask=True)).pack(side="right")

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
            self.top_symbol.configure(text="No results to show")
            self.top_details.configure(text="Check your internet connection and make sure your watchlist contains valid stock tickers.")
        self._render_stock_cards(self.watch_table, valid, limit=12)
        caution_rows = [(symbol, data) for symbol, data in valid if len(data.get("warnings", [])) >= 2]
        self._render_stock_cards(self.caution_text, caution_rows[:8], caution=True)
        self._render_stock_cards(self.results_text, valid)
        errors = ["{}: {}".format(symbol, data["error"]) for symbol, data in output.items() if "error" in data]
        if errors:
            issue = ctk.CTkFrame(self.results_text, corner_radius=12, fg_color=("#F8EEEE", "#3B2D2D"))
            issue.pack(fill="x", padx=5, pady=6)
            ctk.CTkLabel(issue, text="Stocks we couldn't check", font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=("#A34D4D", "#E6A0A0")).pack(anchor="w", padx=12, pady=(8, 2))
            error_details = ctk.CTkLabel(issue, text="\\n".join(errors[:12]),
                                         font=ctk.CTkFont(size=10), justify="left",
                                         text_color=("#8B5555", "#E6A5A5"))
            error_details.pack(anchor="w", fill="x", padx=12, pady=(0, 10))
            self._fit_text_to_width(error_details, issue, 28)
        self.status.configure(text=f"Scan complete · {len(valid)} symbols")
        self.scan_info.configure(
            text=f"Last scan: {datetime.now().strftime('%H:%M')}",
            fg_color=("#454A50", "#30343A"),
            text_color=("#E7E9EC", "#E7E9EC")
        )
        if valid:
            self._update_calculator(valid[0][0], valid[0][1])
            if self.settings.get("auto_open_platform") and valid[0][1]["score"] >= self.settings.get("threshold", 70):
                self.open_selected_platform(valid[0][0], ask=False)
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
        self.calc_output.configure(text=f"{symbol} example levels\nStop loss: ${stop:.2f}  |  Take profit: ${target:.2f}\nApprox. shares: {math.floor(shares)}  |  Risk budget: ${risk_cash:.2f}\nBased on a stop distance of 1.5 × ATR and a potential 2:1 reward-to-risk ratio.")

    def open_top_result(self):
        valid = [(s, d) for s, d in self.results.items() if "error" not in d]
        if not valid:
            self.status.configure(text="Run a scan before opening a stock.")
            return
        symbol, _ = max(valid, key=lambda item: item[1]["score"])
        self.open_selected_platform(symbol, ask=True)

    def schedule_next_scan(self):
        if self.after_id:
            try: self.after_cancel(self.after_id)
            except Exception: pass
            self.after_id = None
        if self.settings.get("auto_scan"):
            self.after_id = self.after(int(self.settings["scan_interval"]) * 60 * 1000, self.start_scan)

if __name__ == "__main__":
    # Keep direct launches attached to their console. Normal setup and desktop
    # launches use the dedicated windowless VBS/pythonw launchers instead.
    try:
        app = MarketInsightApp()
        app.mainloop()
    except BaseException:
        details = traceback.format_exc()
        show_startup_error(details)
        if os.environ.get("MARKET_INSIGHT_DEBUG"):
            raise
