# analysis.py — v2 (dark UI, volume profile, fibs, Insight Card HTML)
from __future__ import annotations
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from dataclasses import dataclass

# ----------------------------
# Data fetch
# ----------------------------
def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval, auto_adjust=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)
    return df

# ----------------------------
# Indicators
# ----------------------------
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # EMAs
    out["EMA20"]  = out["Close"].ewm(span=20, adjust=False).mean()
    out["EMA50"]  = out["Close"].ewm(span=50, adjust=False).mean()
    out["EMA200"] = out["Close"].ewm(span=200, adjust=False).mean()

    # Bollinger (20,2)
    ma20  = out["Close"].rolling(20).mean()
    std20 = out["Close"].rolling(20).std(ddof=0)
    out["BB_upper"] = ma20 + 2 * std20
    out["BB_lower"] = ma20 - 2 * std20

    # MACD (12,26,9)
    ema12 = out["Close"].ewm(span=12, adjust=False).mean()
    ema26 = out["Close"].ewm(span=26, adjust=False).mean()
    out["MACD"]        = ema12 - ema26
    out["MACD_signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_hist"]   = out["MACD"] - out["MACD_signal"]

    # Cross flag
    pm, ps = out["MACD"].shift(1), out["MACD_signal"].shift(1)
    out["MACD_cross"] = np.where(
        (pm < ps) & (out["MACD"] > out["MACD_signal"]), "Bullish",
        np.where((pm > ps) & (out["MACD"] < out["MACD_signal"]), "Bearish", "")
    )

    # RSI(14) (Wilder)
    d = out["Close"].diff()
    up = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))
    out["RSI_state"] = pd.cut(out["RSI"], [-np.inf, 30, 70, np.inf],
                              labels=["Oversold", "Neutral", "Overbought"])

    # Regime
    out["Trend"] = np.where(out["EMA20"] > out["EMA50"], "Uptrend",
                     np.where(out["EMA20"] < out["EMA50"], "Downtrend", "Range"))
    return out

# ----------------------------
# Volume profile (horizontal by price)
# ----------------------------
def compute_volume_profile(df: pd.DataFrame, bins: int = 40):
    if df.empty:
        return None
    lo, hi = float(df["Low"].min()), float(df["High"].max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return None
    prices = df["Close"].to_numpy()
    vols   = df["Volume"].to_numpy()
    counts, edges = np.histogram(prices, bins=bins, range=(lo, hi), weights=vols)
    centers = (edges[:-1] + edges[1:]) / 2.0
    return {
        "price_centers": centers,
        "volume": counts,
        "poc_price": centers[np.argmax(counts)] if np.any(counts) else np.nan
    }

# ----------------------------
# Fibonacci retracement (recent swing)
# ----------------------------
def compute_fibs(df: pd.DataFrame, lookback: int = 120):
    if df.empty:
        return {}
    sub = df.tail(lookback) if len(df) > lookback else df
    hi, lo = float(sub["High"].max()), float(sub["Low"].min())
    if not np.isfinite(hi) or not np.isfinite(lo) or hi == lo:
        return {}
    levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    fibs = {f"{int(l*100)}%": hi - (hi - lo)*l for l in levels}
    return {"high": hi, "low": lo, "levels": fibs}

# ----------------------------
# Risk metrics
# ----------------------------
@dataclass
class RiskCard:
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float

def compute_risk(df: pd.DataFrame, window: int = 252) -> RiskCard:
    if df.empty or len(df) < max(30, window // 4):
        return RiskCard(np.nan, np.nan, np.nan, np.nan, np.nan)
    px = df["Close"]
    r  = px.pct_change().dropna()
    ann = np.sqrt(252)
    p0, p1 = px.iloc[-min(window, len(px))], px.iloc[-1]
    cagr = (p1/p0)**(252/min(window, len(px))) - 1
    vol = r.std()*ann
    mean_ann = r.mean()*252
    sharpe  = mean_ann/vol if vol else np.nan
    dn = r[r<0]; sortino = mean_ann/(dn.std()*ann) if len(dn)>0 else np.nan
    mdd = (px/px.cummax() - 1).min()
    return RiskCard(cagr, vol, sharpe, sortino, mdd)

def _pct(x):  return f"{x*100:.2f}%" if np.isfinite(x) else "—"
def _fmt(x):  return f"{x:.2f}" if np.isfinite(x) else "—"

# ----------------------------
# Insight Card (HTML)
# ----------------------------
def insight_html(df: pd.DataFrame, risk: RiskCard, profile: dict, fibs: dict) -> str:
    last = df.iloc[-1]
    poc_html = f"<div><b>POC</b>: ${profile['poc_price']:.2f}</div>" if profile and np.isfinite(profile.get("poc_price", np.nan)) else ""
    fib_html = ""
    if fibs and "levels" in fibs:
        keep = [k for k in ("38%","50%","62%","61%") if k in fibs["levels"]]
        if keep:
            fib_html = "<div><b>Fibs</b>: " + ", ".join([f"{k} ≈ ${fibs['levels'][k]:.2f}" for k in keep]) + "</div>"

    return f"""
<details open class="insight">
  <summary>📊 Insight Card</summary>
  <div class="i-row"><span>📈 <b>Trend</b></span><span>{last['Trend']} (EMA20 {last['EMA20']:.2f} vs EMA50 {last['EMA50']:.2f})</span></div>
  <div class="i-row"><span>⚡ <b>Momentum (MACD)</b></span><span>{last['MACD']:.2f} vs {last['MACD_signal']:.2f} (hist {'pos' if last['MACD_hist']>0 else 'neg'})</span></div>
  <div class="i-row"><span>💧 <b>RSI</b></span><span>{last['RSI']:.1f} → {str(last['RSI_state'])}</span></div>
  {f'<div class="i-row"><span>🎯 <b>Volume Profile</b></span><span>{poc_html}</span></div>' if poc_html else ''}
  {f'<div class="i-row"><span>📐 <b>Retracements</b></span><span>{fib_html}</span></div>' if fib_html else ''}
  <div class="i-row"><span>🛡 <b>Risk (~1y)</b></span>
      <span>Sharpe {_fmt(risk.sharpe)} · Sortino {_fmt(risk.sortino)} · Vol {_pct(risk.volatility)} · MaxDD {_pct(risk.max_drawdown)} · CAGR {_pct(risk.cagr)}</span>
  </div>
  <div class="i-foot">Simple reading: Trend = direction, MACD = momentum, RSI = “hot/cold”, POC/Fibs = likely pause or bounce zones.</div>
</details>
"""

# ----------------------------
# Plotly figure (dark)
# ----------------------------
def make_figure(df: pd.DataFrame, profile: dict, fibs: dict) -> go.Figure:
    fig = go.Figure()
    # Price panel
    for tr in [
        go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price"),
        go.Scatter(x=df.index, y=df["EMA20"],  name="EMA20",  mode="lines"),
        go.Scatter(x=df.index, y=df["EMA50"],  name="EMA50",  mode="lines"),
        go.Scatter(x=df.index, y=df["BB_upper"], name="BB Upper", mode="lines"),
        go.Scatter(x=df.index, y=df["BB_lower"], name="BB Lower", mode="lines"),
    ]: fig.add_trace(tr)

    # Fibs
    if fibs and "levels" in fibs:
        for label, y in fibs["levels"].items():
            fig.add_hline(y=y, line_dash="dot", line_width=1,
                          annotation_text=f"Fib {label}", annotation_position="right")

    # Volume Profile (right rail)
    if profile:
        fig.add_trace(go.Bar(
            x=profile["volume"], y=profile["price_centers"],
            orientation="h", name="Volume Profile", opacity=0.5,
            xaxis="x5", yaxis="y", showlegend=False
        ))
        if np.isfinite(profile.get("poc_price", np.nan)):
            fig.add_hline(y=profile["poc_price"], line_color="orange", line_width=2,
                          annotation_text="POC", annotation_position="right")

    # MACD / RSI / Volume
    for tr in [
        go.Scatter(x=df.index, y=df["MACD"], name="MACD", xaxis="x2", yaxis="y2"),
        go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal", xaxis="x2", yaxis="y2"),
        go.Bar(x=df.index, y=df["MACD_hist"], name="Hist", xaxis="x2", yaxis="y2", opacity=0.6),
        go.Scatter(x=df.index, y=df["RSI"], name="RSI(14)", xaxis="x3", yaxis="y3"),
        go.Bar(x=df.index, y=df["Volume"], name="Volume", xaxis="x4", yaxis="y4"),
    ]: fig.add_trace(tr)

    fig.update_layout(
        height=700, template="plotly_dark", hovermode="x unified",
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(domain=[0.0, 0.80]),
        yaxis=dict(domain=[0.58, 1.0], title="Price"),
        xaxis5=dict(domain=[0.82, 1.0], showticklabels=False),
        xaxis2=dict(domain=[0,1], anchor="y2"),
        yaxis2=dict(domain=[0.40,0.56], title="MACD"),
        xaxis3=dict(domain=[0,1], anchor="y3"),
        yaxis3=dict(domain=[0.24,0.38], title="RSI", range=[0,100]),
        xaxis4=dict(domain=[0,1], anchor="y4"),
        yaxis4=dict(domain=[0,0.22], title="Volume"),
    )
    fig.add_hrect(yref="y3", y0=70, y1=100, line_width=0, fillcolor="rgba(200,50,50,0.08)")
    fig.add_hrect(yref="y3", y0=0,  y1=30,  line_width=0, fillcolor="rgba(50,200,50,0.08)")
    return fig

# ----------------------------
# Public API
# ----------------------------
def analyze_ticker(ticker: str, period="1y", interval="1d"):
    df = fetch_ohlcv(ticker, period, interval)
    if df.empty:
        return None, "<div class='i-foot'>No data for ticker.</div>", {}
    df = compute_indicators(df)
    profile = compute_volume_profile(df, bins=40)
    fibs    = compute_fibs(df, lookback=120)
    risk    = compute_risk(df)
    fig     = make_figure(df, profile, fibs)
    card    = insight_html(df, risk, profile, fibs)
    context = {
        "ticker": ticker,
        "price": float(df["Close"].iloc[-1]),
        "trend": str(df["Trend"].iloc[-1]),
        "rsi": float(df["RSI"].iloc[-1]),
        "macd": float(df["MACD"].iloc[-1]),
        "macd_signal": float(df["MACD_signal"].iloc[-1]),
        "poc": float(profile["poc_price"]) if profile and np.isfinite(profile.get("poc_price", np.nan)) else None,
        "fibs": fibs.get("levels", {}) if fibs else {},
    }
    return fig, card, context
