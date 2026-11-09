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
import winreg

APP_NAME = "Market Insight"
APP_VERSION = "1.2.21"
# v1.2.21 adds a Windows installer build; scanner features are unchanged.
GITHUB_RELEASES_API = "https://api.github.com/repos/adrianvaleitl-debug/market-insight/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/adrianvaleitl-debug/market-insight/releases/latest"
_SINGLE_INSTANCE_MUTEX = None


def acquire_single_instance():
    """Prevent a second Market Insight process from opening on Windows."""
    global _SINGLE_INSTANCE_MUTEX
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, "Local\\AdrianVale.MarketInsight.Singleton")
        if not handle:
            return True
        if kernel32.GetLastError() == 183:
            kernel32.CloseHandle(handle)
            ctypes.windll.user32.MessageBoxW(None, "Market Insight is already running.\n\nCheck your taskbar for the open window.", APP_NAME, 0x40)
            return False
        _SINGLE_INSTANCE_MUTEX = handle
        return True
    except Exception:
        return True


def set_windows_startup(enabled):
    """Add or remove the app from the current user's Windows startup registry key."""
    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            launcher = APP_DIR / "Start_Market_Insight.vbs"
            if not launcher.exists():
                raise FileNotFoundError("The startup launcher is missing from the Market Insight folder.")
            winreg.SetValueEx(key, "Market Insight", 0, winreg.REG_SZ, 'wscript.exe "' + str(launcher) + '"')
        else:
            try:
                winreg.DeleteValue(key, "Market Insight")
            except FileNotFoundError:
                pass


def version_tuple(value):
    parts = []
    for part in str(value).strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
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
    "startup_window_mode": "Maximised",
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
    "run_on_windows_startup": False,
    "check_for_updates": True,
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


def fetch_market_context():
    """Fetch a compact market pulse from Yahoo Finance daily data."""
    symbols = ["SPY", "QQQ", "DIA", "IWM", "^VIX"]
    try:
        frame = yf.download(tickers=" ".join(symbols), period="5d", interval="1d",
                            auto_adjust=True, progress=False, threads=True, group_by="ticker")
        context = {}
        if frame is None or frame.empty:
            return context
        for symbol in symbols:
            try:
                closes = frame[symbol]["Close"].dropna()
                if len(closes) >= 2:
                    previous, latest = float(closes.iloc[-2]), float(closes.iloc[-1])
                    context[symbol] = {"price": latest, "change": ((latest / previous) - 1) * 100 if previous else 0}
            except Exception:
                continue
        return context
    except Exception:
        return {}

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
        # Replace the stock bright-green accent with a restrained grey-sage palette.
        theme = ctk.ThemeManager.theme
        muted = {
            "CTkButton": {"fg_color": ["#747B70", "#596158"], "hover_color": ["#62695F", "#4B534A"], "text_color": ["#F5F4EF", "#F1F0EA"]},
            "CTkCheckBox": {"fg_color": ["#747B70", "#596158"], "hover_color": ["#62695F", "#4B534A"], "border_color": ["#92968B", "#858A80"], "checkmark_color": ["#F5F4EF", "#F1F0EA"]},
            "CTkSwitch": {"fg_color": ["#C8C9C0", "#454941"], "progress_color": ["#747B70", "#687164"], "button_color": ["#F5F4EF", "#D9D9D0"], "button_hover_color": ["#E1E1D9", "#C4C6BB"]},
            "CTkOptionMenu": {"fg_color": ["#747B70", "#596158"], "button_color": ["#62695F", "#4B534A"], "button_hover_color": ["#555D53", "#414940"], "text_color": ["#F5F4EF", "#F1F0EA"]},
            "CTkSlider": {"progress_color": ["#747B70", "#687164"], "button_color": ["#747B70", "#687164"], "button_hover_color": ["#62695F", "#4B534A"]},
            "CTkProgressBar": {"progress_color": ["#747B70", "#687164"]},
            "CTkRadioButton": {"fg_color": ["#747B70", "#687164"], "hover_color": ["#62695F", "#4B534A"]},
        }
        for widget_name, values in muted.items():
            if widget_name in theme:
                theme[widget_name].update(values)
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
        self.configure(fg_color=("#F1F0EC", "#20211F"))
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
        win.configure(fg_color=("#F1F0EC", "#20211F"))
        win.protocol("WM_DELETE_WINDOW", self.destroy)
        win.grab_set()
        panel = ctk.CTkFrame(win, corner_radius=24, fg_color=("#F8F7F3", "#30332F"))
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
                      text_color=("#647B68", "#B8C2B5"),
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
            row = ctk.CTkFrame(panel, corner_radius=12, fg_color=("#ECEBE5", "#30332F"))
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
        # Apply the selected window mode only after Tk has mapped the main window.
        self.after(250, self.apply_startup_window_mode)
        self.after(700, self._maybe_prompt_shortcut)
        if self.settings.get("check_for_updates", True):
            self.after(3000, self.check_for_updates)
        if self.settings.get("auto_scan"):
            self.after(900, self.start_scan)

    def apply_startup_window_mode(self):
        """Apply the saved display mode after the main window has been mapped."""
        mode = self.settings.get("startup_window_mode", "Maximised")
        try:
            self.attributes("-fullscreen", False)
            if mode == "Full screen":
                self.attributes("-fullscreen", True)
            elif mode == "Windowed":
                self.state("normal")
                self.geometry("1180x760")
            else:
                self.state("zoomed")
        except Exception:
            try:
                self.attributes("-fullscreen", False)
                self.state("normal" if mode == "Windowed" else "zoomed")
            except Exception:
                pass

    def change_startup_window_mode(self, value):
        """Save the display preference without calling the general settings form."""
        if value not in ("Maximised", "Full screen", "Windowed"):
            value = "Maximised"
        self.settings["startup_window_mode"] = value
        try:
            save_settings(self.settings)
            self.status.configure(
                text="Startup display mode saved. It will apply the next time you open Market Insight."
            )
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror(
                APP_NAME,
                "Couldn't save the display setting. Please try again.\\n\\n{}".format(exc),
                parent=self
            )

    def _toggle_fullscreen(self, event=None):
        try:
            if self.attributes("-fullscreen"):
                self.attributes("-fullscreen", False)
                self.state("zoomed")
            else:
                self.attributes("-fullscreen", True)
        except Exception:
            try:
                self.attributes("-fullscreen", False)
                self.state("zoomed")
            except Exception:
                pass
        return "break"

    def _exit_fullscreen(self, event=None):
        try:
            if self.attributes("-fullscreen"):
                self.attributes("-fullscreen", False)
                self.state("zoomed")
        except Exception:
            pass
        return "break"

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

    def create_desktop_shortcut(self):
        if self._apply_desktop_shortcut(True, show_feedback=True):
            self.settings["create_desktop_shortcut"] = True
            save_settings(self.settings)

    def remove_desktop_shortcut(self):
        if self._apply_desktop_shortcut(False, show_feedback=True):
            self.settings["create_desktop_shortcut"] = False
            save_settings(self.settings)

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

        self.sidebar = ctk.CTkFrame(self, width=205, corner_radius=0, fg_color=("#E8E7E1", "#252724"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="MARKET\nINSIGHT", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=("#3C453F", "#D4D8D2"), justify="left").pack(anchor="w", padx=22, pady=(28, 30))
        self.nav_buttons = {}
        for label in ["Overview", "Watchlist", "Settings", "About"]:
            btn = ctk.CTkButton(self.sidebar, text=label, anchor="w", height=42, corner_radius=12,
                                fg_color="transparent", text_color=("#4A514B", "#D8E3DE"),
                                hover_color=("#D8DAD4", "#303B36"),
                                command=lambda name=label: self.show_page(name))
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[label] = btn
        side_info = ctk.CTkScrollableFrame(
            self.sidebar, width=174, corner_radius=16,
            fg_color=("#E1E0D9", "#2B2D29"),
            scrollbar_button_color=("#B9BDB4", "#555A53")
        )
        side_info.pack(fill="both", expand=True, padx=10, pady=(18, 10))
        ctk.CTkLabel(side_info, text="ACCOUNT CONNECTION",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=("#777D75", "#AEB1A8")).pack(anchor="w", padx=8, pady=(10, 4))
        saved_key, saved_secret = get_alpaca_credentials()
        connected = bool(saved_key and saved_secret)
        ctk.CTkLabel(side_info, text="●  Alpaca connected" if connected else "○  Alpaca not connected",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=("#647B68", "#B4C4B1") if connected else ("#947B75", "#C5AAA4"),
                     justify="left").pack(anchor="w", padx=8, pady=3)
        key_hint = ("Key ID: ••••" + saved_key[-4:]) if connected else "API keys not saved"
        ctk.CTkLabel(side_info, text=key_hint, font=ctk.CTkFont(size=9),
                     text_color=("#777D75", "#A7AAA1")).pack(anchor="w", padx=8, pady=(0, 10))
        ctk.CTkLabel(side_info, text="YOUR TRADING PLATFORM",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=("#777D75", "#AEB1A8")).pack(anchor="w", padx=8, pady=(8, 4))
        ctk.CTkLabel(side_info, text=self.settings.get("selected_platform") or "Not selected",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=("#4A514B", "#D8DDD7")).pack(anchor="w", padx=8, pady=(0, 10))
        ctk.CTkLabel(side_info, text="QUICK LINKS",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=("#777D75", "#AEB1A8")).pack(anchor="w", padx=8, pady=(8, 4))
        for link_name, link_url in [
            ("Alpaca dashboard ↗", "https://app.alpaca.markets/"),
            ("TradingView ↗", "https://www.tradingview.com/"),
            ("Yahoo Finance ↗", "https://finance.yahoo.com/"),
            ("Alpaca market data ↗", "https://docs.alpaca.markets/docs/about-market-data-api"),
        ]:
            ctk.CTkButton(side_info, text=link_name, anchor="w", height=30,
                          corner_radius=12, fg_color="transparent",
                          text_color=("#58645B", "#C0C5BC"),
                          hover_color=("#D1D2C9", "#3A3D37"),
                          font=ctk.CTkFont(size=9),
                          command=lambda url=link_url: webbrowser.open(url)
                          ).pack(fill="x", padx=4, pady=2)
        ctk.CTkLabel(self.sidebar, text="Market Insight  •  Research only  •  Adrian Vale",
                     font=ctk.CTkFont(size=9), text_color=("#75827B", "#87958E"),
                     justify="left").pack(side="bottom", anchor="w", padx=14, pady=10)

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
        self.status = ctk.CTkLabel(header, text="Ready", corner_radius=16, padx=14, pady=8,
                                   fg_color=("#E1E4DC", "#353B35"), text_color=("#647B68", "#B8C2B5"))
        self.status.grid(row=0, column=1, sticky="e")

        self.pages = {}
        for name in ["Overview", "Watchlist", "Settings", "About"]:
            frame = ctk.CTkScrollableFrame(self.main, corner_radius=20, fg_color=("#F8F7F3", "#292B28"))
            frame.grid(row=1, column=0, sticky="nsew")
            self.pages[name] = frame
        self._build_overview()
        self._build_watchlist()
        self._build_settings()
        self._build_about()
        self.show_page("Overview")
        # Global bindings work even when a child control has keyboard focus.
        self.bind_all("<F11>", self._toggle_fullscreen)
        self.bind_all("<Escape>", self._exit_fullscreen)

    def card(self, parent, title, subtitle=None, wraplength=None):
        frame = ctk.CTkFrame(parent, corner_radius=22, fg_color=("#EFEEE8", "#30332F"))
        frame.pack(fill="x", padx=14, pady=10)
        heading = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=16, weight="bold"),
                               text_color=("#414841", "#D8DDD7"), justify="left")
        heading.pack(anchor="w", fill="x", padx=18, pady=(14, 3))
        self._fit_text_to_width(heading, frame, 40)
        if subtitle:
            description = ctk.CTkLabel(frame, text=subtitle, font=ctk.CTkFont(size=10),
                                       text_color=("#777D75", "#A7AAA1"), justify="left")
            description.pack(anchor="w", fill="x", padx=18, pady=(0, 9))
            self._fit_text_to_width(description, frame, 40)
        return frame

    def _build_overview(self):
        page = self.pages["Overview"]
        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkButton(actions, text="Scan watchlist", height=42, corner_radius=16,
                      command=self.start_scan).pack(side="left")
        ctk.CTkButton(actions, text="Open highest-rated stock", height=40, corner_radius=12,
                      fg_color=("#E4E4DC", "#35443C"), text_color=("#586D5C", "#D6E8DC"),
                      command=self.open_top_result).pack(side="left", padx=8)
        self.scan_info = ctk.CTkLabel(
            actions, text="50 stocks included",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#E5E4DE", "#E5E4DE"),
            fg_color=("#555A55", "#3B3E3A"),
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
                                        text_color=("#777D75", "#A6B3AC"), justify="left")
        self.top_details.pack(anchor="w", fill="x", padx=18, pady=(2, 16))
        self._fit_text_to_width(self.top_details, top, 40)

        self.watch_card = self.card(left_column, "Watchlist highlights", "The highest-scoring stocks from your latest scan")
        self.watch_table = ctk.CTkScrollableFrame(self.watch_card, height=260, corner_radius=12, fg_color=("#F8F7F3", "#292B28"))
        self.watch_table.pack(fill="x", padx=16, pady=(8, 16))

        caution = self.card(left_column, "Stocks to review", "Stocks showing two or more warning signs. These are prompts to take a closer look, not instructions to buy or sell.")
        self.caution_text = ctk.CTkScrollableFrame(caution, height=170, corner_radius=12, fg_color=("#F8F7F3", "#292B28"))
        self.caution_text.pack(fill="x", padx=16, pady=(8, 16))

        pulse = self.card(right_column, "Market pulse", "Daily market direction from Yahoo Finance. Updates when you scan.")
        self.market_pulse_labels = {}
        for symbol, name in [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("DIA", "Dow Jones"), ("IWM", "Russell 2000"), ("^VIX", "Volatility (VIX)")]:
            line = ctk.CTkFrame(pulse, fg_color="transparent")
            line.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(line, text=name, font=ctk.CTkFont(size=10), text_color=("#646D64", "#B8BDB4")).pack(side="left")
            value = ctk.CTkLabel(line, text="Waiting for scan", font=ctk.CTkFont(size=10, weight="bold"), text_color=("#646D64", "#C0C5BC"))
            value.pack(side="right")
            self.market_pulse_labels[symbol] = value
        self.market_breadth = ctk.CTkLabel(pulse, text="Watchlist breadth: waiting for scan", font=ctk.CTkFont(size=10, weight="bold"), text_color=("#646D64", "#C0C5BC"), justify="left")
        self.market_breadth.pack(anchor="w", padx=14, pady=(8, 12))
        checklist = self.card(right_column, "Before you trade", "A quick discipline check")
        checklist_items = ["Is there a clear reason for this trade?", "Have I checked the wider market trend?", "Is my stop level defined before entry?", "Does the position fit my risk limit?", "Is the potential reward worth the risk?", "Am I avoiding an emotional decision?"]
        for item in checklist_items:
            ctk.CTkLabel(checklist, text="•  " + item, font=ctk.CTkFont(size=9), text_color=("#646D64", "#B8BDB4"), justify="left", wraplength=260).pack(anchor="w", padx=14, pady=3)
        calculator = self.card(right_column, "Position size calculator",
                               "Estimate how many shares may fit your balance and risk limit. This is a guide only; it does not place trades.",
                               wraplength=270)
        ctk.CTkLabel(calculator, text="Account balance (USD)",
                     text_color=("#646D64", "#C0C5BC")).pack(anchor="w", padx=14, pady=(8, 3))
        self.balance_entry = ctk.CTkEntry(calculator, placeholder_text="e.g. 1000")
        self.balance_entry.insert(0, str(self.settings["balance"]))
        self.balance_entry.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(calculator, text="Risk per trade (%)",
                     text_color=("#646D64", "#C0C5BC")).pack(anchor="w", padx=14, pady=(2, 3))
        self.risk_entry = ctk.CTkEntry(calculator, placeholder_text="e.g. 1")
        self.risk_entry.insert(0, str(self.settings["risk_percent"]))
        self.risk_entry.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(calculator, text="Save calculator settings",
                      command=self.save_calculator_settings).pack(fill="x", padx=14, pady=(4, 10))
        self.calc_output = ctk.CTkLabel(
            calculator,
            text="Run a scan to see example position size and price levels for the highest-scoring stock.",
            font=ctk.CTkFont(size=10), text_color=("#777D75", "#A7AAA1"), justify="left"
        )
        self.calc_output.pack(anchor="w", fill="x", padx=14, pady=(0, 16))
        self._fit_text_to_width(self.calc_output, calculator, 32)

        footer = ctk.CTkFrame(page, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(2, 10))
        ctk.CTkLabel(
            footer, text="ADRIAN VALE  ·  MARKET INSIGHT",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("#646D64", "#C0C5BC")
        ).pack(side="left")
        ctk.CTkButton(
            footer, text="@adrianvaleitl  ↗", width=125, height=26,
            corner_radius=12, fg_color="transparent",
            text_color=("#647B68", "#B8C2B5"),
            hover_color=("#E4E4DC", "#35443C"),
            command=lambda: webbrowser.open("https://www.tiktok.com/@adrianvaleitl")
        ).pack(side="right")

    def _build_watchlist(self):
        page = self.pages["Watchlist"]
        card = self.card(page, "Your watchlist", "Add the stock ticker symbols you want to track. Separate each symbol with a comma. You can add up to 100.")
        self.watch_input = ctk.CTkTextbox(card, height=120, corner_radius=10)
        self.watch_input.pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(card, text="Save watchlist", command=self.save_watchlist).pack(anchor="e", padx=16, pady=(0, 14))
        results = self.card(page, "Results from your latest scan")
        self.results_text = ctk.CTkScrollableFrame(results, height=520, corner_radius=12, fg_color=("#F8F7F3", "#292B28"))
        self.results_text.pack(fill="x", padx=16, pady=(8, 16))

    def _build_settings(self):
        page = self.pages["Settings"]

        # Keep the everyday controls together in one clear preferences section.
        preferences = self.card(
            page, "Preferences and display",
            "Choose how Market Insight looks, opens and keeps your watchlist up to date."
        )
        ctk.CTkLabel(preferences, text="Appearance",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("#555D54", "#C0C5BC")).pack(anchor="w", padx=18, pady=(10, 3))
        self.appearance_menu = ctk.CTkOptionMenu(
            preferences, values=["System", "Dark", "Light"], command=self.change_appearance
        )
        self.appearance_menu.set(self.settings["appearance"])
        self.appearance_menu.pack(anchor="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(preferences, text="How the program opens",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("#555D54", "#C0C5BC")).pack(anchor="w", padx=18, pady=(4, 3))
        self.startup_mode_menu = ctk.CTkOptionMenu(
            preferences, values=["Maximised", "Full screen", "Windowed"],
            command=self.change_startup_window_mode
        )
        self.startup_mode_menu.set(self.settings.get("startup_window_mode", "Maximised"))
        self.startup_mode_menu.pack(anchor="w", padx=18, pady=(0, 5))
        mode_note = ctk.CTkLabel(
            preferences,
            text="Maximised fills the screen but keeps the Windows title bar and taskbar. Full screen hides them. Press F11 or Escape to leave full screen.",
            font=ctk.CTkFont(size=10), justify="left", anchor="w",
            text_color=("#777D75", "#A7AAA1")
        )
        mode_note.pack(fill="x", padx=18, pady=(0, 12))
        self._fit_text_to_width(mode_note, preferences, 40)

        self.run_startup_var = ctk.BooleanVar(value=self.settings.get("run_on_windows_startup", False))
        ctk.CTkCheckBox(
            preferences, text="Open Market Insight when Windows starts",
            variable=self.run_startup_var, command=self.change_windows_startup
        ).pack(anchor="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(
            preferences, text="Desktop shortcut",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#555D54", "#C0C5BC")
        ).pack(anchor="w", padx=18, pady=(8, 3))
        shortcut_actions = ctk.CTkFrame(preferences, fg_color="transparent")
        shortcut_actions.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkButton(
            shortcut_actions, text="Create desktop shortcut",
            command=self.create_desktop_shortcut
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            shortcut_actions, text="Remove desktop shortcut",
            fg_color=("#E8E2DE", "#493B38"),
            text_color=("#96716B", "#D8C1BA"),
            command=self.remove_desktop_shortcut
        ).pack(side="left")

        self.auto_scan_var = ctk.BooleanVar(value=self.settings["auto_scan"])
        ctk.CTkCheckBox(
            preferences, text="Scan my watchlist automatically",
            variable=self.auto_scan_var, command=self.save_general_settings
        ).pack(anchor="w", padx=18, pady=(4, 7))
        ctk.CTkLabel(preferences, text="Automatic scan interval (minutes)",
                     font=ctk.CTkFont(size=10),
                     text_color=("#777D75", "#A7AAA1")).pack(anchor="w", padx=18, pady=(0, 3))
        self.interval_menu = ctk.CTkOptionMenu(preferences, values=["5", "15", "30", "60"])
        self.interval_menu.set(str(self.settings["scan_interval"]))
        self.interval_menu.pack(anchor="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(preferences, text="Your trading platform",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("#555D54", "#C0C5BC")).pack(anchor="w", padx=18, pady=(4, 3))
        self.platform_menu = ctk.CTkOptionMenu(
            preferences, values=["TradingView", "MetaTrader 5", "Interactive Brokers", "Robinhood", "eToro", "Other"],
            command=self.change_platform
        )
        self.platform_menu.set(self.settings.get("selected_platform") or "TradingView")
        self.platform_menu.pack(anchor="w", padx=18, pady=(0, 7))
        self.custom_platform_entry = ctk.CTkEntry(
            preferences, placeholder_text="Your platform's stock link (put {symbol} where the ticker goes)"
        )
        self.custom_platform_entry.insert(0, self.settings.get("custom_platform_url", ""))
        self.custom_platform_entry.pack(fill="x", padx=18, pady=6)

        self.auto_platform_var = ctk.BooleanVar(value=self.settings.get("auto_open_platform", False))
        ctk.CTkCheckBox(
            preferences, text="Automatically open the highest-scoring stock on my platform",
            variable=self.auto_platform_var, command=self.save_general_settings
        ).pack(anchor="w", padx=18, pady=(8, 7))
        ctk.CTkLabel(preferences, text="Minimum score for automatic opening",
                     font=ctk.CTkFont(size=10),
                     text_color=("#777D75", "#A7AAA1")).pack(anchor="w", padx=18, pady=(0, 3))
        self.threshold_menu = ctk.CTkOptionMenu(preferences, values=["60", "70", "80", "90"])
        self.threshold_menu.set(str(self.settings["threshold"]))
        self.threshold_menu.pack(anchor="w", padx=18, pady=(0, 10))
        ctk.CTkButton(
            preferences, text="Save preferences", command=self.save_general_settings
        ).pack(anchor="e", padx=18, pady=(4, 16))

        updates = self.card(
            page, "Updates",
            "Check GitHub for a newer version and download the official release when one is available."
        )
        self.update_status = ctk.CTkLabel(
            updates, text="Current version: v{}".format(APP_VERSION),
            font=ctk.CTkFont(size=10), text_color=("#777D75", "#A7AAA1"), justify="left"
        )
        self.update_status.pack(anchor="w", padx=18, pady=(8, 5))
        self.auto_update_check_var = ctk.BooleanVar(value=self.settings.get("check_for_updates", True))
        ctk.CTkCheckBox(
            updates, text="Check for updates automatically when the app opens",
            variable=self.auto_update_check_var, command=self.change_update_check_preference
        ).pack(anchor="w", padx=18, pady=4)
        ctk.CTkButton(
            updates, text="Check for updates now", command=self.check_for_updates
        ).pack(anchor="w", padx=18, pady=(6, 14))

        # Connection credentials stay together in one separate section.
        connection = self.card(
            page, "Live market data connection",
            "Connect Alpaca for the latest available IEX prices. Your API details are stored securely in Windows Credential Manager."
        )
        self.alpaca_key_entry = ctk.CTkEntry(connection, placeholder_text="Alpaca API Key ID", show="•")
        self.alpaca_key_entry.pack(fill="x", padx=18, pady=(8, 6))
        self.alpaca_secret_entry = ctk.CTkEntry(connection, placeholder_text="Alpaca Secret Access Key", show="•")
        self.alpaca_secret_entry.pack(fill="x", padx=18, pady=6)
        key_status = "Your Alpaca keys are saved securely." if all(get_alpaca_credentials()) else "No Alpaca keys have been saved yet."
        self.alpaca_status = ctk.CTkLabel(
            connection, text=key_status, text_color=("#747B70", "#AEB3A8")
        )
        self.alpaca_status.pack(anchor="w", padx=18, pady=(4, 4))
        alpaca_actions = ctk.CTkFrame(connection, fg_color="transparent")
        alpaca_actions.pack(fill="x", padx=18, pady=(4, 8))
        ctk.CTkButton(alpaca_actions, text="Save Alpaca keys", command=self.save_alpaca_keys).pack(side="left")
        ctk.CTkButton(
            alpaca_actions, text="Remove saved keys",
            fg_color=("#E8E2DE", "#493B38"), text_color=("#96716B", "#D8C1BA"),
            command=self.remove_alpaca_keys
        ).pack(side="left", padx=8)
        price_note = ctk.CTkLabel(
            connection,
            text="Price data comes from IEX, which does not cover every US market trade. Live prices are available only when the market is open and an IEX trade is available. Past-price indicators come from Yahoo Finance. If Alpaca can't provide a live price, the app will show an error rather than silently using delayed data.",
            justify="left", font=ctk.CTkFont(size=10),
            text_color=("#8C8067", "#BDB19A")
        )
        price_note.pack(anchor="w", fill="x", padx=18, pady=(0, 14))
        self._fit_text_to_width(price_note, connection, 40)

        # Resources, practical notes and creator links share a single final section.
        extras = self.card(
            page, "Help, resources and credits",
            "Useful notes and links for using Market Insight."
        )
        for label, url in [
            ("Manage Alpaca API keys", "https://app.alpaca.markets/"),
            ("Alpaca market data guide", "https://docs.alpaca.markets/docs/about-market-data-api"),
            ("Yahoo Finance market overview", "https://finance.yahoo.com/"),
            ("TradingView charts", "https://www.tradingview.com/"),
            ("TikTok  ·  @adrianvaleitl", "https://www.tiktok.com/@adrianvaleitl"),
            ("Official website", "https://adrianvaleitl-debug.github.io/market-insight/"),
            ("GitHub repository", "https://github.com/adrianvaleitl-debug/market-insight")
        ]:
            ctk.CTkButton(
                extras, text=label + "  ↗", corner_radius=16,
                fg_color=("#D8DAD4", "#414841"),
                hover_color=("#C8CBC2", "#50564F"),
                text_color=("#414841", "#E5E4DE"),
                command=lambda target=url: webbrowser.open(target)
            ).pack(anchor="center", pady=4)

        ctk.CTkFrame(extras, height=1, fg_color=("#D8DAD4", "#414841")).pack(
            fill="x", padx=18, pady=(12, 8)
        )

        setting_notes = [
            ("Scan interval", "Automatic scans refresh your watchlist at the interval you choose. More frequent scans do not guarantee better prices or signals."),
            ("Score threshold", "The threshold controls when the app may automatically open a top-scoring stock on your selected platform. It does not mean the stock is likely to rise."),
            ("Trading platform", "Choose where stock links should open. If you select Other, add a URL containing {symbol} where the ticker should be inserted."),
            ("Alpaca credentials", "Your API Key ID and Secret Access Key are stored in Windows Credential Manager. The secret is never shown back on screen.")
        ]
        for heading, description in setting_notes:
            ctk.CTkLabel(
                extras, text=heading, font=ctk.CTkFont(size=10, weight="bold"),
                text_color=("#555D54", "#D8DDD7")
            ).pack(anchor="w", padx=18, pady=(7, 1))
            note = ctk.CTkLabel(
                extras, text=description, font=ctk.CTkFont(size=10),
                justify="left", anchor="w", text_color=("#777D75", "#A7AAA1")
            )
            note.pack(fill="x", padx=18, pady=(0, 5))
            self._fit_text_to_width(note, extras, 40)

        ctk.CTkLabel(
            extras, text="Created by Adrian Vale  ·  Market Insight",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#646D64", "#C0C5BC")
        ).pack(anchor="center", pady=(10, 14))

    def _build_about(self):
        page = self.pages["About"]
        card = self.card(page, "About Market Insight")
        intro = ctk.CTkLabel(card, text="A straightforward tool for researching stocks and keeping track of the ones you're interested in.",
                             font=ctk.CTkFont(size=14, weight="bold"),
                             text_color=("#646D64", "#C0C5BC"), justify="left")
        intro.pack(anchor="w", fill="x", padx=18, pady=(6, 8))
        self._fit_text_to_width(intro, card, 40)
        data_note = ctk.CTkLabel(card, text="When connected, live prices come from Alpaca's IEX data feed. Stock indicators are calculated using past daily prices from Yahoo Finance. IEX does not include every US market trade, so some prices may not be available.",
                                 font=ctk.CTkFont(size=10), justify="left",
                                 text_color=("#777D75", "#A7AAA1"))
        data_note.pack(anchor="w", fill="x", padx=18, pady=5)
        self._fit_text_to_width(data_note, card, 40)
        disclaimer = ctk.CTkLabel(card, text="For education and research only. Scores and indicators are estimates, not financial advice or a guarantee of future results. Market Insight does not connect to your broker and cannot place trades.",
                                  font=ctk.CTkFont(size=10), justify="left",
                                  text_color=("#947B75", "#C5AAA4"))
        disclaimer.pack(anchor="w", fill="x", padx=18, pady=5)
        self._fit_text_to_width(disclaimer, card, 40)
        ctk.CTkLabel(card, text="Created by Adrian Vale  •  Market Insight",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=("#646D64", "#C0C5BC")).pack(anchor="w", padx=18, pady=(14, 18))

        indicators = self.card(page, "What the scanner looks at",
                               "A quick guide to the figures shown on each stock.")
        guide_items = [
            ("EMA 20 / 50", "Moving averages that help show short- and medium-term price direction."),
            ("RSI", "A momentum measure from 0 to 100. High or low readings can suggest stretched momentum, not an automatic trade signal."),
            ("MACD", "Compares moving averages to help highlight changes in momentum."),
            ("ATR", "Estimates typical price movement. The position calculator uses it to help estimate a stop distance."),
            ("Volume ratio", "Compares recent trading volume with its average to highlight unusual activity."),
            ("Market score", "A combined technical research score. It is a screening aid, not a probability or price target.")
        ]
        for name, description in guide_items:
            row = ctk.CTkFrame(indicators, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=5)
            ctk.CTkLabel(row, text=name, width=105, anchor="w",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=("#4A514B", "#D8DDD7")).pack(side="left", anchor="nw")
            detail = ctk.CTkLabel(row, text=description, font=ctk.CTkFont(size=10),
                                  justify="left", anchor="w",
                                  text_color=("#777D75", "#A7AAA1"))
            detail.pack(side="left", fill="x", expand=True)
            self._fit_text_to_width(detail, indicators, 150)

        workflow = self.card(page, "A sensible research routine",
                             "Use the scanner as one part of a wider decision process.")
        routine = [
            "1. Check the wider market pulse and upcoming news.",
            "2. Review the stock's trend, momentum and trading volume.",
            "3. Read any caution flags before considering a setup.",
            "4. Decide your invalidation level before calculating size.",
            "5. Check that the possible reward justifies the risk.",
            "6. Re-check prices and conditions before acting."
        ]
        for item in routine:
            ctk.CTkLabel(workflow, text=item, font=ctk.CTkFont(size=10),
                         justify="left", anchor="w",
                         text_color=("#646D64", "#C0C5BC")).pack(fill="x", padx=18, pady=4)

        sources = self.card(page, "Data sources and useful websites",
                            "Open the services Market Insight uses or the platform you selected.")
        for label, url in [
            ("Alpaca dashboard", "https://app.alpaca.markets/"),
            ("Alpaca market data documentation", "https://docs.alpaca.markets/docs/about-market-data-api"),
            ("Yahoo Finance", "https://finance.yahoo.com/"),
            ("TradingView charts", "https://www.tradingview.com/")
        ]:
            ctk.CTkButton(sources, text=label + "  ↗", corner_radius=16,
                          fg_color=("#D8DAD4", "#414841"),
                          hover_color=("#C8CBC2", "#50564F"),
                          text_color=("#414841", "#E5E4DE"),
                          command=lambda target=url: webbrowser.open(target)
                          ).pack(anchor="center", pady=4)


    def show_page(self, name):
        for frame in self.pages.values():
            frame.grid_remove()
        self.pages[name].grid()
        self.page_title.configure(text={"Overview":"Market overview","Watchlist":"Watchlist","Settings":"Settings","About":"About"}[name])
        for label, button in self.nav_buttons.items():
            button.configure(fg_color=("#D8DED5", "#424A43") if label == name else "transparent")

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
            fg_color=("#555A55", "#3B3E3A"),
            text_color=("#E5E4DE", "#E5E4DE")
        )
        self.status.configure(text="Your watchlist has been saved.")

    def change_windows_startup(self):
        enabled = bool(self.run_startup_var.get())
        try:
            set_windows_startup(enabled)
            self.settings["run_on_windows_startup"] = enabled
            save_settings(self.settings)
            self.status.configure(text="Windows startup preference saved.")
        except Exception as exc:
            self.run_startup_var.set(not enabled)
            from tkinter import messagebox
            messagebox.showerror(APP_NAME, "Couldn't change the Windows startup setting.\n\n{}".format(exc), parent=self)

    def change_update_check_preference(self):
        enabled = bool(self.auto_update_check_var.get())
        self.settings["check_for_updates"] = enabled
        save_settings(self.settings)
        self.status.configure(text="Automatic update checks " + ("enabled." if enabled else "disabled."))

    def check_for_updates(self):
        if getattr(self, "_update_check_running", False):
            return
        self._update_check_running = True
        if hasattr(self, "update_status"):
            self.update_status.configure(text="Checking GitHub for updates…")
        threading.Thread(target=self._check_for_updates_worker, daemon=True).start()

    def _check_for_updates_worker(self):
        try:
            response = requests.get(GITHUB_RELEASES_API, headers={"Accept": "application/vnd.github+json"}, timeout=12)
            response.raise_for_status()
            release = response.json()
            latest_tag = str(release.get("tag_name", "")).strip()
            if version_tuple(latest_tag) <= version_tuple(APP_VERSION):
                self.after(0, lambda: self._show_update_status("You're up to date · v{}".format(APP_VERSION)))
                return
            assets = release.get("assets") or []
            asset = next((item for item in assets if str(item.get("name", "")).endswith(".zip")), None)
            if not asset or not str(asset.get("browser_download_url", "")).startswith("https://github.com/adrianvaleitl-debug/market-insight/releases/download/"):
                self.after(0, lambda: self._show_update_status("A newer release is available, but its ZIP download couldn't be verified. Open GitHub releases."))
                return
            self.after(0, lambda tag=latest_tag, url=asset["browser_download_url"], name=asset["name"]: self._offer_update_download(tag, url, name))
        except Exception:
            self.after(0, lambda: self._show_update_status("Couldn't check GitHub right now. Check your connection and try again."))
        finally:
            self._update_check_running = False

    def _show_update_status(self, message):
        if hasattr(self, "update_status"):
            self.update_status.configure(text=message)

    def _offer_update_download(self, tag, url, filename):
        from tkinter import messagebox
        if not messagebox.askyesno(
            "Market Insight update available",
            "A newer version is available: {}\n\nYou have: v{}\n\nDownload the official update ZIP now?".format(tag, APP_VERSION),
            parent=self
        ):
            self._show_update_status("Update {} is available on GitHub.".format(tag))
            return
        self._show_update_status("Downloading {}…".format(tag))
        threading.Thread(target=self._download_update_worker, args=(url, filename, tag), daemon=True).start()

    def _download_update_worker(self, url, filename, tag):
        try:
            response = requests.get(url, stream=True, timeout=(15, 90))
            response.raise_for_status()
            downloads = Path.home() / "Downloads"
            downloads.mkdir(parents=True, exist_ok=True)
            destination = downloads / filename
            temporary = destination.with_suffix(destination.suffix + ".part")
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        output.write(chunk)
            temporary.replace(destination)
            self.after(0, lambda path=destination, version=tag: self._update_download_complete(path, version))
        except Exception:
            self.after(0, lambda: self._show_update_status("The update download failed. Please try again or use GitHub releases."))

    def _update_download_complete(self, path, tag):
        self._show_update_status("Downloaded {} to Downloads. Close the app and extract the ZIP to update.".format(tag))
        try:
            os.startfile(str(path.parent))
        except Exception:
            pass
        from tkinter import messagebox
        messagebox.showinfo(
            "Update downloaded",
            "Market Insight {} has been downloaded to your Downloads folder.\n\nClose Market Insight, extract the ZIP, and replace the old app files with the new ones.".format(tag),
            parent=self
        )

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
        if hasattr(self, "startup_mode_menu"):
            self.settings["startup_window_mode"] = self.startup_mode_menu.get()
        save_settings(self.settings)
        self.status.configure(text="Your settings have been saved. The display mode will apply next time you open Market Insight.")
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
            fg_color=("#555A55", "#3B3E3A"),
            text_color=("#E5E4DE", "#E5E4DE")
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
            if (i + 1) % 5 == 0 or i + 1 == len(symbols):
                self.after(0, lambda n=i+1, total=len(symbols): self.scan_info.configure(text=f"Scanned {n}/{total}"))
        market_context = fetch_market_context()
        self.after(0, lambda: self._finish_scan(output, market_context))

    def _render_stock_cards(self, parent, rows, limit=None, caution=False):
        """Render cards in short batches so the window stays responsive."""
        previous_job = getattr(parent, "_render_job", None)
        if previous_job:
            try:
                parent.after_cancel(previous_job)
            except Exception:
                pass
            parent._render_job = None

        for child in parent.winfo_children():
            child.destroy()

        rows = list(rows if limit is None else rows[:limit])
        if not rows:
            ctk.CTkLabel(
                parent, text="No stocks to show yet. Run a scan to see results here.",
                text_color=("#858A80", "#AEB1A8")
            ).pack(anchor="w", padx=12, pady=14)
            return

        def render_batch(index=0):
            parent._render_job = None
            end_index = min(index + 6, len(rows))
            for symbol, data in rows[index:end_index]:
                tile = ctk.CTkFrame(parent, corner_radius=18, fg_color=("#EFEEE8", "#30332F"))
                tile.pack(fill="x", padx=5, pady=5)
                head = ctk.CTkFrame(tile, fg_color="transparent")
                head.pack(fill="x", padx=13, pady=(9, 2))
                title_area = ctk.CTkFrame(head, fg_color="transparent")
                title_area.pack(side="left", fill="x", expand=True)
                company_name = ctk.CTkLabel(
                    title_area, text=STOCK_NAMES.get(symbol, symbol),
                    font=ctk.CTkFont(size=12, weight="bold"), justify="left"
                )
                company_name.pack(anchor="w", fill="x")
                self._fit_text_to_width(company_name, title_area, 12)
                ctk.CTkLabel(
                    title_area, text=symbol, font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=("#777D75", "#AEB1A8")
                ).pack(anchor="w")

                if caution:
                    warning_text = ctk.CTkLabel(
                        tile, text=", ".join(data.get("warnings", [])) or "Needs a closer look",
                        font=ctk.CTkFont(size=10), text_color=("#A87975", "#C5AAA4"),
                        justify="left"
                    )
                    warning_text.pack(anchor="w", fill="x", padx=13, pady=(2, 9))
                    self._fit_text_to_width(warning_text, tile, 30)
                else:
                    tone = ("#738875", "#B4C4B1") if data["day_change"] >= 0 else ("#A87975", "#C5AAA4")
                    info = ctk.CTkFrame(tile, fg_color="transparent")
                    info.pack(fill="x", padx=13, pady=(5, 10))
                    ctk.CTkLabel(
                        info, text="USD {:.2f}".format(data["price"]),
                        font=ctk.CTkFont(size=14, weight="bold")
                    ).pack(side="left")
                    ctk.CTkLabel(
                        info, text="{:+.2f}%".format(data["day_change"]),
                        font=ctk.CTkFont(size=11, weight="bold"), text_color=tone
                    ).pack(side="left", padx=(10, 0))
                    ctk.CTkLabel(
                        info, text="Score: {}/100 · RSI: {:.0f} · Vol: {:.1f}x".format(
                            data["score"], data["rsi"], data["volume_ratio"]
                        ),
                        font=ctk.CTkFont(size=9, weight="bold"),
                        text_color=("#747A72", "#B8BDB4")
                    ).pack(side="left", padx=(10, 0))
                    ctk.CTkButton(
                        info, text="View on {} ↗".format(self.settings.get("selected_platform", "platform")),
                        width=145, height=28, corner_radius=9, font=ctk.CTkFont(size=10),
                        command=lambda sym=symbol: self.open_selected_platform(sym, ask=True)
                    ).pack(side="right")

            if end_index < len(rows):
                parent._render_job = parent.after(10, lambda: render_batch(end_index))

        render_batch()

    def _finish_scan(self, output, market_context=None):
        self.results = output
        market_context = market_context or {}
        for symbol, label in getattr(self, "market_pulse_labels", {}).items():
            data = market_context.get(symbol)
            if data:
                label.configure(text="{:.2f}  ({:+.2f}%)".format(data["price"], data["change"]))
                tone = ("#8C8067", "#BDB19A") if symbol == "^VIX" else (("#738875", "#B4C4B1") if data["change"] >= 0 else ("#A87975", "#C5AAA4"))
                label.configure(text_color=tone)
            else:
                label.configure(text="Not available")
        breadth_valid = [d for d in output.values() if "error" not in d]
        if breadth_valid and hasattr(self, "market_breadth"):
            advancing = sum(1 for d in breadth_valid if d.get("day_change", 0) > 0)
            declining = sum(1 for d in breadth_valid if d.get("day_change", 0) < 0)
            unchanged = len(breadth_valid) - advancing - declining
            self.market_breadth.configure(text="Watchlist breadth: {} up  ·  {} down  ·  {} flat".format(advancing, declining, unchanged))
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
            issue = ctk.CTkFrame(self.results_text, corner_radius=12, fg_color=("#EEE8E4", "#393331"))
            issue.pack(fill="x", padx=5, pady=6)
            ctk.CTkLabel(issue, text="Stocks we couldn't check", font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=("#A87975", "#C5AAA4")).pack(anchor="w", padx=12, pady=(8, 2))
            error_details = ctk.CTkLabel(issue, text="\\n".join(errors[:12]),
                                         font=ctk.CTkFont(size=10), justify="left",
                                         text_color=("#947B75", "#C5AAA4"))
            error_details.pack(anchor="w", fill="x", padx=12, pady=(0, 10))
            self._fit_text_to_width(error_details, issue, 28)
        self.status.configure(text=f"Scan complete · {len(valid)} symbols")
        self.scan_info.configure(
            text=f"Last scan: {datetime.now().strftime('%H:%M')}",
            fg_color=("#555A55", "#3B3E3A"),
            text_color=("#E5E4DE", "#E5E4DE")
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
    if not acquire_single_instance():
        raise SystemExit(0)
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
