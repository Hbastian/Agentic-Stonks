# analysis.py
# Data fetch, indicator calculations, chart construction, and a compact summary for chat.

from __future__ import annotations
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Literal, Tuple, Dict, Any

# -------------------------- Data --------------------------

def _fetch(symbol: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)

    # Robust empty-frame handling
    empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return empty

    # normalize potential MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.droplevel(1, axis=1)
        except Exception:
            pass

    # normalize names, guard for missing OHLC
    df = df.rename(columns=lambda c: str(c).strip().title())
    needed = {"Open", "High", "Low", "Close"}
    if not needed.issubset(set(df.columns)):
        return empty

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if "Volume" not in df.columns:
        df["Volume"] = 0
    return df

def fetch_ohlcv(symbol: str, timeframe: Literal["1h", "4h", "1d"]) -> Tuple[pd.DataFrame, str, str]:
    """
    Returns (df, period, interval_used).
    4h is created by fetching 1h and resampling to 4h OHLCV.
    """
    if timeframe == "1h":
        period, interval = "1mo", "1h"
        df = _fetch(symbol, period, interval)
    elif timeframe == "4h":
        period, interval = "3mo", "1h"
        base = _fetch(symbol, period, interval)
        if base.empty:
            return base, period, "4h"
        # Resample to 4h
        o = base["Open"].resample("4H").first()
        h = base["High"].resample("4H").max()
        l = base["Low"].resample("4H").min()
        c = base["Close"].resample("4H").last()
        v = base["Volume"].resample("4H").sum()
        df = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}).dropna()
        interval = "4h"
    else:  # "1d"
        period, interval = "1y", "1d"
        df = _fetch(symbol, period, interval)
    return df, period, interval

# ----------------------- Indicators -----------------------

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = true_range(df)
    # Wilder's ATR approximated via EMA(alpha=1/n)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()

def session_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP that resets each trading day (use on intraday)."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    vol = df["Volume"]
    key = pd.Series(df.index.date, index=df.index)
    cum_pv = (tp * vol).groupby(key).cumsum()
    cum_v  = vol.groupby(key).cumsum().replace(0, np.nan)
    return (cum_pv / cum_v).rename("VWAP")

def rolling_vwap(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    pv = tp * df["Volume"]
    roll_pv = pv.rolling(n, min_periods=1).sum()
    roll_v  = df["Volume"].rolling(n, min_periods=1).sum().replace(0, np.nan)
    return (roll_pv / roll_v).rename("VWAP")

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    line = ema_fast - ema_slow
    sig = ema(line, signal)
    hist = line - sig
    return line.rename("MACD"), sig.rename("Signal"), hist.rename("MACD_Hist")

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def compute_indicators(
    df: pd.DataFrame,
    *,
    want_ema200: bool = True,
    want_atr: bool = True,
    vwap_mode: Literal["session", "anchored", "rolling"] = "session",
    vwap_n: int = 20,
    want_vtvr: bool = True,
    vtvr_use_tr: bool = False,  # False => use ATR(14); True => use single-bar TR
    vtvr_z_on: bool = False,
    vtvr_z_window: int = 60,
    ensure_macd_rsi: bool = True
) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    # Baseline momentum (keeps figure resilient)
    if ensure_macd_rsi:
        if "MACD" not in out.columns or "Signal" not in out.columns:
            m, s, h = macd(out["Close"])
            out["MACD"], out["Signal"], out["MACD_Hist"] = m, s, h
        if "RSI" not in out.columns:
            out["RSI"] = rsi(out["Close"])

    if want_ema200:
        out["EMA200"] = ema(out["Close"], 200)

    if want_atr:
        out["ATR14"] = atr(out, 14)

    # VWAP
    if vwap_mode == "session":
        try:
            out["VWAP"] = session_vwap(out)
        except Exception:
            out["VWAP"] = rolling_vwap(out, max(5, min(50, vwap_n)))
    elif vwap_mode == "rolling":
        out["VWAP"] = rolling_vwap(out, vwap_n)
    else:  # anchored -> fallback to rolling unless an anchor is supplied externally
        out["VWAP"] = rolling_vwap(out, vwap_n)

    # VTVR (Volume to Volatility Ratio)
    if want_vtvr:
        denom = true_range(out) if vtvr_use_tr else out.get("ATR14", atr(out, 14))
        denom = denom.replace(0, np.nan)
        out["VTVR"] = (out["Volume"] / denom).rename("VTVR")
        if vtvr_z_on:
            mean = out["VTVR"].rolling(vtvr_z_window, min_periods=10).mean()
            std = out["VTVR"].rolling(vtvr_z_window, min_periods=10).std()
            out["VTVR_z"] = (out["VTVR"] - mean) / std

    return out

# ---------------- Chat snapshot for the bot ---------------

def make_chat_snapshot(df: pd.DataFrame) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if df is None or df.empty:
        return out
    last = df.iloc[-1]

    def g(col):
        return float(last[col]) if col in df.columns and pd.notna(last[col]) else None

    out["last_close"]   = round(g("Close"), 2) if g("Close") is not None else None
    out["last_ema200"]  = round(g("EMA200"), 2) if g("EMA200") is not None else None
    out["last_atr14"]   = round(g("ATR14"), 2) if g("ATR14") is not None else None
    out["last_vwap"]    = round(g("VWAP"), 2) if g("VWAP") is not None else None
    out["last_rsi"]     = round(g("RSI"), 2) if g("RSI") is not None else None
    out["last_macd"]    = round(g("MACD"), 2) if g("MACD") is not None else None
    out["last_signal"]  = round(g("Signal"), 2) if g("Signal") is not None else None
    out["last_vtvr"]    = round(g("VTVR"), 2) if g("VTVR") is not None else None
    out["last_vtvr_z"]  = round(g("VTVR_z"), 2) if g("VTVR_z") is not None else None

    notes = []
    if out["last_close"] is not None and out["last_ema200"] is not None:
        if out["last_close"] > out["last_ema200"]:
            notes.append("Price above EMA200 (long-term up-bias).")
        elif out["last_close"] < out["last_ema200"]:
            notes.append("Price below EMA200 (long-term down-bias).")

    if out["last_rsi"] is not None:
        if out["last_rsi"] >= 70:
            notes.append("RSI overbought zone (≥70).")
        elif out["last_rsi"] <= 30:
            notes.append("RSI oversold zone (≤30).")

    if out["last_macd"] is not None and out["last_signal"] is not None:
        if out["last_macd"] > out["last_signal"]:
            notes.append("MACD above Signal (bullish momentum).")
        elif out["last_macd"] < out["last_signal"]:
            notes.append("MACD below Signal (bearish momentum).")

    out["notes"] = notes
    return out

# ----------------------- Plotly Figure --------------------
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def make_figure(
    df: pd.DataFrame,
    *,
    show_ema200: bool = True,
    show_atr: bool = True,
    show_vwap: bool = True,
    show_vtvr: bool = True,
    show_vtvr_z: bool = False,
):
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title="No data", height=900)
        return fig

    fig = make_subplots(
        rows=5, cols=1,
        specs=[
            [{"secondary_y": False}],  # Price
            [{"secondary_y": False}],  # MACD
            [{"secondary_y": False}],  # RSI
            [{"secondary_y": True}],   # Volume + VTVR_z
            [{"secondary_y": False}],  # ATR
        ],
        row_heights=[0.54, 0.12, 0.12, 0.12, 0.10],
    )

    # 1) Price
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Price", showlegend=False
    ), row=1, col=1)

    if show_ema200 and "EMA200" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["EMA200"], name="EMA200", mode="lines"), row=1, col=1)

    if show_vwap and "VWAP" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["VWAP"], name="VWAP", mode="lines"), row=1, col=1)

    # 2) MACD
    if "MACD" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", mode="lines"), row=2, col=1)
    if "Signal" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["Signal"], name="Signal", mode="lines"), row=2, col=1)

    # 3) RSI
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", mode="lines"), row=3, col=1)
        fig.update_yaxes(range=[0, 100], row=3, col=1)

    # 4) Volume + optional VTVR_z
    if "Volume" in df.columns:
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume", opacity=0.5), row=4, col=1, secondary_y=False)
    if show_vtvr and show_vtvr_z and "VTVR_z" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["VTVR_z"], name="VTVR_z", mode="lines"),
                      row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Volume", row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="VTVR_z", row=4, col=1, secondary_y=True)

    # 5) ATR
    if show_atr and "ATR14" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["ATR14"], name="ATR(14)", mode="lines"), row=5, col=1)

    fig.update_layout(
        height=900,
        margin=dict(l=40, r=20, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig
