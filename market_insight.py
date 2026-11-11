import json
import math
import csv
import os
import hashlib
import sys
import subprocess
import threading
import traceback
import colorsys
import webbrowser
import requests
import certifi
import keyring
import tkinter as tk
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageTk

GLASS_KEY = "#010101"

def apply_windows_glass_backdrop(window, transparency=8, light=False):
    """Expose a Windows acrylic backdrop through transparent Tk root pixels."""
    if sys.platform != "win32":
        return False
    key = GLASS_KEY
    try:
        # Tk's colour-key transparency lets DWM draw acrylic behind the client
        # area without fading child text, icons or controls.
        window.wm_attributes("-transparentcolor", key)
        window.configure(fg_color=key)
    except Exception:
        # Keep the app usable if colour-key transparency is unavailable.
        try:
            window.configure(fg_color="#EDEDED" if light else "#101012")
        except Exception:
            pass
    try:
        window.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = ctypes.c_void_p(window.winfo_id())
        try:
            user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user32.GetAncestor.restype = ctypes.c_void_p
            hwnd = ctypes.c_void_p(user32.GetAncestor(hwnd, 2) or hwnd.value)
        except Exception:
            pass

        # Windows 11 system backdrop (transient acrylic).
        backdrop_ok = False
        try:
            backdrop = ctypes.c_int(3)
            dwm_set = ctypes.windll.dwmapi.DwmSetWindowAttribute
            dwm_set.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
            dwm_set.restype = ctypes.c_long
            result = dwm_set(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
            backdrop_ok = (result == 0)
        except Exception:
            pass

        # Acrylic fallback also supplies a user-adjustable tint on Windows 10.
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_int), ("AnimationId", ctypes.c_int)]
        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),
                        ("SizeOfData", ctypes.c_size_t)]
        amount = max(0, min(35, int(transparency)))
        alpha = 0xE8 - round((0xE8 - 0x70) * amount / 35)
        colour = 0x00F0F0F0 if light else 0x0017171B
        policy = ACCENT_POLICY(4, 2, (alpha << 24) | colour, 0)
        data = WINDOWCOMPOSITIONATTRIBDATA(19, ctypes.addressof(policy), ctypes.sizeof(policy))
        apply_attribute = user32.SetWindowCompositionAttribute
        apply_attribute.argtypes = [ctypes.c_void_p, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        apply_attribute.restype = ctypes.c_bool
        accent_ok = bool(apply_attribute(hwnd, ctypes.byref(data)))
        try:
            user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                            ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            user32.SetWindowPos.restype = ctypes.c_bool
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                                0x0001 | 0x0002 | 0x0004 | 0x0020)
        except Exception:
            pass
        return backdrop_ok or accent_ok
    except Exception:
        return False



def install_accent_spotlight(window, accent, background="#101012"):
    """Render a soft multi-layer nebula glow behind the app's glass surfaces."""
    try:
        if not isinstance(accent, str) or len(accent) != 7 or not accent.startswith("#"):
            return
        window.update_idletasks()
        width = max(900, int(window.winfo_width()))
        height = max(620, int(window.winfo_height()))
        rgb = tuple(int(accent[index:index + 2], 16) for index in (1, 3, 5))
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)
        # Broad atmospheric haze plus several softer nebula cores. Keep the
        # edges diffuse so the colour never looks like a hard spotlight.
        blobs = [
            (0.76, 0.10, 0.48, 0.48, 68),
            (0.92, 0.42, 0.34, 0.38, 46),
            (0.18, 0.88, 0.42, 0.38, 32),
            (0.46, 0.52, 0.34, 0.30, 22),
        ]
        for cx, cy, rx, ry, alpha in blobs:
            bounds = (int((cx-rx)*width), int((cy-ry)*height),
                      int((cx+rx)*width), int((cy+ry)*height))
            draw.ellipse(bounds, fill=(*rgb, alpha))
        glow = glow.filter(ImageFilter.GaussianBlur(max(90, int(min(width, height) * 0.19))))
        photo = ImageTk.PhotoImage(glow)
        previous = getattr(window, "_accent_spotlight_canvas", None)
        if previous is not None and previous.winfo_exists():
            previous.destroy()
        canvas = tk.Canvas(window, width=width, height=height, highlightthickness=0,
                           borderwidth=0, bg=background)
        canvas.place(x=0, y=0, relwidth=1, relheight=1)
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas.lower()
        window._accent_spotlight_canvas = canvas
        window._accent_spotlight_photo = photo
        # Do not regenerate a blurred full-window bitmap for every resize event.
        # Keeping the glow static removes expensive image processing while dragging.
        window._active_spotlight_colour = accent
    except Exception:
        # A decorative layer must never interrupt app startup or navigation.
        pass

# Apply bold typography globally, including widgets that use CustomTkinter's
# built-in default font (such as sidebar buttons and small helper/status text).
_original_ctkfont_init = ctk.CTkFont.__init__

def _bold_ctkfont_init(self, *args, **kwargs):
    kwargs["weight"] = "bold"
    _original_ctkfont_init(self, *args, **kwargs)

ctk.CTkFont.__init__ = _bold_ctkfont_init
import pandas as pd
import yfinance as yf
import ctypes
import winreg
from tkinter import filedialog

APP_NAME = "Market Insight"
APP_VERSION = "V1.16"
PERSONAL_SITE = "https://adrianvaleitl-debug.github.io/"
KOFI_URL = "https://ko-fi.com/marketinsight"

# Keep this release history current whenever a new version is published.
RELEASE_NOTES = [
    {
        "version": "V1.16",
        "title": "Reliable colour themes and smoother resizing",
        "date": "11 November 2026",
        "items": [
            "Stopped resetting CustomTkinter's global theme manager during live accent changes.",
            "Removed repeated full-window spotlight image processing during interactive resizing.",
            "Restored a consistent 1380 × 900 default window and 1020 × 680 minimum size.",
            "Prevented theme refreshes from scheduling duplicate price-alert polling.",
            "Preserved watchlists, scans, saved plans, alerts, credentials and research data.",
        ],
    },
    {
        "version": "V1.15",
        "title": "Accent spotlight and creator shortcuts",
        "date": "11 November 2026",
        "items": [
            "Added an accent-colour spotlight and persistent Adrian Vale / Ko-fi shortcuts.",
            "Introduced the initial transparency control; the Windows backdrop implementation is refined in V1.15.",
        ],
    },
    {
        "version": "V1.11",
        "title": "A quieter, more Mac-like workspace",
        "date": "November 2026",
        "items": [
            "Introduced adjustable transparency preferences and neutral charcoal surfaces.",
            "Standardised the app's typography, panels and settings controls.",
        ],
    },
    {
        "version": "V1.10",
        "title": "A unified analyst workspace",
        "date": "November 2026",
        "items": [
            "Reworked the desktop interface around a floating sidebar and rounded research panels.",
            "Standardised navigation, market context and watchlist surfaces.",
        ],
    },
    {
        "version": "V1.9",
        "title": "Currency colours that feel right",
        "date": "November 2026",
        "items": [
            "Refined the five currency accent palettes to better match each currency visual identity.",
            "Updated Light and Dark modes while keeping saved theme choices and status colours intact.",
        ],
    },
    {
        "version": "V1.8",
        "title": "A more disciplined trading workspace",
        "date": "November 2026",
        "items": [
            "Added the Trade Planner with risk-based position sizing and reward-to-risk calculations.",
            "Saved trade plans locally and added input guardrails for price levels and risk.",
        ],
    },
    {
        "version": "V1.6",
        "title": "A more focused analyst workspace",
        "date": "November 2026",
        "items": [
            "Refined page hierarchy, scan actions, market context and watchlist research.",
            "Introduced a denser terminal-style layout for market information.",
        ],
    },
    {
        "version": "V1.5",
        "title": "Deeper research and smarter organisation",
        "date": "November 2026",
        "items": [
            "Added watchlist folders, saved scan history, ticker notes and reusable scan presets.",
            "Added a daily market briefing from the latest completed scan.",
        ],
    },
    {
        "version": "V1.4",
        "title": "Scanner improvements",
        "date": "November 2026",
        "items": [
            "Added scan snapshots, ticker search, sorting, filters and CSV export.",
            "Added font, bold-text, currency and accent-colour preferences.",
        ],
    },
]
# Temporary QA switch: replay first-launch onboarding on every startup.
# Existing credentials and preferences are preserved.
ONBOARDING_TEST_MODE = False
# v1.2.24 resolves the bundled icon from PyInstaller's runtime resource folder.
GITHUB_RELEASES_API = "https://api.github.com/repos/adrianvaleitl-debug/market-insight/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/adrianvaleitl-debug/market-insight/releases/latest"
_SINGLE_INSTANCE_MUTEX = None
_WINDOW_ICON_HANDLES = []


def set_windows_window_icon(window, icon_path):
    """Set explicit high-resolution Windows taskbar and title-bar icons."""
    if not sys.platform.startswith("win") or not icon_path or not Path(icon_path).is_file():
        return
    try:
        user32 = ctypes.windll.user32
        user32.LoadImageW.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint,
            ctypes.c_int, ctypes.c_int, ctypes.c_uint
        ]
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p
        ]
        user32.SendMessageW.restype = ctypes.c_void_p
        hwnd = ctypes.c_void_p(window.winfo_id())
        load_from_file = 0x0010
        image_icon = 1
        wm_seticon = 0x0080
        icon_small = 0
        icon_big = 1
        # Load the exact 256px and 32px frames from the multi-resolution ICO.
        for size, kind in ((256, icon_big), (32, icon_small)):
            handle = user32.LoadImageW(
                None, str(icon_path), image_icon, size, size, load_from_file
            )
            if handle:
                user32.SendMessageW(
                    hwnd, wm_seticon, ctypes.c_void_p(kind), ctypes.c_void_p(handle)
                )
                _WINDOW_ICON_HANDLES.append(handle)
    except Exception:
        # Keep the existing Tk icon as a safe fallback on unsupported systems.
        pass


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
    "colour_theme": "Black",
    "transparency": 8,
    "font_family": "Segoe UI",
    "bold_text": True,
    "startup_window_mode": "Maximised",
    "auto_scan": True,
    "scan_interval": 5,
    "auto_open_tradingview": False,
    "confirm_tradingview": False,
    "threshold": 70,
    "watchlist": DEFAULT_TICKERS,
    "balance": 1000.0,
    "currency": "USD",
    "risk_percent": 1.0,
    "selected_platform": "",
    "custom_platform_url": "",
    "auto_open_platform": False,
    "shortcut_prompted": False,
    "tutorial_completed": False,
    "create_desktop_shortcut": False,
    "run_on_windows_startup": False,
    "check_for_updates": True,
    "price_alerts": [],
    "trade_journal": [],
    "watchlist_folders": {},
    "scan_history": [],
    "ticker_notes": {},
    "scan_presets": {},
    "daily_briefing": "",
    "trade_plans": [],
}


# Five high-contrast accent identities. The hue is applied consistently across
# cards, controls and highlights while preserving each surface's lightness.
ACTIVE_COLOUR_THEME = "Black"
ACTIVE_FONT_FAMILY = "Segoe UI"
ACTIVE_BOLD_TEXT = True
# Currency-inspired hues, softened to work across both Light and Dark modes.
COLOUR_THEME_HUES = {"Black": 0, "Amber": 38, "Azure": 215, "Lavender": 270, "Rose": 345, "Teal": 185, "Dollar": 0, "Euro": 215, "Pound": 270, "Yen": 345, "Franc": 185}
COLOUR_ACCENTS = {"Black":("#B9B9B9","#A0A0A0"),"Amber":("#D7B77F","#BFA16A"),"Azure":("#91AFE0","#7897C8"),"Lavender":("#B5A0D8","#9B86BE"),"Rose":("#D99EAD","#C48495"),"Teal":("#91BEC3","#76A6AB")}
CURRENCY_OPTIONS = {
    "USD": "USD ($)",
    "GBP": "GBP (£)",
    "EUR": "EUR (€)",
    "CAD": "CAD ($)",
    "AUD": "AUD ($)",
    "JPY": "JPY (¥)",
    "CHF": "CHF (Fr)",
}
CURRENCY_SYMBOLS = {
    "USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$",
    "AUD": "A$", "JPY": "¥", "CHF": "Fr",
}

def currency_to_usd_rate(currency):
    """Return the latest available units-to-USD FX rate using Yahoo Finance."""
    if currency == "USD":
        return 1.0
    history = yf.Ticker("{}USD=X".format(currency)).history(period="5d")
    if history.empty or "Close" not in history:
        raise ValueError("The {} to USD exchange rate is currently unavailable.".format(currency))
    rate = safe_num(history["Close"].dropna().iloc[-1], 0)
    if rate <= 0:
        raise ValueError("The {} to USD exchange rate is currently unavailable.".format(currency))
    return rate


def palette_color(value):
    """Keep the forest-green glass surfaces neutral; accents are applied by controls."""
    return value

def apply_ctk_palette_theme():
    """Update CustomTkinter's built-in accent colours for the active palette."""
    # The base CustomTkinter theme is loaded once at startup. Do not replace
    # ThemeManager during a live palette change; update its existing entries.
    theme = ctk.ThemeManager.theme
    primary, hover = COLOUR_ACCENTS.get(ACTIVE_COLOUR_THEME, COLOUR_ACCENTS["Black"])
    muted = {
        "CTkButton": {"fg_color": [primary, primary], "hover_color": [hover, hover], "text_color": ["#202020", "#202020"], "corner_radius": 13},
        "CTkCheckBox": {"fg_color": [primary, primary], "hover_color": [hover, hover], "border_color": ["#7F7F7F", "#7F7F7F"], "checkmark_color": ["#202020", "#202020"]},
        "CTkSwitch": {"fg_color": ["#434343", "#434343"], "progress_color": [primary, primary], "button_color": ["#F2F2F2", "#F2F2F2"], "button_hover_color": ["#FFFFFF", "#FFFFFF"]},
        "CTkOptionMenu": {"fg_color": ["#282828", "#282828"], "button_color": [primary, primary], "button_hover_color": [hover, hover], "text_color": ["#F2F2F2", "#F2F2F2"], "dropdown_fg_color": ["#1F1F1F", "#1F1F1F"], "dropdown_hover_color": ["#363636", "#363636"], "dropdown_text_color": ["#F2F2F2", "#F2F2F2"], "corner_radius": 13},
        "CTkSlider": {"progress_color": [palette_color("#797979"), palette_color("#6E6E6E")], "button_color": [palette_color("#797979"), palette_color("#6E6E6E")], "button_hover_color": [palette_color("#676767"), palette_color("#515151")]},
        "CTkProgressBar": {"progress_color": [palette_color("#797979"), palette_color("#6E6E6E")]},
        "CTkRadioButton": {"fg_color": [palette_color("#797979"), palette_color("#6E6E6E")], "hover_color": [palette_color("#676767"), palette_color("#515151")]},
    }
    for widget_name, values in muted.items():
        if widget_name in theme:
            theme[widget_name].update(values)


def app_font(*args, **kwargs):
    """Create a consistently bold app font using the user-selected font family."""
    kwargs.setdefault("family", ACTIVE_FONT_FAMILY)
    kwargs.setdefault("weight", "bold" if ACTIVE_BOLD_TEXT else "normal")
    return ctk.CTkFont(*args, **kwargs)


def styled_settings_dropdown(parent, values, command=None):
    """Create a settings selector that matches the app's soft card styling."""
    return ctk.CTkOptionMenu(
        parent,
        values=values,
        command=command,
        width=230,
        height=36,
        corner_radius=10,
        fg_color=(palette_color("#E8E8E8"), palette_color("#383838")),
        button_color=(palette_color("#D6D6D6"), palette_color("#4D4D4D")),
        button_hover_color=(palette_color("#CBCBCB"), palette_color("#5C5C5C")),
        text_color=(palette_color("#383838"), palette_color("#EBEBEB")),
        dropdown_fg_color=(palette_color("#F7F7F7"), palette_color("#2A2A2A")),
        dropdown_hover_color=(palette_color("#E7E7E7"), palette_color("#424242")),
        dropdown_text_color=(palette_color("#383838"), palette_color("#EBEBEB")),
        font=app_font(size=13, weight="bold"),
        dropdown_font=app_font(size=13, weight="bold"),
        anchor="w",
    )


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
    """Find the current icon in both PyInstaller and normal Python locations."""
    # PyInstaller 6 places --add-data files inside sys._MEIPASS (usually _internal).
    # Prefer that bundled asset so an older icon beside the executable cannot win.
    resource_dir = Path(getattr(sys, "_MEIPASS", APP_DIR))
    candidates = (resource_dir / "market_insight.ico", APP_DIR / "market_insight.ico")
    for icon_path in candidates:
        if icon_path.is_file():
            return icon_path
    # Never manufacture the obsolete green fallback icon.
    return None
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


def _uk_market_time(day, zone, hour, minute=0):
    uk_zone = ZoneInfo("Europe/London")
    uk_now = datetime.now(uk_zone)
    market_day = uk_now.astimezone(ZoneInfo(zone)).date() if uk_now.date() == day else day
    local = datetime.combine(market_day, time(hour, minute), tzinfo=ZoneInfo(zone))
    return local.astimezone(uk_zone)


def _uk_market_range(day, zone, start, end):
    a = _uk_market_time(day, zone, *start)
    b = _uk_market_time(day, zone, *end)
    def clock(value):
        suffix = " (+1 day)" if value.date() > day else (" (prev. day)" if value.date() < day else "")
        return value.strftime("%H:%M") + suffix
    return clock(a) + "–" + clock(b)


def _uk_market_overlap(day, zone_a, hours_a, zone_b, hours_b):
    a = (_uk_market_time(day, zone_a, *hours_a[0]), _uk_market_time(day, zone_a, *hours_a[1]))
    b = (_uk_market_time(day, zone_b, *hours_b[0]), _uk_market_time(day, zone_b, *hours_b[1]))
    start, end = max(a[0], b[0]), min(a[1], b[1])
    if end <= start:
        return "No overlap today"
    return start.strftime("%H:%M") + "–" + end.strftime("%H:%M")

class MarketInsightApp(ctk.CTk):
    def __init__(self):
        # Set the Windows taskbar identity before creating the Tk window.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AdrianVale.MarketInsight")
        except Exception:
            pass
        super().__init__()
        self.settings = load_settings()
        global ACTIVE_COLOUR_THEME
        previous_theme_names = {
            "Emerald": "Black", "Sapphire": "Azure", "Violet": "Lavender",
            "Crimson": "Rose", "Amber": "Amber", "Dollar": "Black", "Euro": "Azure", "Pound": "Lavender", "Yen": "Rose", "Franc": "Teal",
        }
        saved_theme = self.settings.get("colour_theme", "Black")
        ACTIVE_COLOUR_THEME = previous_theme_names.get(saved_theme, saved_theme)
        global ACTIVE_FONT_FAMILY, ACTIVE_BOLD_TEXT
        ACTIVE_FONT_FAMILY = self.settings.get("font_family", "Segoe UI")
        ACTIVE_BOLD_TEXT = bool(self.settings.get("bold_text", True))
        if ACTIVE_FONT_FAMILY not in ("Segoe UI", "Arial", "Verdana", "Trebuchet MS", "Georgia"):
            ACTIVE_FONT_FAMILY = "Segoe UI"
        if ACTIVE_COLOUR_THEME not in COLOUR_THEME_HUES:
            ACTIVE_COLOUR_THEME = "Black"
        self.settings["colour_theme"] = ACTIVE_COLOUR_THEME
        if self.settings.get("currency") not in CURRENCY_OPTIONS:
            self.settings["currency"] = "USD"
        ctk.set_appearance_mode(self.settings["appearance"].lower())
        ctk.set_default_color_theme("green")
        apply_ctk_palette_theme()
        self.title(APP_NAME)
        icon_path = ensure_app_icon()
        if icon_path and icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{min(1380, max(1080, screen_w - 80))}x{min(900, max(720, screen_h - 100))}")
        self.minsize(1020, 680)
        # Apply native Windows icon handles after the window has a real HWND.
        if icon_path and icon_path.exists():
            self.update_idletasks()
            set_windows_window_icon(self, icon_path)
        self.configure(fg_color=GLASS_KEY if sys.platform=="win32" else ("#EDEDED", "#101010"))
        self.apply_liquid_glass()
        self.results = {}
        self.scanning = False
        self.after_id = None
        # Keep the root window mapped while onboarding dialogs are displayed.
        # Withdrawing the parent can also hide its CTkToplevel setup dialog on Windows.
        api_key, secret_key = get_alpaca_credentials()
        valid = self._validate_alpaca_credentials(api_key, secret_key)[0] if api_key and secret_key else False
        self.saved_alpaca_connection_valid = valid
        if ONBOARDING_TEST_MODE:
            # Replay first-run setup without deleting saved data.
            self._show_alpaca_setup()
        elif valid and self.settings.get("selected_platform"):
            self._launch_main_ui()
        elif valid:
            self._show_platform_setup()
        else:
            self._show_alpaca_setup()

    def apply_liquid_glass(self):
        try:
            if not sys.platform.startswith("win"):
                return
            apply_windows_glass_backdrop(
                self, int(self.settings.get("transparency", 8)),
                ctk.get_appearance_mode() == "Light")
        except Exception:
            pass

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
                win.iconbitmap(str(icon_path))
            except Exception:
                pass
        win.geometry("650x590")
        win.minsize(560, 520)
        win.configure(fg_color=(palette_color("#F0F0F0"), palette_color("#212121")))
        win.protocol("WM_DELETE_WINDOW", self.destroy)
        win.grab_set()
        panel = ctk.CTkFrame(win, corner_radius=24, fg_color=(palette_color("#F7F7F7"), palette_color("#323232")))
        panel.pack(fill="both", expand=True, padx=22, pady=22)
        ctk.CTkLabel(panel, text="MARKET INSIGHT", font=app_font(size=16, weight="bold")).pack(anchor="w", padx=30, pady=(25, 8))
        ctk.CTkLabel(panel, text=title, font=app_font(size=28, weight="bold"),
                     wraplength=540, justify="left").pack(anchor="w", fill="x", padx=30)
        setup_description = ctk.CTkLabel(panel, text=subtitle, font=app_font(size=14, weight="bold"),
                                         justify="left")
        setup_description.pack(anchor="w", fill="x", padx=30, pady=(8, 18))
        self._fit_text_to_width(setup_description, panel, 60)
        return win, panel

    def _show_alpaca_setup(self):
        win, panel = self._setup_window("Connect your Alpaca account", "To get live market prices, connect your Alpaca account. Enter your API details below and we'll check that they work before continuing.")
        if getattr(self, "saved_alpaca_connection_valid", False):
            ctk.CTkButton(
                panel, text="Continue with my saved Alpaca connection", height=40,
                command=self._continue_with_saved_alpaca
            ).pack(fill="x", padx=30, pady=(0, 12))
            ctk.CTkLabel(
                panel, text="Or enter different API keys below to replace the saved connection.",
                font=app_font(size=12, weight="bold"), justify="left"
            ).pack(anchor="w", padx=30, pady=(0, 8))
        ctk.CTkLabel(panel, text="API Key ID").pack(anchor="w", padx=30, pady=(0, 5))
        self.setup_key_entry = ctk.CTkEntry(panel, height=44, placeholder_text="Paste your Alpaca API Key ID here")
        self.setup_key_entry.pack(fill="x", padx=30, pady=(0, 13))
        ctk.CTkLabel(panel, text="Secret Access Key").pack(anchor="w", padx=30, pady=(0, 5))
        self.setup_secret_entry = ctk.CTkEntry(panel, height=44, show="•", placeholder_text="Paste your Alpaca Secret Access Key")
        self.setup_secret_entry.pack(fill="x", padx=30)
        ctk.CTkButton(panel, text="Get your API keys from Alpaca ↗", fg_color="transparent",
                      text_color=(palette_color("#757575"), palette_color("#BFBFBF")),
                      command=lambda: webbrowser.open("https://app.alpaca.markets/")).pack(anchor="w", padx=25, pady=12)
        self.setup_status = ctk.CTkLabel(panel, text="Your keys are saved securely in Windows Credential Manager on this computer.",
                                         font=app_font(size=13, weight="bold"), justify="left")
        self.setup_status.pack(anchor="w", fill="x", padx=30, pady=8)
        self._fit_text_to_width(self.setup_status, panel, 60)
        ctk.CTkButton(panel, text="Check keys and continue", height=45, command=self._validate_setup_keys).pack(fill="x", padx=30, pady=18)
        win.focus_force()

    def _continue_with_saved_alpaca(self):
        self.setup_window.grab_release()
        self.setup_window.destroy()
        self._show_platform_setup()

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
            row = ctk.CTkFrame(panel, corner_radius=12, fg_color=(palette_color("#EBEBEB"), palette_color("#323232")))
            row.pack(fill="x", padx=30, pady=3)
            ctk.CTkRadioButton(row, text=name, value=name, variable=self.setup_platform_var).pack(anchor="w", padx=14, pady=(7, 0))
            ctk.CTkLabel(row, text=detail, font=app_font(size=13, weight="bold")).pack(anchor="w", padx=39, pady=(0, 6))
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
        if not getattr(self, "_price_alert_poll_started", False):
            self._price_alert_poll_started = True
            self.after(15000, self._check_price_alerts)
        self.after(700, self._maybe_prompt_shortcut)
        # Show the beginner walkthrough once, on the user's first successful launch.
        if not self.settings.get("tutorial_completed", False):
            self.after(1200, self.show_beginner_tutorial)
        if self.settings.get("check_for_updates", True):
            self.after(3000, self.check_for_updates)
        if self.settings.get("auto_scan"):
            self.after(900, self.start_scan)

    def show_beginner_tutorial(self):
        """Display a guided, repeatable introduction to the main app features."""
        existing = getattr(self, "_tutorial_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    return
            except Exception:
                pass
        steps = [
            ("Welcome to Market Insight",
             "This short tour explains the main areas of the app and how to get started. It appears every time you open the app in this test version. Nothing in this tour places trades."),
            ("1. Your market overview",
             "The Overview is your starting point. It shows the highest-scoring stock from your latest scan, watchlist highlights, market direction and a position-size calculator. The figures are analysis tools, not guaranteed predictions."),
            ("2. Build your watchlist",
             "Open Watchlist in the left menu. Replace the example ticker symbols with the stocks you want to follow, separated by commas. Select Save watchlist. You can track up to 100 symbols."),
            ("3. Run your first scan",
             "Return to Overview and select Scan watchlist. Market Insight checks each symbol one at a time. The counter shows how many are left. When the scan finishes, the results appear in Overview and Watchlist."),
            ("4. Understand the results",
             "Each stock has a score out of 100, daily price movement, RSI and volume information. Higher scores mean more of the scanner's selected conditions are present; they are not a promise that a stock will rise. Read any warnings before making a decision."),
            ("5. Check market timing and news",
             "Market Hours shows major trading sessions and exchange opening times in UK local time. Economic Calendar lists upcoming releases that can move markets. High-impact news can cause sharp price changes and wider spreads."),
            ("6. Alerts and your journal",
             "Price Alerts can notify you when a ticker reaches a price you choose while Market Insight is open. Trading Journal lets you record closed trades and review your own results. Neither feature places trades for you."),
            ("7. Make the app yours",
             "Settings contains appearance, colour themes, trading platform, risk calculator and update preferences. Your Alpaca API credentials are used to retrieve market data. Keep them private and never share your secret key.")
        ]
        win = ctk.CTkToplevel(self)
        self._tutorial_window = win
        win.title("Getting started · Market Insight")
        win.geometry("720x560")
        win.minsize(620, 500)
        win.configure(fg_color=(palette_color("#F0F0F0"), palette_color("#212121")))
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_beginner_tutorial(win))
        try:
            icon_path = APP_DIR / "market_insight.ico"
            if icon_path.exists():
                win.iconbitmap(str(icon_path))
        except Exception:
            pass

        panel = ctk.CTkFrame(win, corner_radius=24, fg_color=(palette_color("#F7F7F7"), palette_color("#323232")))
        panel.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(panel, text="MARKET INSIGHT  ·  QUICK START",
                     font=app_font(size=12, weight="bold"),
                     text_color=(palette_color("#828282"), palette_color("#BFBFBF"))).pack(anchor="w", padx=28, pady=(26, 10))
        title = ctk.CTkLabel(panel, text="", font=app_font(size=27, weight="bold"),
                             justify="left", anchor="w", wraplength=610)
        title.pack(fill="x", padx=28, pady=(8, 12))
        body = ctk.CTkLabel(panel, text="", font=app_font(size=16, weight="bold"),
                            justify="left", anchor="nw", wraplength=610)
        body.pack(fill="both", expand=True, padx=28, pady=(4, 14))
        progress = ctk.CTkLabel(panel, text="", font=app_font(size=12, weight="bold"),
                                text_color=(palette_color("#7B7B7B"), palette_color("#B0B0B0")))
        progress.pack(anchor="w", padx=28, pady=(0, 8))
        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=(0, 22))
        back_button = ctk.CTkButton(buttons, text="Back", width=100, state="disabled")
        back_button.pack(side="left", padx=4)
        skip_button = ctk.CTkButton(buttons, text="Close tour", width=110, fg_color="transparent",
                                    text_color=(palette_color("#757575"), palette_color("#BFBFBF")),
                                    command=lambda: self._close_beginner_tutorial(win))
        skip_button.pack(side="right", padx=4)
        next_button = ctk.CTkButton(buttons, text="Next", width=130)
        next_button.pack(side="right", padx=4)
        state = {"index": 0}

        def render():
            index = state["index"]
            heading, description = steps[index]
            title.configure(text=heading)
            body.configure(text=description)
            progress.configure(text="STEP {} OF {}".format(index + 1, len(steps)))
            back_button.configure(state="normal" if index else "disabled")
            next_button.configure(text="Finish" if index == len(steps) - 1 else "Next")

        def go_back():
            state["index"] = max(0, state["index"] - 1)
            render()

        def go_next():
            if state["index"] >= len(steps) - 1:
                self._close_beginner_tutorial(win)
                return
            state["index"] += 1
            render()

        back_button.configure(command=go_back)
        next_button.configure(command=go_next)
        render()
        win.update_idletasks()
        try:
            win.grab_set()
            win.focus_force()
        except Exception:
            pass

    def _close_beginner_tutorial(self, window):
        try:
            window.grab_release()
        except Exception:
            pass
        try:
            window.destroy()
        except Exception:
            pass
        self._tutorial_window = None
        if not self.settings.get("tutorial_completed", False):
            self.settings["tutorial_completed"] = True
            save_settings(self.settings)

    def apply_startup_window_mode(self):
        """Apply the saved display mode after the main window has been mapped."""
        mode = self.settings.get("startup_window_mode", "Maximised")
        try:
            self.attributes("-fullscreen", False)
            if mode == "Full screen":
                self.attributes("-fullscreen", True)
            elif mode == "Windowed":
                self.state("normal")
                self.geometry("1380x900")
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
        if self.settings.get("shortcut_prompted") and not ONBOARDING_TEST_MODE:
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
        install_accent_spotlight(self, COLOUR_ACCENTS.get(ACTIVE_COLOUR_THEME, COLOUR_ACCENTS["Black"])[0], GLASS_KEY if sys.platform=="win32" else ("#F0F0F0" if ctk.get_appearance_mode()=="Light" else "#101012"))
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=224, corner_radius=26, fg_color=("#F3F3F3", "#1B1B1B"), border_width=1, border_color=("#DBDBDB", "#404040"))
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(14, 8), pady=14)
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text="MARKET\nINSIGHT", font=app_font(size=25, weight="bold"),
                     text_color=(palette_color("#434343"), palette_color("#D7D7D7")), justify="left").pack(anchor="w", padx=22, pady=(28, 30))
        self.nav_buttons = {}
        for label in ["Overview", "What's New", "Market Hours", "Watchlist", "Economic Calendar", "Price Alerts", "Trading Journal", "Settings", "About"]:
            btn = ctk.CTkButton(self.sidebar, text=label, anchor="w", height=42, corner_radius=12,
                                fg_color="transparent", text_color=(palette_color("#4F4F4F"), palette_color("#E0E0E0")),
                                hover_color=(palette_color("#D9D9D9"), palette_color("#383838")),
                                command=lambda name=label: self.show_page(name))
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[label] = btn
        side_info = ctk.CTkScrollableFrame(
            self.sidebar, width=174, corner_radius=16,
            fg_color=("#E9E9E9", "#282828"),
            scrollbar_button_color=(palette_color("#BBBBBB"), palette_color("#585858"))
        )
        side_info.pack(fill="both", expand=True, padx=10, pady=(18, 10))
        ctk.CTkLabel(side_info, text="ACCOUNT CONNECTION",
                     font=app_font(size=12, weight="bold"),
                     text_color=(palette_color("#7B7B7B"), palette_color("#B0B0B0"))).pack(anchor="w", padx=8, pady=(10, 4))
        saved_key, saved_secret = get_alpaca_credentials()
        connected = bool(saved_key and saved_secret)
        ctk.CTkLabel(side_info, text="●  Alpaca connected" if connected else "○  Alpaca not connected",
                     font=app_font(size=13, weight="bold"),
                     text_color=(palette_color("#757575"), palette_color("#BFBFBF")) if connected else (palette_color("#808080"), palette_color("#AFAFAF")),
                     justify="left").pack(anchor="w", padx=8, pady=3)
        key_hint = ("Key ID: ••••" + saved_key[-4:]) if connected else "API keys not saved"
        ctk.CTkLabel(side_info, text=key_hint, font=app_font(size=12, weight="bold"),
                     text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))).pack(anchor="w", padx=8, pady=(0, 10))
        ctk.CTkLabel(side_info, text="YOUR TRADING PLATFORM",
                     font=app_font(size=12, weight="bold"),
                     text_color=(palette_color("#7B7B7B"), palette_color("#B0B0B0"))).pack(anchor="w", padx=8, pady=(8, 4))
        ctk.CTkLabel(side_info, text=self.settings.get("selected_platform") or "Not selected",
                     font=app_font(size=13, weight="bold"),
                     text_color=(palette_color("#4F4F4F"), palette_color("#DCDCDC"))).pack(anchor="w", padx=8, pady=(0, 10))
        ctk.CTkLabel(side_info, text="QUICK LINKS",
                     font=app_font(size=12, weight="bold"),
                     text_color=(palette_color("#7B7B7B"), palette_color("#B0B0B0"))).pack(anchor="w", padx=8, pady=(8, 4))
        for link_name, link_url in [
            ("Alpaca dashboard ↗", "https://app.alpaca.markets/"),
            ("TradingView ↗", "https://www.tradingview.com/"),
            ("Yahoo Finance ↗", "https://finance.yahoo.com/"),
            ("Alpaca market data ↗", "https://docs.alpaca.markets/docs/about-market-data-api"),
        ]:
            ctk.CTkButton(side_info, text=link_name, anchor="w", height=30,
                          corner_radius=12, fg_color="transparent",
                          text_color=(palette_color("#616161"), palette_color("#C3C3C3")),
                          hover_color=(palette_color("#D1D1D1"), palette_color("#3C3C3C")),
                          font=app_font(size=12, weight="bold"),
                          command=lambda url=link_url: webbrowser.open(url)
                          ).pack(fill="x", padx=4, pady=2)
        ctk.CTkLabel(self.sidebar, text="Market Insight  •  Research only  •  Adrian Vale",
                     font=app_font(size=12, weight="bold"), text_color=(palette_color("#7F7F7F"), palette_color("#929292")),
                     justify="left").pack(side="bottom", anchor="w", padx=14, pady=(8, 4))
        creator_actions = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        creator_actions.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
        ctk.CTkButton(creator_actions, text="My website ↗", height=31, corner_radius=10,
                      fg_color="transparent", hover_color=(palette_color("#D9D9D9"), palette_color("#383838")),
                      text_color=(palette_color("#555555"), palette_color("#D7D7D7")),
                      command=lambda: webbrowser.open(PERSONAL_SITE)).pack(fill="x", padx=2, pady=2)
        ctk.CTkButton(creator_actions, text="Donate · Ko-fi ↗", height=31, corner_radius=10,
                      fg_color=COLOUR_ACCENTS.get(ACTIVE_COLOUR_THEME, COLOUR_ACCENTS["Black"])[0],
                      hover_color=COLOUR_ACCENTS.get(ACTIVE_COLOUR_THEME, COLOUR_ACCENTS["Black"])[1],
                      text_color="#202020", command=lambda: webbrowser.open(KOFI_URL)).pack(fill="x", padx=2, pady=2)

        self.main = ctk.CTkFrame(self, corner_radius=24, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=(8, 14), pady=14)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(header, text="Market overview", font=app_font(size=29, weight="bold"),
                                       text_color=(palette_color("#313131"), palette_color("#ECECEC")))
        self.page_title.grid(row=0, column=0, sticky="w")
        self.status = ctk.CTkLabel(header, text="Ready", corner_radius=16, padx=14, pady=8,
                                   fg_color=(palette_color("#E3E3E3"), palette_color("#393939")), text_color=(palette_color("#757575"), palette_color("#BFBFBF")))
        self.status.grid(row=0, column=1, sticky="e")

        self.pages = {}
        for name in ["Overview", "What's New", "Market Hours", "Watchlist", "Economic Calendar", "Price Alerts", "Trading Journal", "Settings", "About"]:
            frame = ctk.CTkScrollableFrame(self.main, corner_radius=24, border_width=1, border_color=(palette_color("#E2E2E2"), palette_color("#3F3F3F")), fg_color="transparent")
            frame.grid(row=1, column=0, sticky="nsew", padx=(0, 2), pady=(0, 2))
            self.pages[name] = frame
        self._build_overview()
        self._build_whats_new()
        self._build_market_hours()
        self._build_watchlist()
        self._build_economic_calendar()
        self._build_price_alerts()
        self._build_trading_journal()
        self._build_settings()
        self._build_about()
        self.show_page("Overview")
        self.after(350, self.apply_liquid_glass)
        # Global bindings work even when a child control has keyboard focus.
        self.bind_all("<F11>", self._toggle_fullscreen)
        self.bind_all("<Escape>", self._exit_fullscreen)

    def card(self, parent, title, subtitle=None, wraplength=None):
        frame = ctk.CTkFrame(parent, corner_radius=24, border_width=1, border_color=("#404040", "#404040"), fg_color=("#FBFBFB", "#1F1F1F"))
        frame.pack(fill="x", padx=14, pady=10)
        heading = ctk.CTkLabel(frame, text=title, font=app_font(size=19, weight="bold"),
                               text_color=(palette_color("#464646"), palette_color("#DCDCDC")), justify="left")
        heading.pack(anchor="w", fill="x", padx=18, pady=(14, 3))
        self._fit_text_to_width(heading, frame, 40)
        if subtitle:
            description = ctk.CTkLabel(frame, text=subtitle, font=app_font(size=13, weight="bold"),
                                       text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9")), justify="left")
            description.pack(anchor="w", fill="x", padx=18, pady=(0, 9))
            self._fit_text_to_width(description, frame, 40)
        return frame

    def _build_overview(self):
        page = self.pages["Overview"]
        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkButton(actions, text="Scan watchlist", height=42, corner_radius=16,
                      command=self.start_scan).pack(side="left")
        ctk.CTkButton(actions, text="Trade planner", height=40, corner_radius=12,
                      fg_color=(palette_color("#E3E3E3"), palette_color("#404040")),
                      text_color=(palette_color("#676767"), palette_color("#E3E3E3")),
                      command=self.open_trade_planner).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="Open highest-rated stock", height=40, corner_radius=12,
                      fg_color=(palette_color("#E3E3E3"), palette_color("#404040")), text_color=(palette_color("#676767"), palette_color("#E3E3E3")),
                      command=self.open_top_result).pack(side="left", padx=8)
        self.scan_info = ctk.CTkLabel(
            actions, text="50 stocks included",
            font=app_font(size=15, weight="bold"),
            text_color=(palette_color("#E4E4E4"), palette_color("#E4E4E4")),
            fg_color=(palette_color("#595959"), palette_color("#3D3D3D")),
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
                                       font=app_font(size=31, weight="bold"))
        self.top_symbol.pack(anchor="w", fill="x", padx=18, pady=(6, 0))
        self._fit_text_to_width(self.top_symbol, top, 40)
        self.top_details = ctk.CTkLabel(top, text="Connect Alpaca in Settings, then scan your watchlist to see available live prices.",
                                        font=app_font(size=13, weight="bold"),
                                        text_color=(palette_color("#7B7B7B"), palette_color("#B0B0B0")), justify="left")
        self.top_details.pack(anchor="w", fill="x", padx=18, pady=(2, 16))
        self._fit_text_to_width(self.top_details, top, 40)

        self.watch_card = self.card(left_column, "Watchlist highlights", "The highest-scoring stocks from your latest scan")
        self.watch_table = ctk.CTkScrollableFrame(self.watch_card, height=260, corner_radius=12, fg_color=(palette_color("#F7F7F7"), palette_color("#2A2A2A")))
        self.watch_table.pack(fill="x", padx=16, pady=(8, 16))

        caution = self.card(left_column, "Stocks to review", "Stocks showing two or more warning signs. These are prompts to take a closer look, not instructions to buy or sell.")
        self.caution_text = ctk.CTkScrollableFrame(caution, height=170, corner_radius=12, fg_color=(palette_color("#F7F7F7"), palette_color("#2A2A2A")))
        self.caution_text.pack(fill="x", padx=16, pady=(8, 16))

        pulse = self.card(right_column, "Market pulse", "Daily market direction from Yahoo Finance. Updates when you scan.")
        self.market_pulse_labels = {}
        for symbol, name in [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("DIA", "Dow Jones"), ("IWM", "Russell 2000"), ("^VIX", "Volatility (VIX)")]:
            line = ctk.CTkFrame(pulse, fg_color="transparent")
            line.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(line, text=name, font=app_font(size=13, weight="bold"), text_color=(palette_color("#6A6A6A"), palette_color("#BBBBBB"))).pack(side="left")
            value = ctk.CTkLabel(line, text="Waiting for scan", font=app_font(size=13, weight="bold"), text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3")))
            value.pack(side="right")
            self.market_pulse_labels[symbol] = value
        self.market_breadth = ctk.CTkLabel(pulse, text="Watchlist breadth: waiting for scan", font=app_font(size=13, weight="bold"), text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3")), justify="left")
        self.market_breadth.pack(anchor="w", padx=14, pady=(8, 12))
        checklist = self.card(right_column, "Before you trade", "A quick discipline check")
        checklist_items = ["Is there a clear reason for this trade?", "Have I checked the wider market trend?", "Is my stop level defined before entry?", "Does the position fit my risk limit?", "Is the potential reward worth the risk?", "Am I avoiding an emotional decision?"]
        for item in checklist_items:
            ctk.CTkLabel(checklist, text="•  " + item, font=app_font(size=12, weight="bold"), text_color=(palette_color("#6A6A6A"), palette_color("#BBBBBB")), justify="left", wraplength=260).pack(anchor="w", padx=14, pady=3)
        calculator = self.card(right_column, "Position size calculator",
                               "Estimate how many shares may fit your balance and risk limit. This is a guide only; it does not place trades.",
                               wraplength=270)
        balance_heading = ctk.CTkFrame(calculator, fg_color="transparent")
        balance_heading.pack(fill="x", padx=14, pady=(8, 3))
        self.balance_label = ctk.CTkLabel(
            balance_heading, text="Account balance ({})".format(self.settings.get("currency", "USD")),
            text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3"))
        )
        self.balance_label.pack(anchor="w")
        self.currency_menu = styled_settings_dropdown(
            calculator, values=list(CURRENCY_OPTIONS.values()),
            command=self.change_calculator_currency
        )
        selected_currency = self.settings.get("currency", "USD")
        self.currency_menu.set(CURRENCY_OPTIONS.get(selected_currency, CURRENCY_OPTIONS["USD"]))
        self.currency_menu.pack(anchor="w", padx=14, pady=(0, 8))
        self.balance_entry = ctk.CTkEntry(calculator, placeholder_text="e.g. 1000")
        self.balance_entry.insert(0, str(self.settings["balance"]))
        self.balance_entry.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(calculator, text="Risk per trade (%)",
                     text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3"))).pack(anchor="w", padx=14, pady=(2, 3))
        self.risk_entry = ctk.CTkEntry(calculator, placeholder_text="e.g. 1")
        self.risk_entry.insert(0, str(self.settings["risk_percent"]))
        self.risk_entry.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(calculator, text="Save calculator settings",
                      command=self.save_calculator_settings).pack(fill="x", padx=14, pady=(4, 10))
        self.calc_output = ctk.CTkLabel(
            calculator,
            text="Run a scan to see example position size and price levels for the highest-scoring stock.",
            font=app_font(size=13, weight="bold"), text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9")), justify="left"
        )
        self.calc_output.pack(anchor="w", fill="x", padx=14, pady=(0, 16))
        self._fit_text_to_width(self.calc_output, calculator, 32)

        footer = ctk.CTkFrame(page, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(2, 10))
        ctk.CTkLabel(
            footer, text="ADRIAN VALE  ·  MARKET INSIGHT",
            font=app_font(size=13, weight="bold"),
            text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3"))
        ).pack(side="left")
        creator_links = ctk.CTkFrame(footer, fg_color="transparent")
        creator_links.pack(side="right")
        ctk.CTkButton(
            creator_links, text="YouTube  ↗", width=100, height=28,
            corner_radius=12, fg_color="transparent",
            text_color=(palette_color("#757575"), palette_color("#BFBFBF")),
            hover_color=(palette_color("#E3E3E3"), palette_color("#404040")),
            command=lambda: webbrowser.open("https://www.youtube.com/@Adrianvaleitl")
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            creator_links, text="TikTok  ↗", width=90, height=28,
            corner_radius=12, fg_color="transparent",
            text_color=(palette_color("#757575"), palette_color("#BFBFBF")),
            hover_color=(palette_color("#E3E3E3"), palette_color("#404040")),
            command=lambda: webbrowser.open("https://www.tiktok.com/@adrianvaleitl")
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            creator_links, text="☕ Donate on Ko-fi  ↗", width=150, height=28,
            corner_radius=12,
            fg_color=(palette_color("#D9D9D9"), palette_color("#464646")),
            hover_color=(palette_color("#CACACA"), palette_color("#545454")),
            text_color=(palette_color("#464646"), palette_color("#E4E4E4")),
            command=lambda: webbrowser.open("https://ko-fi.com/marketinsight")
        ).pack(side="right", padx=(6, 0))


    def _build_whats_new(self):
        page = self.pages["What's New"]
        hero = ctk.CTkFrame(
            page, corner_radius=24,
            fg_color=(palette_color("#EEEEEE"), palette_color("#292929")),
            border_width=1,
            border_color=(palette_color("#DADADA"), palette_color("#414141"))
        )
        hero.pack(fill="x", padx=14, pady=(14, 18))
        head = ctk.CTkFrame(hero, fg_color="transparent")
        head.pack(fill="x", padx=22, pady=(20, 8))
        ctk.CTkLabel(
            head, text=RELEASE_NOTES[0]["version"],
            font=app_font(size=26, weight="bold"),
            text_color=COLOUR_ACCENTS.get(ACTIVE_COLOUR_THEME, COLOUR_ACCENTS["Black"])[0]
        ).pack(side="left")
        ctk.CTkLabel(
            head, text="LATEST RELEASE",
            font=app_font(size=10, weight="bold"),
            text_color=(palette_color("#777777"), palette_color("#B8B8B8"))
        ).pack(side="right")
        ctk.CTkLabel(
            hero, text=RELEASE_NOTES[0]["title"],
            font=app_font(size=19, weight="bold"),
            text_color=(palette_color("#303030"), palette_color("#EEEEEE"))
        ).pack(anchor="w", padx=22, pady=(0, 4))
        ctk.CTkLabel(
            hero, text=RELEASE_NOTES[0]["date"] + "  ·  Windows desktop",
            font=app_font(size=11, weight="bold"),
            text_color=(palette_color("#777777"), palette_color("#AFAFAF"))
        ).pack(anchor="w", padx=22)
        ctk.CTkLabel(
            hero,
            text="A focused summary of what changed, why it matters and which earlier releases introduced the tools you already use.",
            font=app_font(size=12, weight="bold"),
            justify="left", anchor="w", wraplength=850,
            text_color=(palette_color("#686868"), palette_color("#C3C3C3"))
        ).pack(fill="x", padx=22, pady=(12, 14))
        for item in RELEASE_NOTES[0]["items"]:
            row = ctk.CTkFrame(hero, fg_color="transparent")
            row.pack(fill="x", padx=22, pady=3)
            ctk.CTkLabel(
                row, text="✓", width=22, anchor="w",
                font=app_font(size=12, weight="bold"),
                text_color=COLOUR_ACCENTS.get(ACTIVE_COLOUR_THEME, COLOUR_ACCENTS["Black"])[0]
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=item, anchor="w", justify="left", wraplength=820,
                font=app_font(size=11, weight="bold"),
                text_color=(palette_color("#555555"), palette_color("#D0D0D0"))
            ).pack(side="left", fill="x", expand=True)
        ctk.CTkFrame(hero, height=10, fg_color="transparent").pack()
        ctk.CTkLabel(
            page, text="RELEASE HISTORY",
            font=app_font(size=10, weight="bold"),
            text_color=(palette_color("#777777"), palette_color("#AFAFAF"))
        ).pack(anchor="w", padx=18, pady=(0, 5))
        for release in RELEASE_NOTES[1:]:
            card = ctk.CTkFrame(
                page, corner_radius=18,
                fg_color=(palette_color("#F0F0F0"), palette_color("#242424")),
                border_width=1,
                border_color=(palette_color("#E0E0E0"), palette_color("#3A3A3A"))
            )
            card.pack(fill="x", padx=14, pady=5)
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=18, pady=(13, 4))
            ctk.CTkLabel(
                header, text=release["version"],
                font=app_font(size=14, weight="bold"),
                text_color=COLOUR_ACCENTS.get(ACTIVE_COLOUR_THEME, COLOUR_ACCENTS["Black"])[0]
            ).pack(side="left")
            ctk.CTkLabel(
                header, text=release["date"],
                font=app_font(size=10, weight="bold"),
                text_color=(palette_color("#888888"), palette_color("#A9A9A9"))
            ).pack(side="right")
            ctk.CTkLabel(
                card, text=release["title"],
                font=app_font(size=13, weight="bold"),
                text_color=(palette_color("#414141"), palette_color("#DEDEDE"))
            ).pack(anchor="w", padx=18, pady=(0, 5))
            for item in release["items"]:
                ctk.CTkLabel(
                    card, text="•  " + item, justify="left", anchor="w",
                    wraplength=850, font=app_font(size=11, weight="bold"),
                    text_color=(palette_color("#686868"), palette_color("#C3C3C3"))
                ).pack(fill="x", padx=22, pady=2)
            ctk.CTkFrame(card, height=9, fg_color="transparent").pack()

    def _build_market_hours(self):
        page = self.pages["Market Hours"]
        self.fx_schedule_frame = self.card(
            page, "Forex sessions",
            "The global forex market runs around the clock on weekdays. Session times below are converted into UK local time."
        )
        self.fx_overlap_frame = self.card(
            page, "Key forex overlaps",
            "Overlaps often bring more participation and liquidity, but can also mean faster price moves and higher risk."
        )
        self.stock_schedule_frame = self.card(
            page, "Major stock exchanges",
            "Regular cash-market hours, excluding exchange holidays and special early closes."
        )
        tips = self.card(
            page, "Commonly watched trading windows",
            "These are educational reference periods, not guaranteed profitable entry times. Suitability depends on the instrument, strategy, news and risk limits."
        )
        notes = [
            ("London open", "08:00–10:00 UK", "Often active for GBP, EUR and European markets."),
            ("London–New York overlap", "Shown above; shifts with daylight saving", "Often the busiest forex period for major pairs such as EUR/USD and GBP/USD."),
            ("US stock open", "First 60–90 minutes after the open", "Often elevated volume and volatility; the first move can be erratic."),
            ("US stock close", "Final 60 minutes", "Can see increased activity as traders adjust positions."),
            ("Asian session", "Tokyo morning and Sydney–Tokyo overlap", "More relevant to JPY, AUD and NZD pairs.")
        ]
        for heading, period, detail in notes:
            row = ctk.CTkFrame(tips, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=5)
            ctk.CTkLabel(row, text=heading, width=180, anchor="w",
                         font=app_font(size=13, weight="bold")).pack(side="left")
            ctk.CTkLabel(row, text=period, width=235, anchor="w",
                         font=app_font(size=13, weight="bold")).pack(side="left")
            label = ctk.CTkLabel(row, text=detail, anchor="w", justify="left",
                         font=app_font(size=12, weight="bold"),
                         text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9")))
            label.pack(side="left", fill="x", expand=True)
            self._fit_text_to_width(label, row, 440, 150)
        warning = ctk.CTkLabel(
            tips, text="Higher activity is not the same as a better trade. Check spreads, scheduled economic news, instrument-specific hours and your risk plan.",
            font=app_font(size=12, weight="bold"), justify="left",
            text_color=(palette_color("#808080"), palette_color("#B0B0B0"))
        )
        warning.pack(anchor="w", fill="x", padx=18, pady=(8, 14))
        self._fit_text_to_width(warning, tips, 40)
        ctk.CTkButton(page, text="Refresh market times", height=38,
                      command=self.refresh_market_hours).pack(anchor="e", padx=18, pady=8)
        self.market_hours_updated = ctk.CTkLabel(page, text="", font=app_font(size=12, weight="bold"),
            text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9")))
        self.market_hours_updated.pack(anchor="e", padx=20, pady=(0, 14))
        self.refresh_market_hours()

    def refresh_market_hours(self):
        if not hasattr(self, "fx_schedule_frame"):
            return
        for frame in (self.fx_schedule_frame, self.fx_overlap_frame, self.stock_schedule_frame):
            for child in frame.winfo_children():
                child.destroy()
        now = datetime.now(ZoneInfo("Europe/London"))
        today = now.date()
        ctk.CTkLabel(self.fx_schedule_frame, text="UK time • " + now.strftime("%A %d %B %Y"),
                     font=app_font(size=12, weight="bold")).pack(anchor="w", padx=14, pady=(0, 6))
        sessions = [
            ("Sydney", "Australia/Sydney", (7, 0), (16, 0), "AUD / NZD"),
            ("Tokyo", "Asia/Tokyo", (9, 0), (18, 0), "JPY / AUD / NZD"),
            ("London", "Europe/London", (8, 0), (17, 0), "GBP / EUR / CHF"),
            ("New York", "America/New_York", (8, 0), (17, 0), "USD / CAD")
        ]
        for name, zone, start, end, pairs in sessions:
            row = ctk.CTkFrame(self.fx_schedule_frame, corner_radius=12,
                fg_color=(palette_color("#E7E7E7"), palette_color("#393939")))
            row.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(row, text=name, width=115, anchor="w",
                         font=app_font(size=14, weight="bold")).pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(row, text=_uk_market_range(today, zone, start, end), width=190,
                         anchor="w", font=app_font(size=14, weight="bold")).pack(side="left")
            ctk.CTkLabel(row, text="Main pairs: " + pairs, anchor="w",
                         font=app_font(size=12, weight="bold"),
                         text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))).pack(side="left", padx=8)

        overlaps = [
            ("Sydney–Tokyo", "Australia/Sydney", ((7, 0), (16, 0)), "Asia/Tokyo", ((9, 0), (18, 0)), "AUD / NZD / JPY pairs"),
            ("Tokyo–London", "Asia/Tokyo", ((9, 0), (18, 0)), "Europe/London", ((8, 0), (17, 0)), "JPY pairs / European handover"),
            ("London–New York", "Europe/London", ((8, 0), (17, 0)), "America/New_York", ((8, 0), (17, 0)), "EUR / GBP / USD major pairs")
        ]
        for name, zone_a, hours_a, zone_b, hours_b, pairs in overlaps:
            row = ctk.CTkFrame(self.fx_overlap_frame, corner_radius=12,
                fg_color=(palette_color("#E7E7E7"), palette_color("#393939")))
            row.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(row, text=name, width=155, anchor="w",
                         font=app_font(size=14, weight="bold")).pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(row, text=_uk_market_overlap(today, zone_a, hours_a, zone_b, hours_b), width=160,
                         anchor="w", font=app_font(size=14, weight="bold")).pack(side="left")
            ctk.CTkLabel(row, text=pairs, anchor="w", font=app_font(size=12, weight="bold"),
                         text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))).pack(side="left", padx=8)

        exchanges = [
            ("London Stock Exchange", "Europe/London", [((8, 0), (16, 30))], "FTSE 100 / UK shares", "08:00–09:30 and 15:30–16:30 UK"),
            ("NYSE / Nasdaq", "America/New_York", [((9, 30), (16, 0))], "S&P 500 / Nasdaq 100 / US shares", "First 60–90 minutes and final hour"),
            ("Tokyo Stock Exchange", "Asia/Tokyo", [((9, 0), (11, 30)), ((12, 30), (15, 30))], "Nikkei 225 / Japanese shares", "First 60–90 minutes or final hour"),
            ("Hong Kong Exchange", "Asia/Hong_Kong", [((9, 30), (12, 0)), ((13, 0), (16, 0))], "Hang Seng / Hong Kong shares", "First 60–90 minutes or final hour")
        ]
        for name, zone, periods, instruments, best in exchanges:
            hours = " / ".join(_uk_market_range(today, zone, start, end) for start, end in periods)
            row = ctk.CTkFrame(self.stock_schedule_frame, corner_radius=12,
                fg_color=(palette_color("#E7E7E7"), palette_color("#393939")))
            row.pack(fill="x", padx=10, pady=4)
            ctk.CTkLabel(row, text=name, font=app_font(size=14, weight="bold"),
                         anchor="w").pack(anchor="w", padx=12, pady=(9, 2))
            ctk.CTkLabel(row, text="Open: " + hours + " UK",
                         font=app_font(size=13, weight="bold"), anchor="w").pack(anchor="w", padx=12)
            ctk.CTkLabel(row, text=instruments + " • Commonly watched: " + best,
                         font=app_font(size=12, weight="bold"), anchor="w", justify="left",
                         text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))).pack(anchor="w", padx=12, pady=(2, 9))
        self.market_hours_updated.configure(text="Times refreshed: " + now.strftime("%H:%M:%S UK"))

    def _build_watchlist(self):
        page = self.pages["Watchlist"]
        card = self.card(page, "Your watchlist", "Add the stock ticker symbols you want to track. Separate each symbol with a comma. You can add up to 100.")
        self.watch_input = ctk.CTkTextbox(card, height=120, corner_radius=10)
        self.watch_input.pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(card, text="Save watchlist", command=self.save_watchlist).pack(anchor="e", padx=16, pady=(0, 14))
        summary = self.card(page, "Scan snapshot", "A quick summary of the latest completed scan.")
        self.scan_summary_labels = {}
        summary_grid = ctk.CTkFrame(summary, fg_color="transparent")
        summary_grid.pack(fill="x", padx=12, pady=(4, 12))
        for index, (key, heading) in enumerate([
            ("average", "AVERAGE SCORE"), ("best", "BEST DAILY MOVE"),
            ("worst", "WORST DAILY MOVE"), ("volume", "HIGH VOLUME")
        ]):
            tile = ctk.CTkFrame(summary_grid, corner_radius=12, fg_color=(palette_color("#E5E5E5"), palette_color("#3B3B3B")))
            tile.grid(row=0, column=index, sticky="nsew", padx=4, pady=4)
            summary_grid.grid_columnconfigure(index, weight=1)
            ctk.CTkLabel(tile, text=heading, font=app_font(size=10, weight="bold"),
                         text_color=(palette_color("#7B7B7B"), palette_color("#B0B0B0"))).pack(anchor="w", padx=10, pady=(9, 2))
            value = ctk.CTkLabel(tile, text="—", font=app_font(size=17, weight="bold"))
            value.pack(anchor="w", padx=10, pady=(0, 9))
            self.scan_summary_labels[key] = value

        results = self.card(page, "Results from your latest scan", "Search, sort and filter your scanned symbols, or export the results.")
        controls = ctk.CTkFrame(results, fg_color="transparent")
        controls.pack(fill="x", padx=14, pady=(6, 4))
        self.results_search = ctk.CTkEntry(controls, placeholder_text="Search ticker or company…", width=220)
        self.results_search.pack(side="left", padx=(0, 7), pady=4)
        self.results_search.bind("<KeyRelease>", lambda _event: self._refresh_results_view())
        self.results_sort = styled_settings_dropdown(
            controls, ["Highest score", "Biggest daily gain", "Biggest daily loss", "Highest RSI", "Highest volume"],
            command=lambda _value: self._refresh_results_view()
        )
        self.results_sort.configure(width=175)
        self.results_sort.set("Highest score")
        self.results_sort.pack(side="left", padx=4, pady=4)
        self.results_filter = styled_settings_dropdown(
            controls, ["All stocks", "Positive today", "Negative today", "Score 70+", "With warnings"],
            command=lambda _value: self._refresh_results_view()
        )
        self.results_filter.configure(width=155)
        self.results_filter.set("All stocks")
        self.results_filter.pack(side="left", padx=4, pady=4)
        ctk.CTkButton(controls, text="Export CSV", width=105, command=self.export_scan_csv).pack(side="right", padx=4, pady=4)
        self.results_count = ctk.CTkLabel(results, text="No scan results yet", font=app_font(size=12, weight="bold"),
                                          text_color=(palette_color("#7B7B7B"), palette_color("#B0B0B0")))
        self.results_count.pack(anchor="w", padx=18, pady=(0, 4))
        self.results_text = ctk.CTkScrollableFrame(results, height=520, corner_radius=12, fg_color=(palette_color("#F7F7F7"), palette_color("#2A2A2A")))
        self.results_text.pack(fill="x", padx=16, pady=(4, 16))

        folders = self.card(page, "Watchlist folders", "Group symbols into your own lists such as Tech, ETFs or Long-term. Folders organise your watchlist; they do not remove symbols from scans.")
        folder_row = ctk.CTkFrame(folders, fg_color="transparent")
        folder_row.pack(fill="x", padx=16, pady=6)
        self.watch_folder_name_entry = ctk.CTkEntry(folder_row, placeholder_text="Folder name", width=190)
        self.watch_folder_name_entry.pack(side="left", padx=(0, 8))
        self.watch_folder_symbols_entry = ctk.CTkEntry(folder_row, placeholder_text="Tickers, comma separated", width=300)
        self.watch_folder_symbols_entry.pack(side="left", padx=4)
        ctk.CTkButton(folder_row, text="Save folder", command=self._save_watchlist_folder).pack(side="left", padx=6)
        self.watch_folder_menu = styled_settings_dropdown(folders, values=["All folders"] + sorted(self.settings.get("watchlist_folders", {}).keys()), command=self._load_watchlist_folder)
        self.watch_folder_menu.pack(anchor="w", padx=16, pady=(4, 12))

        presets = self.card(page, "Custom scan presets", "Save your current watchlist and minimum score threshold so you can reuse a setup later.")
        preset_row = ctk.CTkFrame(presets, fg_color="transparent")
        preset_row.pack(fill="x", padx=16, pady=8)
        self.preset_name_entry = ctk.CTkEntry(preset_row, placeholder_text="Preset name", width=190)
        self.preset_name_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(preset_row, text="Save current setup", command=self._save_scan_preset).pack(side="left", padx=4)
        self.preset_menu = styled_settings_dropdown(presets, values=sorted(self.settings.get("scan_presets", {}).keys()) or ["No presets saved"], command=self._apply_scan_preset)
        self.preset_menu.pack(anchor="w", padx=16, pady=(4, 12))

        notes = self.card(page, "Ticker research notes", "Keep your own research notes locally against a ticker. Notes are not trading advice or a signal.")
        note_row = ctk.CTkFrame(notes, fg_color="transparent")
        note_row.pack(fill="x", padx=16, pady=6)
        self.note_symbol_entry = ctk.CTkEntry(note_row, placeholder_text="Ticker (e.g. AAPL)", width=180)
        self.note_symbol_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(note_row, text="Load note", command=self._load_ticker_note).pack(side="left", padx=4)
        ctk.CTkButton(note_row, text="Save note", command=self._save_ticker_note).pack(side="left", padx=4)
        self.ticker_notes_text = ctk.CTkTextbox(notes, height=115, corner_radius=10)
        self.ticker_notes_text.pack(fill="x", padx=16, pady=(2, 14))

        history = self.card(page, "Scan history", "A local record of recent completed scans, with the strongest results from each run.")
        self.scan_history_text = ctk.CTkTextbox(history, height=155, corner_radius=10)
        self.scan_history_text.pack(fill="x", padx=16, pady=(4, 14))
        self._render_scan_history()

        briefing = self.card(page, "Daily market briefing", "A quick summary generated from your latest completed scan. It updates when a scan finishes.")
        self.daily_briefing_text = ctk.CTkTextbox(briefing, height=165, corner_radius=10)
        self.daily_briefing_text.pack(fill="x", padx=16, pady=(4, 14))
        self._update_daily_briefing(self.results)


    def _save_watchlist_folder(self):
        name = self.watch_folder_name_entry.get().strip()
        symbols = list(dict.fromkeys(x.strip().upper() for x in self.watch_folder_symbols_entry.get().replace("\n", ",").split(",") if x.strip()))
        if not name or not symbols:
            self.status.configure(text="Enter a folder name and at least one ticker.")
            return
        folders = self.settings.setdefault("watchlist_folders", {})
        folders[name] = symbols[:100]
        save_settings(self.settings)
        self.watch_folder_menu.configure(values=["All folders"] + sorted(folders))
        self.watch_folder_menu.set(name)
        self.status.configure(text="Saved watchlist folder: " + name)

    def _load_watchlist_folder(self, name):
        if name == "All folders":
            self._refresh_watchlist_text()
            return
        symbols = self.settings.get("watchlist_folders", {}).get(name, [])
        self.watch_folder_name_entry.delete(0, "end")
        self.watch_folder_name_entry.insert(0, name)
        self.watch_folder_symbols_entry.delete(0, "end")
        self.watch_folder_symbols_entry.insert(0, ", ".join(symbols))

    def _save_scan_preset(self):
        name = self.preset_name_entry.get().strip()
        if not name:
            self.status.configure(text="Enter a name for this scan preset.")
            return
        presets = self.settings.setdefault("scan_presets", {})
        presets[name] = {
            "threshold": int(self.settings.get("threshold", 70)),
            "watchlist": list(self.settings.get("watchlist", DEFAULT_TICKERS)),
            "sort": self.results_sort.get() if hasattr(self, "results_sort") else "Highest score",
            "filter": self.results_filter.get() if hasattr(self, "results_filter") else "All stocks",
        }
        save_settings(self.settings)
        self.preset_menu.configure(values=sorted(presets))
        self.preset_menu.set(name)
        self.status.configure(text="Saved scan preset: " + name)

    def _apply_scan_preset(self, name):
        preset = self.settings.get("scan_presets", {}).get(name)
        if not preset:
            return
        self.settings["threshold"] = int(preset.get("threshold", 70))
        self.settings["watchlist"] = list(preset.get("watchlist", DEFAULT_TICKERS))[:100]
        save_settings(self.settings)
        self._refresh_watchlist_text()
        if hasattr(self, "threshold_menu"):
            self.threshold_menu.set(str(self.settings["threshold"]))
        if hasattr(self, "results_sort"):
            self.results_sort.set(preset.get("sort", "Highest score"))
            self.results_filter.set(preset.get("filter", "All stocks"))
            self._refresh_results_view()
        self.status.configure(text="Applied scan preset: " + name)

    def _save_ticker_note(self):
        symbol = self.note_symbol_entry.get().strip().upper()
        note = self.ticker_notes_text.get("1.0", "end").strip()
        if not symbol:
            self.status.configure(text="Enter a ticker symbol before saving a note.")
            return
        self.settings.setdefault("ticker_notes", {})[symbol] = {"note": note, "updated": datetime.now().isoformat(timespec="minutes")}
        save_settings(self.settings)
        self.status.configure(text="Research note saved for " + symbol)

    def _load_ticker_note(self):
        symbol = self.note_symbol_entry.get().strip().upper()
        if not symbol:
            self.status.configure(text="Enter a ticker symbol to load its note.")
            return
        record = self.settings.get("ticker_notes", {}).get(symbol, {})
        self.ticker_notes_text.delete("1.0", "end")
        self.ticker_notes_text.insert("1.0", record.get("note", "") if isinstance(record, dict) else str(record))
        self.status.configure(text="Loaded research note for " + symbol)

    def _render_scan_history(self):
        if not hasattr(self, "scan_history_text"):
            return
        history = self.settings.get("scan_history", [])
        lines = []
        for item in history[:20]:
            leaders = ", ".join("{} ({})".format(x.get("symbol"), x.get("score")) for x in item.get("leaders", [])) or "No successful results"
            lines.append("{}  ·  {}/{} successful  ·  Leaders: {}".format(item.get("time", ""), item.get("successful", 0), item.get("total", 0), leaders))
        self.scan_history_text.configure(state="normal")
        self.scan_history_text.delete("1.0", "end")
        self.scan_history_text.insert("1.0", "\n".join(lines) if lines else "No completed scans saved yet.")
        self.scan_history_text.configure(state="disabled")

    def _update_daily_briefing(self, results):
        if not hasattr(self, "daily_briefing_text"):
            return
        valid = [(symbol, data) for symbol, data in results.items() if isinstance(data, dict) and "error" not in data]
        valid.sort(key=lambda item: item[1].get("score", 0), reverse=True)
        if not valid:
            message = self.settings.get("daily_briefing") or "Your daily briefing will appear here after your first successful scan."
        else:
            advancing = sum(1 for _, data in valid if data.get("day_change", 0) > 0)
            declining = sum(1 for _, data in valid if data.get("day_change", 0) < 0)
            leaders = ["{}  ·  score {}/100  ·  day {:+.2f}%".format(s, d.get("score", 0), d.get("day_change", 0)) for s, d in valid[:3]]
            cautions = ["{}: {}".format(s, ", ".join(d.get("warnings", [])[:2])) for s, d in valid if d.get("warnings")][:4]
            message = "LATEST SCAN  ·  {}\n".format(datetime.now().strftime("%d %b %Y, %H:%M")) + "Watchlist breadth: {} advancing, {} declining, {} unchanged.\n\nTop scored symbols\n".format(advancing, declining, len(valid)-advancing-declining) + "\n".join(leaders)
            if cautions:
                message += "\n\nCaution flags\n" + "\n".join(cautions)
            message += "\n\nResearch summary only — not a buy or sell recommendation."
        self.daily_briefing_text.configure(state="normal")
        self.daily_briefing_text.delete("1.0", "end")
        self.daily_briefing_text.insert("1.0", message)
        self.daily_briefing_text.configure(state="disabled")
        if valid:
            self.settings["daily_briefing"] = message
            save_settings(self.settings)


    def open_trade_planner(self):
        window=ctk.CTkToplevel(self)
        window.title("Trade Planner")
        window.geometry("760x650")
        window.minsize(650,560)
        window.transient(self)
        window.configure(fg_color=(palette_color("#F0F0F0"),palette_color("#212121")))
        self.card(window,"Trade Planner","Plan risk, stop distance and potential reward before placing an order.")
        form=ctk.CTkFrame(window,fg_color="transparent")
        form.pack(fill="x",padx=20,pady=12)
        fields={}
        for label,default in [("Account balance",str(self.settings.get("balance",1000))),("Risk per trade (%)",str(self.settings.get("risk_percent",1))),("Entry price","100"),("Stop-loss price","96"),("Target price","112")]:
            row=ctk.CTkFrame(form,fg_color="transparent");row.pack(fill="x",pady=5)
            ctk.CTkLabel(row,text=label,width=190,anchor="w",font=app_font(size=13,weight="bold")).pack(side="left")
            entry=ctk.CTkEntry(row,width=220);entry.insert(0,default);entry.pack(side="left")
            fields[label]=entry
        result=ctk.CTkLabel(window,text="Enter your assumptions and calculate a plan.",font=app_font(size=14,weight="bold"),justify="left")
        result.pack(anchor="w",padx=24,pady=14)
        def calculate(save=False):
            try:
                balance=float(fields["Account balance"].get());risk=float(fields["Risk per trade (%)"].get())
                entry=float(fields["Entry price"].get());stop=float(fields["Stop-loss price"].get());target=float(fields["Target price"].get())
                if min(balance,risk,entry,stop,target)<=0 or risk>100 or not stop<entry<target:raise ValueError
                risk_cash=balance*risk/100;distance=entry-stop;shares=int(risk_cash/distance)
                reward=target-entry;ratio=reward/distance;position=shares*entry
                result.configure(text=f"Suggested size: {shares:,} shares\nPosition value: {position:,.2f} {self.settings.get('currency','USD')}\nRisk at stop: {shares*distance:,.2f}\nPotential reward: {shares*reward:,.2f}\nReward-to-risk: {ratio:.2f}:1")
                if save:
                    self.settings.setdefault("trade_plans",[]).insert(0,{"date":datetime.now().strftime("%Y-%m-%d %H:%M"),"entry":entry,"stop":stop,"target":target,"shares":shares,"ratio":round(ratio,2)})
                    self.settings["trade_plans"]=self.settings["trade_plans"][:30]
                    save_settings(self.settings)
                    messagebox.showinfo(APP_NAME,"Trade plan saved on this device.",parent=window)
            except (ValueError,ZeroDivisionError):
                result.configure(text="Check your inputs. Use positive numbers and a long setup where stop < entry < target.")
        actions=ctk.CTkFrame(window,fg_color="transparent");actions.pack(anchor="w",padx=20,pady=8)
        ctk.CTkButton(actions,text="Calculate",command=calculate).pack(side="left",padx=5)
        ctk.CTkButton(actions,text="Save plan",command=lambda:calculate(True)).pack(side="left",padx=5)
        history=self.card(window,"Recent saved plans","Stored locally in your Market Insight settings.")
        for plan in self.settings.get("trade_plans",[])[:8]:
            ctk.CTkLabel(history,text=f"{plan.get('date','')} · {plan.get('shares')} shares · {plan.get('ratio')}:1 reward/risk",font=app_font(size=12,weight="bold")).pack(anchor="w",padx=16,pady=4)
        if not self.settings.get("trade_plans"):
            ctk.CTkLabel(history,text="No saved plans yet.",font=app_font(size=12)).pack(anchor="w",padx=16,pady=(0,12))

    def _build_economic_calendar(self):
        page = self.pages["Economic Calendar"]
        card = self.card(page, "Economic calendar", "Upcoming public economic releases, converted to UK local time.")
        controls = ctk.CTkFrame(card, fg_color="transparent")
        controls.pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(controls, text="Refresh calendar", command=self.refresh_economic_calendar).pack(side="left")
        self.calendar_status = ctk.CTkLabel(controls, text="Ready to load events")
        self.calendar_status.pack(side="left", padx=12)
        self.calendar_frame = ctk.CTkFrame(page, fg_color="transparent")
        self.calendar_frame.pack(fill="x", padx=14, pady=8)
        self.card(page, "Trading around news", "High-impact releases can increase volatility and spreads. This calendar is informational, may be revised or unavailable, and is not a trading signal.")

    def refresh_economic_calendar(self):
        if getattr(self, "_calendar_loading", False):
            return
        self._calendar_loading = True
        self.calendar_status.configure(text="Loading upcoming events…")
        threading.Thread(target=self._calendar_worker, daemon=True).start()

    def _calendar_worker(self):
        try:
            response = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=15)
            response.raise_for_status()
            payload = response.json()
            rows = []
            now = datetime.now(ZoneInfo("Europe/London"))
            for event in payload if isinstance(payload, list) else []:
                try:
                    moment = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
                    if moment.tzinfo is None:
                        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
                    moment = moment.astimezone(ZoneInfo("Europe/London"))
                    if moment >= now:
                        rows.append((moment, str(event.get("impact", "Unknown")), str(event.get("country", "")),
                                     str(event.get("title", "Economic release")),
                                     str(event.get("forecast", "—") or "—"), str(event.get("previous", "—") or "—")))
                except (KeyError, TypeError, ValueError):
                    continue
            rows.sort(key=lambda row: row[0])
            self.after(0, lambda data=rows: self._show_calendar_events(data))
        except Exception:
            self.after(0, lambda: self.calendar_status.configure(text="Calendar unavailable. Check your connection and retry."))
        finally:
            self._calendar_loading = False

    def _show_calendar_events(self, rows):
        for child in self.calendar_frame.winfo_children():
            child.destroy()
        if not rows:
            ctk.CTkLabel(self.calendar_frame, text="No upcoming events were returned for this week.").pack(anchor="w", padx=10, pady=12)
        for moment, impact, country, title, forecast, previous in rows[:80]:
            tile = ctk.CTkFrame(self.calendar_frame, corner_radius=12, fg_color=(palette_color("#EEEEEE"), palette_color("#323232")))
            tile.pack(fill="x", padx=4, pady=4)
            ctk.CTkLabel(tile, text=moment.strftime("%a %d %b · %H:%M") + "  ·  " + impact.upper(),
                         font=app_font(size=12, weight="bold")).pack(anchor="w", padx=12, pady=(8, 2))
            ctk.CTkLabel(tile, text=country + " · " + title, font=app_font(size=14, weight="bold"),
                         justify="left", anchor="w").pack(fill="x", anchor="w", padx=12, pady=2)
            ctk.CTkLabel(tile, text="Forecast: " + forecast + "    Previous: " + previous,
                         font=app_font(size=12, weight="bold"), justify="left", anchor="w").pack(fill="x", anchor="w", padx=12, pady=(0, 8))
        self._calendar_loaded = True
        self.calendar_status.configure(text="Updated " + datetime.now().strftime("%H:%M") + " · " + str(len(rows)) + " upcoming events")

    def _build_price_alerts(self):
        page = self.pages["Price Alerts"]
        card = self.card(page, "Create a price alert", "Choose a ticker and target. Alerts check Alpaca IEX snapshots about once per minute while the app is open.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=14, pady=8)
        self.alert_symbol = ctk.CTkEntry(form, width=125, placeholder_text="Ticker")
        self.alert_symbol.pack(side="left", padx=4)
        self.alert_direction = styled_settings_dropdown(form, ["Rises to or above", "Falls to or below"])
        self.alert_direction.configure(width=175)
        self.alert_direction.pack(side="left", padx=4)
        self.alert_target = ctk.CTkEntry(form, width=135, placeholder_text="Target USD")
        self.alert_target.pack(side="left", padx=4)
        ctk.CTkButton(form, text="Add alert", command=self.add_price_alert).pack(side="left", padx=4)
        self.alert_list = ctk.CTkFrame(page, fg_color="transparent")
        self.alert_list.pack(fill="x", padx=14, pady=8)
        self.render_price_alerts()
        self.card(page, "Alert information", "Requires valid Alpaca credentials and Market Insight to remain open. IEX snapshots are not tick-by-tick data. Alerts do not place trades.")

    def add_price_alert(self):
        symbol = self.alert_symbol.get().strip().upper()
        target = safe_num(self.alert_target.get(), 0)
        if not symbol or not symbol.replace(".", "").replace("-", "").isalnum() or target <= 0:
            self.status.configure(text="Enter a valid ticker and a target price above zero.")
            return
        alerts = self.settings.setdefault("price_alerts", [])
        alerts.append({"symbol": symbol, "direction": self.alert_direction.get(), "target": target,
                       "triggered": False, "id": datetime.now().isoformat(timespec="microseconds")})
        self.settings["price_alerts"] = alerts[-100:]
        save_settings(self.settings)
        self.alert_symbol.delete(0, "end")
        self.alert_target.delete(0, "end")
        self.render_price_alerts()
        self.status.configure(text="Price alert saved for " + symbol + ".")

    def render_price_alerts(self):
        if not hasattr(self, "alert_list"):
            return
        for child in self.alert_list.winfo_children():
            child.destroy()
        alerts = self.settings.get("price_alerts", [])
        if not alerts:
            ctk.CTkLabel(self.alert_list, text="No alerts saved yet.").pack(anchor="w", padx=10, pady=12)
        for index, alert in enumerate(alerts):
            row = ctk.CTkFrame(self.alert_list, corner_radius=12, fg_color=(palette_color("#EEEEEE"), palette_color("#323232")))
            row.pack(fill="x", padx=4, pady=4)
            state = "TRIGGERED" if alert.get("triggered") else "WAITING"
            label = "{} · {} USD {:.4f} · {}".format(alert.get("symbol", "?"), alert.get("direction", "Rises to or above"), safe_num(alert.get("target")), state)
            ctk.CTkLabel(row, text=label, font=app_font(size=13, weight="bold")).pack(side="left", padx=12, pady=10)
            ctk.CTkButton(row, text="Remove", width=76, height=28, command=lambda i=index: self.remove_price_alert(i)).pack(side="right", padx=10, pady=7)

    def remove_price_alert(self, index):
        alerts = self.settings.get("price_alerts", [])
        if 0 <= index < len(alerts):
            alerts.pop(index)
            save_settings(self.settings)
            self.render_price_alerts()

    def _check_price_alerts(self):
        self.after(60000, self._check_price_alerts)
        alerts = self.settings.get("price_alerts", [])
        if not alerts or getattr(self, "_alerts_checking", False):
            return
        key, secret = get_alpaca_credentials()
        if not key or not secret:
            return
        self._alerts_checking = True
        threading.Thread(target=self._price_alert_worker, args=(key, secret, list(alerts)), daemon=True).start()

    def _price_alert_worker(self, key, secret, alerts):
        triggered = []
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        for alert in alerts:
            if alert.get("triggered"):
                continue
            try:
                response = requests.get("https://data.alpaca.markets/v2/stocks/{}/snapshot".format(alert["symbol"]),
                                         headers=headers, params={"feed": "iex"}, timeout=10)
                response.raise_for_status()
                snapshot = response.json()
                price = safe_num((snapshot.get("latestTrade") or {}).get("p"), 0)
                target = safe_num(alert.get("target"), 0)
                direction = alert.get("direction", "Rises to or above")
                if price > 0 and target > 0 and (price >= target if direction == "Rises to or above" else price <= target):
                    triggered.append({"symbol": alert["symbol"], "price": price, "target": target, "id": alert.get("id")})
            except Exception:
                continue
        self.after(0, lambda items=triggered: self._finish_price_alert_check(items))

    def _finish_price_alert_check(self, triggered):
        self._alerts_checking = False
        if not triggered:
            return
        for item in triggered:
            for alert in self.settings.get("price_alerts", []):
                if alert.get("id") == item["id"]:
                    alert["triggered"] = True
                    break
        save_settings(self.settings)
        self.render_price_alerts()
        from tkinter import messagebox
        messagebox.showinfo("Market Insight price alert", "\n".join(
            "{} reached USD {:.4f} (target USD {:.4f})".format(x["symbol"], x["price"], x["target"])
            for x in triggered
        ), parent=self)

    def _build_trading_journal(self):
        page = self.pages["Trading Journal"]
        card = self.card(page, "Log a completed trade", "Record closed trades. Profit/loss is calculated from entry, exit and quantity, before fees.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=14, pady=8)
        self.journal_symbol = ctk.CTkEntry(form, width=105, placeholder_text="Ticker")
        self.journal_symbol.pack(side="left", padx=3)
        self.journal_side = styled_settings_dropdown(form, ["Long", "Short"])
        self.journal_side.configure(width=90)
        self.journal_side.pack(side="left", padx=3)
        self.journal_entry = ctk.CTkEntry(form, width=115, placeholder_text="Entry USD")
        self.journal_entry.pack(side="left", padx=3)
        self.journal_exit = ctk.CTkEntry(form, width=115, placeholder_text="Exit USD")
        self.journal_exit.pack(side="left", padx=3)
        self.journal_quantity = ctk.CTkEntry(form, width=95, placeholder_text="Quantity")
        self.journal_quantity.pack(side="left", padx=3)
        self.journal_notes = ctk.CTkEntry(card, placeholder_text="Notes (optional)")
        self.journal_notes.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(card, text="Save trade", command=self.add_journal_trade).pack(anchor="e", padx=16, pady=(0, 14))
        self.journal_summary = ctk.CTkLabel(page, text="", font=app_font(size=15, weight="bold"))
        self.journal_summary.pack(anchor="w", padx=20, pady=(8, 4))
        self.journal_list = ctk.CTkFrame(page, fg_color="transparent")
        self.journal_list.pack(fill="x", padx=14, pady=8)
        self.render_journal()

    def add_journal_trade(self):
        symbol = self.journal_symbol.get().strip().upper()
        entry = safe_num(self.journal_entry.get(), 0)
        exit_price = safe_num(self.journal_exit.get(), 0)
        quantity = safe_num(self.journal_quantity.get(), 0)
        side = self.journal_side.get()
        if not symbol or not symbol.replace(".", "").replace("-", "").isalnum() or min(entry, exit_price, quantity) <= 0:
            self.status.configure(text="Enter a ticker and positive entry, exit and quantity values.")
            return
        pnl = (exit_price - entry) * quantity * (1 if side == "Long" else -1)
        self.settings.setdefault("trade_journal", []).insert(0, {
            "symbol": symbol, "side": side, "entry": entry, "exit": exit_price, "quantity": quantity,
            "pnl": pnl, "notes": self.journal_notes.get().strip(),
            "closed": datetime.now().isoformat(timespec="seconds")
        })
        self.settings["trade_journal"] = self.settings["trade_journal"][:500]
        save_settings(self.settings)
        for field in (self.journal_symbol, self.journal_entry, self.journal_exit, self.journal_quantity, self.journal_notes):
            field.delete(0, "end")
        self.render_journal()
        self.status.configure(text="Trade saved to your journal.")

    def render_journal(self):
        if not hasattr(self, "journal_list"):
            return
        for child in self.journal_list.winfo_children():
            child.destroy()
        trades = self.settings.get("trade_journal", [])
        total = sum(safe_num(t.get("pnl")) for t in trades)
        wins = sum(1 for t in trades if safe_num(t.get("pnl")) > 0)
        self.journal_summary.configure(text="{} trades · Net P/L: USD {:+,.2f} · {} wins".format(len(trades), total, wins))
        if not trades:
            ctk.CTkLabel(self.journal_list, text="Your saved trades will appear here.").pack(anchor="w", padx=10, pady=12)
        for index, trade in enumerate(trades):
            pnl = safe_num(trade.get("pnl"))
            tile = ctk.CTkFrame(self.journal_list, corner_radius=12, fg_color=(palette_color("#EEEEEE"), palette_color("#323232")))
            tile.pack(fill="x", padx=4, pady=4)
            ctk.CTkLabel(tile, text="{} {} · Entry {:.4f} → Exit {:.4f} · Qty {} · P/L {:+,.2f} USD".format(
                trade.get("symbol", "?"), trade.get("side", "Long"), safe_num(trade.get("entry")),
                safe_num(trade.get("exit")), safe_num(trade.get("quantity")), pnl
            ), font=app_font(size=13, weight="bold"), justify="left").pack(anchor="w", padx=12, pady=(8, 2))
            if trade.get("notes"):
                ctk.CTkLabel(tile, text=trade["notes"], font=app_font(size=12, weight="bold"), justify="left").pack(anchor="w", padx=12, pady=2)
            ctk.CTkLabel(tile, text=trade.get("closed", "").replace("T", " ")[:16],
                         font=app_font(size=11, weight="bold"), text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))).pack(anchor="w", padx=12, pady=(0, 6))
            ctk.CTkButton(tile, text="Delete", width=72, height=26, command=lambda i=index: self.remove_journal_trade(i)).pack(anchor="e", padx=10, pady=(0, 8))

    def remove_journal_trade(self, index):
        trades = self.settings.get("trade_journal", [])
        if 0 <= index < len(trades):
            trades.pop(index)
            save_settings(self.settings)
            self.render_journal()

    def _build_settings(self):
        page = self.pages["Settings"]

        # Keep the everyday controls together in one clear preferences section.
        preferences = self.card(
            page, "Preferences and display",
            "Choose how Market Insight looks, opens and keeps your watchlist up to date."
        )
        ctk.CTkLabel(preferences, text="Appearance",
                     font=app_font(size=14, weight="bold"),
                     text_color=(palette_color("#5B5B5B"), palette_color("#C3C3C3"))).pack(anchor="w", padx=18, pady=(10, 3))
        self.appearance_menu = styled_settings_dropdown(
            preferences, values=["System", "Dark", "Light"], command=self.change_appearance
        )
        self.appearance_menu.set(self.settings["appearance"])
        self.appearance_menu.pack(anchor="w", padx=18, pady=(0, 12))
        ctk.CTkLabel(preferences, text="Accent colour", font=app_font(size=14, weight="bold"), text_color=(palette_color("#5B5B5B"), palette_color("#C3C3C3"))).pack(anchor="w", padx=18, pady=(4, 3))
        self.colour_theme_menu = styled_settings_dropdown(preferences, values=["Black", "Amber", "Azure", "Lavender", "Rose", "Teal"], command=self.change_colour_theme)
        self.colour_theme_menu.set(self.settings.get("colour_theme", "Black"))
        self.colour_theme_menu.pack(anchor="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(
            preferences, text="Window transparency",
            font=app_font(size=14, weight="bold"),
            text_color=(palette_color("#555D54"), palette_color("#C0C5BC"))
        ).pack(anchor="w", padx=18, pady=(4, 3))
        self.transparency_value = ctk.CTkLabel(
            preferences, text="{}%".format(int(self.settings.get("transparency", 8))),
            font=app_font(size=13, weight="bold")
        )
        self.transparency_value.pack(anchor="w", padx=18, pady=(0, 3))
        self.transparency_slider = ctk.CTkSlider(
            preferences, from_=0, to=35, number_of_steps=35,
            command=self.change_transparency
        )
        self.transparency_slider.set(int(self.settings.get("transparency", 8)))
        self.transparency_slider.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            preferences, text="Font style",
            font=app_font(size=14),
            text_color=(palette_color("#5B5B5B"), palette_color("#C3C3C3"))
        ).pack(anchor="w", padx=18, pady=(4, 3))
        self.font_family_menu = styled_settings_dropdown(
            preferences,
            values=["Segoe UI", "Arial", "Verdana", "Trebuchet MS", "Georgia"],
            command=self.change_font_family
        )
        self.font_family_menu.set(self.settings.get("font_family", "Segoe UI"))
        self.font_family_menu.pack(anchor="w", padx=18, pady=(0, 8))

        self.bold_text_var = ctk.BooleanVar(value=bool(self.settings.get("bold_text", True)))
        self.bold_text_checkbox = ctk.CTkCheckBox(
            preferences,
            text="Use bold text throughout the app",
            variable=self.bold_text_var,
            command=self.change_bold_text,
            font=app_font(size=13),
            text_color=(palette_color("#5B5B5B"), palette_color("#C3C3C3")),
            fg_color=(palette_color("#A5A5A5"), palette_color("#939393")),
            hover_color=(palette_color("#939393"), palette_color("#A9A9A9")),
            border_color=(palette_color("#B3B3B3"), palette_color("#7C7C7C")),
            checkmark_color="#FFFFFF"
        )
        self.bold_text_checkbox.pack(anchor="w", padx=18, pady=(0, 8))
        font_note = ctk.CTkLabel(
            preferences,
            text="Choose from five font styles and turn bold text on or off for the whole app, including the sidebar and smaller labels.",
            font=app_font(size=13), justify="left", anchor="w",
            text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))
        )
        font_note.pack(fill="x", padx=18, pady=(0, 12))
        self._fit_text_to_width(font_note, preferences, 40)

        ctk.CTkLabel(preferences, text="How the program opens",
                     font=app_font(size=14, weight="bold"),
                     text_color=(palette_color("#5B5B5B"), palette_color("#C3C3C3"))).pack(anchor="w", padx=18, pady=(4, 3))
        self.startup_mode_menu = styled_settings_dropdown(
            preferences, values=["Maximised", "Full screen", "Windowed"],
            command=self.change_startup_window_mode
        )
        self.startup_mode_menu.set(self.settings.get("startup_window_mode", "Maximised"))
        self.startup_mode_menu.pack(anchor="w", padx=18, pady=(0, 5))
        mode_note = ctk.CTkLabel(
            preferences,
            text="Maximised fills the screen but keeps the Windows title bar and taskbar. Full screen hides them. Press F11 or Escape to leave full screen.",
            font=app_font(size=13, weight="bold"), justify="left", anchor="w",
            text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))
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
            font=app_font(size=14, weight="bold"),
            text_color=(palette_color("#5B5B5B"), palette_color("#C3C3C3"))
        ).pack(anchor="w", padx=18, pady=(8, 3))
        shortcut_actions = ctk.CTkFrame(preferences, fg_color="transparent")
        shortcut_actions.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkButton(
            shortcut_actions, text="Create desktop shortcut",
            command=self.create_desktop_shortcut
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            shortcut_actions, text="Remove desktop shortcut",
            fg_color=(palette_color("#E3E3E3"), palette_color("#3E3E3E")),
            text_color=(palette_color("#787878"), palette_color("#C5C5C5")),
            command=self.remove_desktop_shortcut
        ).pack(side="left")

        self.auto_scan_var = ctk.BooleanVar(value=self.settings["auto_scan"])
        ctk.CTkCheckBox(
            preferences, text="Scan my watchlist automatically",
            variable=self.auto_scan_var, command=self.save_general_settings
        ).pack(anchor="w", padx=18, pady=(4, 7))
        ctk.CTkLabel(preferences, text="Automatic scan interval (minutes)",
                     font=app_font(size=13, weight="bold"),
                     text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))).pack(anchor="w", padx=18, pady=(0, 3))
        self.interval_menu = styled_settings_dropdown(preferences, values=["5", "15", "30", "60"])
        self.interval_menu.set(str(self.settings["scan_interval"]))
        self.interval_menu.pack(anchor="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(preferences, text="Your trading platform",
                     font=app_font(size=14, weight="bold"),
                     text_color=(palette_color("#5B5B5B"), palette_color("#C3C3C3"))).pack(anchor="w", padx=18, pady=(4, 3))
        self.platform_menu = styled_settings_dropdown(
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
                     font=app_font(size=13, weight="bold"),
                     text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))).pack(anchor="w", padx=18, pady=(0, 3))
        self.threshold_menu = styled_settings_dropdown(preferences, values=["60", "70", "80", "90"])
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
            updates, text="Current version: {}".format(APP_VERSION),
            font=app_font(size=13, weight="bold"), text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9")), justify="left"
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
            connection, text=key_status, text_color=(palette_color("#797979"), palette_color("#B1B1B1"))
        )
        self.alpaca_status.pack(anchor="w", padx=18, pady=(4, 4))
        alpaca_actions = ctk.CTkFrame(connection, fg_color="transparent")
        alpaca_actions.pack(fill="x", padx=18, pady=(4, 8))
        ctk.CTkButton(alpaca_actions, text="Save Alpaca keys", command=self.save_alpaca_keys).pack(side="left")
        ctk.CTkButton(
            alpaca_actions, text="Remove saved keys",
            fg_color=(palette_color("#E3E3E3"), palette_color("#3E3E3E")), text_color=(palette_color("#787878"), palette_color("#C5C5C5")),
            command=self.remove_alpaca_keys
        ).pack(side="left", padx=8)
        price_note = ctk.CTkLabel(
            connection,
            text="Price data comes from IEX, which does not cover every US market trade. Live prices are available only when the market is open and an IEX trade is available. Past-price indicators come from Yahoo Finance. If Alpaca can't provide a live price, the app will show an error rather than silently using delayed data.",
            justify="left", font=app_font(size=13, weight="bold"),
            text_color=(palette_color("#818181"), palette_color("#B2B2B2"))
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
            ("YouTube  ·  @Adrianvaleitl", "https://www.youtube.com/@Adrianvaleitl"),
            ("TikTok  ·  @adrianvaleitl", "https://www.tiktok.com/@adrianvaleitl"),
            ("Donate  ·  Ko-fi", "https://ko-fi.com/marketinsight"),
            ("Official website", "https://adrianvaleitl-debug.github.io/market-insight/"),
            ("GitHub repository", "https://github.com/adrianvaleitl-debug/market-insight")
        ]:
            ctk.CTkButton(
                extras, text=label + "  ↗", corner_radius=16,
                fg_color=(palette_color("#D9D9D9"), palette_color("#464646")),
                hover_color=(palette_color("#CACACA"), palette_color("#545454")),
                text_color=(palette_color("#464646"), palette_color("#E4E4E4")),
                command=lambda target=url: webbrowser.open(target)
            ).pack(anchor="center", pady=4)

        ctk.CTkFrame(extras, height=1, fg_color=(palette_color("#D9D9D9"), palette_color("#464646"))).pack(
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
                extras, text=heading, font=app_font(size=13, weight="bold"),
                text_color=(palette_color("#5B5B5B"), palette_color("#DCDCDC"))
            ).pack(anchor="w", padx=18, pady=(7, 1))
            note = ctk.CTkLabel(
                extras, text=description, font=app_font(size=13, weight="bold"),
                justify="left", anchor="w", text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9"))
            )
            note.pack(fill="x", padx=18, pady=(0, 5))
            self._fit_text_to_width(note, extras, 40)

        ctk.CTkLabel(
            extras, text="Created by Adrian Vale  ·  Market Insight",
            font=app_font(size=15, weight="bold"),
            text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3"))
        ).pack(anchor="center", pady=(10, 14))

    def _build_about(self):
        page = self.pages["About"]
        card = self.card(page, "About Market Insight")
        intro = ctk.CTkLabel(card, text="A straightforward tool for researching stocks and keeping track of the ones you're interested in.",
                             font=app_font(size=17, weight="bold"),
                             text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3")), justify="left")
        intro.pack(anchor="w", fill="x", padx=18, pady=(6, 8))
        self._fit_text_to_width(intro, card, 40)
        data_note = ctk.CTkLabel(card, text="When connected, live prices come from Alpaca's IEX data feed. Stock indicators are calculated using past daily prices from Yahoo Finance. IEX does not include every US market trade, so some prices may not be available.",
                                 font=app_font(size=13, weight="bold"), justify="left",
                                 text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9")))
        data_note.pack(anchor="w", fill="x", padx=18, pady=5)
        self._fit_text_to_width(data_note, card, 40)
        disclaimer = ctk.CTkLabel(card, text="For education and research only. Scores and indicators are estimates, not financial advice or a guarantee of future results. Market Insight does not connect to your broker and cannot place trades.",
                                  font=app_font(size=13, weight="bold"), justify="left",
                                  text_color=(palette_color("#808080"), palette_color("#AFAFAF")))
        disclaimer.pack(anchor="w", fill="x", padx=18, pady=5)
        self._fit_text_to_width(disclaimer, card, 40)
        ctk.CTkLabel(card, text="Created by Adrian Vale  •  Market Insight",
                     font=app_font(size=15, weight="bold"), text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3"))).pack(anchor="w", padx=18, pady=(14, 18))

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
                         font=app_font(size=13, weight="bold"),
                         text_color=(palette_color("#4F4F4F"), palette_color("#DCDCDC"))).pack(side="left", anchor="nw")
            detail = ctk.CTkLabel(row, text=description, font=app_font(size=13, weight="bold"),
                                  justify="left", anchor="w",
                                  text_color=(palette_color("#7B7B7B"), palette_color("#A9A9A9")))
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
            ctk.CTkLabel(workflow, text=item, font=app_font(size=13, weight="bold"),
                         justify="left", anchor="w",
                         text_color=(palette_color("#6A6A6A"), palette_color("#C3C3C3"))).pack(fill="x", padx=18, pady=4)

        sources = self.card(page, "Data sources and useful websites",
                            "Open the services Market Insight uses or the platform you selected.")
        for label, url in [
            ("Alpaca dashboard", "https://app.alpaca.markets/"),
            ("Alpaca market data documentation", "https://docs.alpaca.markets/docs/about-market-data-api"),
            ("Yahoo Finance", "https://finance.yahoo.com/"),
            ("TradingView charts", "https://www.tradingview.com/")
        ]:
            ctk.CTkButton(sources, text=label + "  ↗", corner_radius=16,
                          fg_color=(palette_color("#D9D9D9"), palette_color("#464646")),
                          hover_color=(palette_color("#CACACA"), palette_color("#545454")),
                          text_color=(palette_color("#464646"), palette_color("#E4E4E4")),
                          command=lambda target=url: webbrowser.open(target)
                          ).pack(anchor="center", pady=4)


    def show_page(self, name):
        self.current_page = name
        for frame in self.pages.values():
            frame.grid_remove()
        self.pages[name].grid()
        self.page_title.configure(text={"Overview":"Market overview","What's New":"What's New","Market Hours":"Market hours","Watchlist":"Watchlist","Economic Calendar":"Economic calendar","Price Alerts":"Price alerts","Trading Journal":"Trading journal","Settings":"Settings","About":"About"}[name])
        if name == "Market Hours":
            self.refresh_market_hours()
        elif name == "Economic Calendar" and not getattr(self, "_calendar_loaded", False):
            self.refresh_economic_calendar()
        elif name == "Price Alerts":
            self.render_price_alerts()
        elif name == "Trading Journal":
            self.render_journal()
        for label, button in self.nav_buttons.items():
            button.configure(fg_color=(palette_color("#DCDCDC"), palette_color("#484848")) if label == name else "transparent")

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
            fg_color=(palette_color("#595959"), palette_color("#3D3D3D")),
            text_color=(palette_color("#E4E4E4"), palette_color("#E4E4E4"))
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
            response = requests.get(GITHUB_RELEASES_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "Market-Insight-Updater/1.8"}, timeout=(12, 25), verify=certifi.where())
            response.raise_for_status()
            release = response.json()
            latest_tag = str(release.get("tag_name", "")).strip()
            if version_tuple(latest_tag) <= version_tuple(APP_VERSION):
                self.after(0, lambda: self._show_update_status("You're up to date · {}".format(APP_VERSION)))
                return
            expected_name = "Market_Insight_Setup_{}.exe".format(latest_tag)
            assets = release.get("assets") or []
            asset = next((item for item in assets if item.get("name") == expected_name), None)
            url = str(asset.get("browser_download_url", "")) if asset else ""
            digest = str(asset.get("digest", "")) if asset else ""
            size = int(asset.get("size", 0)) if asset else 0
            if (not asset or not url.startswith("https://github.com/adrianvaleitl-debug/market-insight/releases/download/")
                    or not digest.startswith("sha256:") or size <= 0):
                self.after(0, lambda: self._show_update_status("The update is available, but its installer could not be verified. Open GitHub releases."))
                return
            self.after(0, lambda tag=latest_tag, download_url=url, name=expected_name, expected_size=size, expected_digest=digest.split(":", 1)[1]:
                       self._offer_update_download(tag, download_url, name, expected_size, expected_digest))
        except Exception as exc:
            detail = str(exc).replace("\n", " ")[:180]
            self.after(0, lambda error=detail: self._show_update_status("GitHub update check failed: " + error))
        finally:
            self._update_check_running = False

    def _show_update_status(self, message):
        if hasattr(self, "update_status"):
            self.update_status.configure(text=message)

    def _offer_update_download(self, tag, url, filename, expected_size, expected_digest):
        from tkinter import messagebox
        if not messagebox.askyesno(
            "Market Insight update available",
            "A newer version is available: {}\n\nYou have: {}\n\nInstall this update now? Market Insight will close briefly and reopen automatically. Your saved settings and credentials will be kept.".format(tag, APP_VERSION),
            parent=self
        ):
            self._show_update_status("Update {} is available on GitHub.".format(tag))
            return
        self._show_update_status("Downloading and verifying {}…".format(tag))
        threading.Thread(
            target=self._download_update_worker,
            args=(url, filename, tag, expected_size, expected_digest),
            daemon=True
        ).start()

    def _download_update_worker(self, url, filename, tag, expected_size, expected_digest):
        try:
            response = requests.get(url, stream=True, timeout=(15, 120))
            response.raise_for_status()
            update_dir = Path(os.environ.get("TEMP", str(Path.home() / "AppData" / "Local" / "Temp"))) / "Market Insight Updates"
            update_dir.mkdir(parents=True, exist_ok=True)
            destination = update_dir / filename
            temporary = destination.with_suffix(destination.suffix + ".part")
            digest = hashlib.sha256()
            downloaded = 0
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        output.write(chunk)
                        digest.update(chunk)
                        downloaded += len(chunk)
            if downloaded != expected_size or digest.hexdigest().lower() != expected_digest.lower():
                temporary.unlink(missing_ok=True)
                raise ValueError("The downloaded installer did not match GitHub's published size and SHA-256 checksum.")
            temporary.replace(destination)
            self.after(0, lambda path=destination, version=tag: self._begin_update_install(path, version))
        except Exception as exc:
            message = "The update download or verification failed: {}".format(exc)
            self.after(0, lambda msg=message: self._show_update_status(msg))

    def _begin_update_install(self, installer_path, tag):
        from tkinter import messagebox
        try:
            if not getattr(sys, "frozen", False):
                raise RuntimeError("Automatic installation is available in the installed Windows version of Market Insight.")
            app_exe = APP_DIR / "Market Insight.exe"
            if not app_exe.exists():
                raise FileNotFoundError("The installed Market Insight executable could not be found.")
            helper = installer_path.with_suffix(".vbs")

            def vbs_literal(value):
                return '"' + str(value).replace('"', '""') + '"'

            installer_command = '"{}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="{}"'.format(
                installer_path, APP_DIR
            )
            app_command = '"{}"'.format(app_exe)
            script_lines = [
                'Set shell = CreateObject("WScript.Shell")',
                'Set wmi = GetObject("winmgmts:\\\\.\\root\\cimv2")',
                'Do',
                '  Set matches = wmi.ExecQuery("SELECT * FROM Win32_Process WHERE ProcessId = {}")'.format(os.getpid()),
                '  If matches.Count = 0 Then Exit Do',
                '  WScript.Sleep 500',
                'Loop',
                'result = shell.Run({}, 0, True)'.format(vbs_literal(installer_command)),
                'If result = 0 Then',
                '  shell.Run {}, 0, False'.format(vbs_literal(app_command)),
                'Else',
                '  MsgBox "The update installer could not complete (code " & result & "). You can run the downloaded installer manually.", 16, "Market Insight update"',
                'End If',
                'Set fso = CreateObject("Scripting.FileSystemObject")',
                'fso.DeleteFile WScript.ScriptFullName, True',
            ]
            helper.write_text("\r\n".join(script_lines) + "\r\n", encoding="utf-8")
            subprocess.Popen(["wscript.exe", str(helper)], close_fds=True)
            self._show_update_status("Installing {}… Market Insight will reopen automatically.".format(tag))
            self.after(150, self.destroy)
        except Exception as exc:
            messagebox.showerror(
                "Market Insight update",
                "The update was downloaded, but automatic installation couldn't start. You can run this installer manually:\n\n{}\n\n{}".format(installer_path, exc),
                parent=self
            )
            self._show_update_status("Couldn't start the update installer.")

    def change_transparency(self, value):
        """Apply and persist the user's window opacity preference."""
        value = round(max(0, min(35, float(value))))
        self.settings["transparency"] = value
        if hasattr(self, "transparency_value"):
            self.transparency_value.configure(text="{}%".format(value))
        self.after_idle(self.apply_liquid_glass)
        save_settings(self.settings)

    def change_appearance(self, value):
        self.settings["appearance"] = value
        ctk.set_appearance_mode(value.lower())
        save_settings(self.settings)

    def change_colour_theme(self, value):
        """Apply a palette immediately and rebuild the UI so every surface updates."""
        global ACTIVE_COLOUR_THEME
        display_to_theme = {"USD":"Black","EUR":"Azure","GBP":"Lavender","JPY":"Rose","CHF":"Teal","Dollar":"Black","Euro":"Azure","Pound":"Lavender","Yen":"Rose","Franc":"Teal"}
        value = display_to_theme.get(value, value)
        if value not in COLOUR_ACCENTS:
            value = "Black"
        self.settings["colour_theme"] = value
        ACTIVE_COLOUR_THEME = value
        apply_ctk_palette_theme()
        save_settings(self.settings)

        # Rebuild widgets with the new palette; preserve the current page and app state.
        current_page = getattr(self, "current_page", "Settings")
        def rebuild_with_new_accent():
            try:
                for child in self.winfo_children():
                    child.destroy()
                self.configure(fg_color=GLASS_KEY if sys.platform=="win32" else (palette_color("#F0F0F0"), palette_color("#101012")))
                self._build_ui()
                self.apply_liquid_glass()
                install_accent_spotlight(self, COLOUR_ACCENTS[ACTIVE_COLOUR_THEME][0],
                                         GLASS_KEY if sys.platform=="win32" else ("#F0F0F0" if ctk.get_appearance_mode()=="Light" else "#101012"))
                self._refresh_watchlist_text()
                self.show_page(current_page if current_page in self.pages else "Settings")
                self.status.configure(text="{} colour theme applied and saved.".format(value))
            except Exception as exc:
                write_diagnostic("Accent-colour rebuild failed: " + traceback.format_exc())
                try:
                    from tkinter import messagebox
                    messagebox.showerror(APP_NAME, "The colour was saved, but the interface could not refresh. Restart the app to apply it.")
                except Exception:
                    pass
        self.after_idle(rebuild_with_new_accent)

    def change_font_family(self, value):
        """Apply the selected typeface across the app while keeping all text bold."""
        global ACTIVE_FONT_FAMILY
        allowed = ("Segoe UI", "Arial", "Verdana", "Trebuchet MS", "Georgia")
        if value not in allowed:
            value = "Segoe UI"
        self.settings["font_family"] = value
        ACTIVE_FONT_FAMILY = value
        save_settings(self.settings)

        current_page = getattr(self, "current_page", "Settings")
        for child in self.winfo_children():
            child.destroy()
        self.configure(fg_color=(palette_color("#F0F0F0"), palette_color("#212121")))
        self._build_ui()
        self._refresh_watchlist_text()
        self.show_page(current_page if current_page in self.pages else "Settings")
        self.status.configure(text="{} font applied and saved.".format(value))

    def change_bold_text(self):
        """Save and apply the user's bold/regular text preference app-wide."""
        global ACTIVE_BOLD_TEXT
        ACTIVE_BOLD_TEXT = bool(self.bold_text_var.get())
        self.settings["bold_text"] = ACTIVE_BOLD_TEXT
        save_settings(self.settings)
        current_page = getattr(self, "current_page", "Settings")
        for child in self.winfo_children():
            child.destroy()
        self.configure(fg_color=(palette_color("#F0F0F0"), palette_color("#212121")))
        self._build_ui()
        self._refresh_watchlist_text()
        self.show_page(current_page if current_page in self.pages else "Settings")
        self.status.configure(text="Bold text {}.".format("enabled" if ACTIVE_BOLD_TEXT else "disabled"))

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

    def change_calculator_currency(self, selected_label):
        currency = next((code for code, label in CURRENCY_OPTIONS.items() if label == selected_label), "USD")
        self.settings["currency"] = currency
        if hasattr(self, "balance_label"):
            self.balance_label.configure(text="Account balance ({})".format(currency))
        save_settings(self.settings)

    def save_calculator_settings(self):
        balance = safe_num(self.balance_entry.get(), 1000)
        risk = safe_num(self.risk_entry.get(), 1)
        if balance <= 0 or not 0 < risk <= 5:
            self.status.configure(text="Enter an account balance above 0 and a risk amount between 0% and 5%.")
            return
        self.settings["balance"] = balance
        self.settings["risk_percent"] = risk
        self.settings["currency"] = next(
            (code for code, label in CURRENCY_OPTIONS.items() if label == self.currency_menu.get()), "USD"
        )
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
        self._scan_total = len(self.settings.get("watchlist", DEFAULT_TICKERS))
        self._scan_remaining = self._scan_total
        self.results = {}
        self.status.configure(text="Scanning watchlist…")
        # Start with an empty results list so old scan data is not mistaken for
        # stocks checked in the current run.
        if hasattr(self, "results_text"):
            self._refresh_results_view()
        self.scan_info.configure(
            text="Getting recent stock price data…",
            fg_color=(palette_color("#595959"), palette_color("#3D3D3D")),
            text_color=(palette_color("#E4E4E4"), palette_color("#E4E4E4"))
        )
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        output = {}
        symbols = list(self.settings.get("watchlist", DEFAULT_TICKERS))
        total = len(symbols)
        self.after(0, lambda count=total: self.scan_info.configure(text=f"{count}/{count} left"))
        api_key, secret_key = get_alpaca_credentials()
        for i, symbol in enumerate(symbols):
            try:
                output[symbol] = scan_symbol(symbol, api_key, secret_key)
            except Exception as exc:
                output[symbol] = {"error": str(exc)}
            remaining = total - (i + 1)
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
                text_color=(palette_color("#888888"), palette_color("#B0B0B0"))
            ).pack(anchor="w", padx=12, pady=14)
            return

        def render_batch(index=0):
            parent._render_job = None
            end_index = min(index + 6, len(rows))
            for symbol, data in rows[index:end_index]:
                tile = ctk.CTkFrame(parent, corner_radius=18, fg_color=(palette_color("#EEEEEE"), palette_color("#323232")))
                tile.pack(fill="x", padx=5, pady=5)
                head = ctk.CTkFrame(tile, fg_color="transparent")
                head.pack(fill="x", padx=13, pady=(9, 2))
                title_area = ctk.CTkFrame(head, fg_color="transparent")
                title_area.pack(side="left", fill="x", expand=True)
                company_name = ctk.CTkLabel(
                    title_area, text=STOCK_NAMES.get(symbol, symbol),
                    font=app_font(size=15, weight="bold"), justify="left"
                )
                company_name.pack(anchor="w", fill="x")
                self._fit_text_to_width(company_name, title_area, 12)
                ctk.CTkLabel(
                    title_area, text=symbol, font=app_font(size=13, weight="bold"),
                    text_color=(palette_color("#7B7B7B"), palette_color("#B0B0B0"))
                ).pack(anchor="w")

                if caution:
                    warning_text = ctk.CTkLabel(
                        tile, text=", ".join(data.get("warnings", [])) or "Needs a closer look",
                        font=app_font(size=13, weight="bold"), text_color=(palette_color("#838383"), palette_color("#AFAFAF")),
                        justify="left"
                    )
                    warning_text.pack(anchor="w", fill="x", padx=13, pady=(2, 9))
                    self._fit_text_to_width(warning_text, tile, 30)
                else:
                    tone = (palette_color("#828282"), palette_color("#BFBFBF")) if data["day_change"] >= 0 else (palette_color("#838383"), palette_color("#AFAFAF"))
                    info = ctk.CTkFrame(tile, fg_color="transparent")
                    info.pack(fill="x", padx=13, pady=(5, 10))
                    ctk.CTkLabel(
                        info, text="USD {:.2f}".format(data["price"]),
                        font=app_font(size=17, weight="bold")
                    ).pack(side="left")
                    ctk.CTkLabel(
                        info, text="{:+.2f}%".format(data["day_change"]),
                        font=app_font(size=14, weight="bold"), text_color=tone
                    ).pack(side="left", padx=(10, 0))
                    ctk.CTkLabel(
                        info, text="Score: {}/100 · RSI: {:.0f} · Vol: {:.1f}x".format(
                            data["score"], data["rsi"], data["volume_ratio"]
                        ),
                        font=app_font(size=12, weight="bold"),
                        text_color=(palette_color("#787878"), palette_color("#BBBBBB"))
                    ).pack(side="left", padx=(10, 0))
                    ctk.CTkButton(
                        info, text="View on {} ↗".format(self.settings.get("selected_platform", "platform")),
                        width=145, height=28, corner_radius=9, font=app_font(size=13, weight="bold"),
                        command=lambda sym=symbol: self.open_selected_platform(sym, ask=True)
                    ).pack(side="right")

            if end_index < len(rows):
                parent._render_job = parent.after(10, lambda: render_batch(end_index))

        render_batch()

    def _update_scan_summary(self, valid):
        labels = getattr(self, "scan_summary_labels", {})
        if not labels:
            return
        if not valid:
            for label in labels.values():
                label.configure(text="—")
            return
        average = sum(data["score"] for _, data in valid) / len(valid)
        best = max(valid, key=lambda item: item[1].get("day_change", 0))
        worst = min(valid, key=lambda item: item[1].get("day_change", 0))
        high_volume = max(valid, key=lambda item: item[1].get("volume_ratio", 0))
        labels["average"].configure(text="{:.0f}/100".format(average))
        labels["best"].configure(text="{} {:+.1f}%".format(best[0], best[1].get("day_change", 0)))
        labels["worst"].configure(text="{} {:+.1f}%".format(worst[0], worst[1].get("day_change", 0)))
        labels["volume"].configure(text="{} {:.1f}x".format(high_volume[0], high_volume[1].get("volume_ratio", 0)))

    def _refresh_results_view(self):
        if not hasattr(self, "results_text"):
            return
        rows = [(symbol, data) for symbol, data in self.results.items() if "error" not in data]
        query = self.results_search.get().strip().lower() if hasattr(self, "results_search") else ""
        if query:
            rows = [(symbol, data) for symbol, data in rows
                    if query in symbol.lower() or query in STOCK_NAMES.get(symbol, symbol).lower()]
        filter_name = self.results_filter.get() if hasattr(self, "results_filter") else "All stocks"
        if filter_name == "Positive today":
            rows = [(s, d) for s, d in rows if d.get("day_change", 0) > 0]
        elif filter_name == "Negative today":
            rows = [(s, d) for s, d in rows if d.get("day_change", 0) < 0]
        elif filter_name == "Score 70+":
            rows = [(s, d) for s, d in rows if d.get("score", 0) >= 70]
        elif filter_name == "With warnings":
            rows = [(s, d) for s, d in rows if d.get("warnings")]
        sort_name = self.results_sort.get() if hasattr(self, "results_sort") else "Highest score"
        sort_keys = {
            "Highest score": lambda item: item[1].get("score", 0),
            "Biggest daily gain": lambda item: item[1].get("day_change", 0),
            "Biggest daily loss": lambda item: item[1].get("day_change", 0),
            "Highest RSI": lambda item: item[1].get("rsi", 0),
            "Highest volume": lambda item: item[1].get("volume_ratio", 0),
        }
        rows.sort(key=sort_keys.get(sort_name, sort_keys["Highest score"]),
                  reverse=(sort_name != "Biggest daily loss"))
        self._render_stock_cards(self.results_text, rows)
        total_valid = sum(1 for data in self.results.values() if "error" not in data)
        if hasattr(self, "results_count"):
            if getattr(self, "scanning", False):
                checked = getattr(self, "_scan_total", 0) - getattr(self, "_scan_remaining", 0)
                self.results_count.configure(
                    text="Showing {} loaded stocks · {} of {} checked".format(len(rows), checked, getattr(self, "_scan_total", 0))
                )
            else:
                self.results_count.configure(text="Showing {} of {} successful results".format(len(rows), total_valid))

    def export_scan_csv(self):
        if not self.results:
            self.status.configure(text="Run a scan before exporting results.")
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Export Market Insight scan",
            defaultextension=".csv", filetypes=[("CSV spreadsheet", "*.csv")],
            initialfile="Market_Insight_Scan_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M"))
        )
        if not path:
            return
        columns = ["Ticker", "Company", "Price USD", "Score", "Daily change %", "20-day change %",
                   "RSI", "MACD", "ATR", "Volume vs average", "EMA 20", "EMA 50", "Date", "Warnings", "Error"]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                for symbol, data in self.results.items():
                    writer.writerow({
                        "Ticker": symbol, "Company": STOCK_NAMES.get(symbol, symbol),
                        "Price USD": data.get("price", ""), "Score": data.get("score", ""),
                        "Daily change %": data.get("day_change", ""),
                        "20-day change %": data.get("change20", ""), "RSI": data.get("rsi", ""),
                        "MACD": data.get("macd", ""), "ATR": data.get("atr", ""),
                        "Volume vs average": data.get("volume_ratio", ""),
                        "EMA 20": data.get("ema20", ""), "EMA 50": data.get("ema50", ""),
                        "Date": data.get("date", ""), "Warnings": "; ".join(data.get("warnings", [])),
                        "Error": data.get("error", "")
                    })
            self.status.configure(text="Scan results exported to CSV.")
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror(APP_NAME, "Couldn't export the CSV file.\\n\\n{}".format(exc), parent=self)

    def _finish_scan(self, output, market_context=None):
        self.results = output
        valid_for_history = [(symbol, data) for symbol, data in output.items() if "error" not in data]
        valid_for_history.sort(key=lambda item: item[1].get("score", 0), reverse=True)
        history = self.settings.setdefault("scan_history", [])
        history.insert(0, {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "successful": len(valid_for_history),
            "total": len(output),
            "leaders": [{"symbol": symbol, "score": round(float(data.get("score", 0)), 1)} for symbol, data in valid_for_history[:5]],
        })
        self.settings["scan_history"] = history[:20]
        save_settings(self.settings)
        self._render_scan_history()
        self._update_daily_briefing(output)
        market_context = market_context or {}
        for symbol, label in getattr(self, "market_pulse_labels", {}).items():
            data = market_context.get(symbol)
            if data:
                label.configure(text="{:.2f}  ({:+.2f}%)".format(data["price"], data["change"]))
                tone = (palette_color("#818181"), palette_color("#B2B2B2")) if symbol == "^VIX" else ((palette_color("#828282"), palette_color("#BFBFBF")) if data["change"] >= 0 else (palette_color("#838383"), palette_color("#AFAFAF")))
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
        self._update_scan_summary(valid)
        self._refresh_results_view()
        errors = ["{}: {}".format(symbol, data["error"]) for symbol, data in output.items() if "error" in data]
        if errors:
            issue = ctk.CTkFrame(self.results_text, corner_radius=12, fg_color=(palette_color("#E9E9E9"), palette_color("#343434")))
            issue.pack(fill="x", padx=5, pady=6)
            ctk.CTkLabel(issue, text="Stocks we couldn't check", font=app_font(size=15, weight="bold"),
                         text_color=(palette_color("#838383"), palette_color("#AFAFAF"))).pack(anchor="w", padx=12, pady=(8, 2))
            error_details = ctk.CTkLabel(issue, text="\\n".join(errors[:12]),
                                         font=app_font(size=13, weight="bold"), justify="left",
                                         text_color=(palette_color("#808080"), palette_color("#AFAFAF")))
            error_details.pack(anchor="w", fill="x", padx=12, pady=(0, 10))
            self._fit_text_to_width(error_details, issue, 28)
        self.status.configure(text=f"Scan complete · {len(valid)} symbols")
        self.scan_info.configure(
            text=f"Last scan: {datetime.now().strftime('%H:%M')}",
            fg_color=(palette_color("#595959"), palette_color("#3D3D3D")),
            text_color=(palette_color("#E4E4E4"), palette_color("#E4E4E4"))
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
        currency = self.settings.get("currency", "USD")
        symbol_mark = CURRENCY_SYMBOLS.get(currency, "$")
        try:
            balance_usd = balance * currency_to_usd_rate(currency)
        except Exception as exc:
            self.calc_output.configure(text="{}\n\n{}".format(
                symbol, str(exc) + " The calculator will update when the rate is available."
            ))
            return
        risk_cash = balance * risk_pct / 100
        risk_cash_usd = balance_usd * risk_pct / 100
        shares = min(risk_cash_usd / stop_distance, balance_usd / price)
        self.calc_output.configure(text=f"{symbol} example levels\nStop loss: ${stop:.2f} USD  |  Take profit: ${target:.2f} USD\nApprox. shares: {math.floor(shares)}  |  Risk budget: {symbol_mark}{risk_cash:,.2f} {currency}\nBased on a stop distance of 1.5 × ATR and a potential 2:1 reward-to-risk ratio. FX conversion uses the latest available rate.")

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
