# gradio_ui.py
# ------------------------------------------------------------
# Stock Viewer (Interval + Day-Length selectors, anti-flicker)
# - Candlesticks (Plotly)
# - Optional MA-20 / MA-50 + Volume bars
# - Interval (minutes/hours) and day-length selection with clamping
# ------------------------------------------------------------

import gradio as gr
import yfinance as yf
import plotly.graph_objects as go
import datetime
from typing import Dict, Tuple, Any

# ---------- Allowed periods per interval (clamped if needed) ----------
# These reflect practical Yahoo limits; 1m is restricted to short windows.
ALLOWED_PERIODS: Dict[str, Tuple[str, ...]] = {
    "1m":  ("1d", "5d", "7d"),
    "2m":  ("1d", "5d", "7d", "1mo"),
    "5m":  ("1d", "5d", "7d", "1mo", "3mo"),
    "15m": ("1d", "5d", "7d", "1mo", "3mo"),
    "30m": ("1d", "5d", "7d", "1mo", "3mo"),
    "60m": ("1d", "5d", "7d", "1mo", "3mo"),
    "90m": ("1d", "5d", "7d", "1mo", "3mo"),
    "1h":  ("1d", "5d", "7d", "1mo", "3mo"),  # yfinance also accepts "1h"
}

# ---------- Cache to avoid flicker ----------
_last_outputs: Dict[Tuple[str, str, str, bool, bool], Dict[str, Any]] = {}
# key: (ticker, interval, period, show_ma, show_volume)
# val: { "last_ts": pd.Timestamp|None, "summary": str, "fig": go.Figure, "updated": str }

def _build_chart(hist, show_ma: bool, show_volume: bool, title: str):
    fig = go.Figure()

    # Candles
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"], name="Price"
    ))

    # MAs
    if show_ma and not hist.empty:
        ma20 = hist["Close"].rolling(window=20).mean()
        ma50 = hist["Close"].rolling(window=50).mean()
        fig.add_trace(go.Scatter(x=hist.index, y=ma20, mode="lines",
                                 name="MA-20", line=dict(color="yellow", width=1.5)))
        fig.add_trace(go.Scatter(x=hist.index, y=ma50, mode="lines",
                                 name="MA-50", line=dict(color="cyan", width=1.5)))

    # Volume (secondary axis)
    if show_volume and "Volume" in hist.columns:
        colors = ["green" if row["Close"] > row["Open"] else "red" for _, row in hist.iterrows()]
        fig.add_trace(go.Bar(
            x=hist.index, y=hist["Volume"], name="Volume",
            marker_color=colors, yaxis="y2", opacity=0.3
        ))
        fig.update_layout(
            yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Volume")
        )

    fig.update_layout(
        title=title,
        yaxis_title="Price (USD)",
        xaxis_title="Date",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        legend=dict(orientation="h", y=-0.25)
    )
    return fig

def _clamp_period(interval: str, period_choice: str) -> Tuple[str, str]:
    """Ensure the chosen period is valid for the interval; return (effective_period, note)."""
    allowed = ALLOWED_PERIODS.get(interval, ALLOWED_PERIODS["5m"])
    if period_choice in allowed:
        return period_choice, ""
    # clamp to the max allowed (last element)
    return allowed[-1], f"(clamped to {allowed[-1]} for {interval} data)"

def get_stock_info(ticker: str, interval: str, period_choice: str, show_ma: bool, show_volume: bool):
    """
    Returns (summary_markdown, plotly_figure, last_updated_text)
    - Uses interval + period (day-length)
    - Only updates when a new candle arrives to avoid flicker
    - Clamps invalid combos (e.g., 1m with 3mo) and shows a small note
    """
    interval = interval or "5m"
    period_choice = period_choice or "1d"
    effective_period, clamp_note = _clamp_period(interval, period_choice)

    key = (ticker or "", interval, effective_period, bool(show_ma), bool(show_volume))
    cached = _last_outputs.get(key, {"last_ts": None, "summary": "Waiting for data...", "fig": None, "updated": "—"})

    if not (ticker and ticker.strip()):
        return cached["summary"], cached["fig"], cached["updated"]

    try:
        stock = yf.Ticker(ticker)

        # Fetch with interval + period
        hist = stock.history(period=effective_period, interval=interval)
        if hist is None or hist.empty:
            # Keep last good state (no flashing)
            return cached["summary"], cached["fig"], cached["updated"]

        # Detect new candle (by index)
        current_last_ts = hist.index[-1]
        if cached["last_ts"] is not None and current_last_ts == cached["last_ts"]:
            # No change → don't touch components (prevents flicker)
            return gr.update(), gr.update(), cached["updated"]

        # Build summary (stable — no embedded timestamp)
        info = stock.info
        summary = (
            f"### {info.get('shortName', ticker)} ({ticker.upper()})\n\n"
            f"**Current Price:** {info.get('currentPrice', 'N/A')}\n"
            f"**Previous Close:** {info.get('previousClose', 'N/A')}\n"
            f"**Market Cap:** {info.get('marketCap', 'N/A')}\n"
            f"**Volume:** {info.get('volume', 'N/A')}\n"
            f"**52 Week High:** {info.get('fiftyTwoWeekHigh', 'N/A')}\n"
            f"**52 Week Low:** {info.get('fiftyTwoWeekLow', 'N/A')}\n"
        )

        title = f"{ticker.upper()} — {interval} over {effective_period}"
        fig = _build_chart(hist, show_ma, show_volume, title)

        note = (" " + clamp_note) if clamp_note else ""
        updated = datetime.datetime.now().strftime(f"Last updated: %Y-%m-%d %H:%M:%S{note}")

        # Cache fresh state
        _last_outputs[key] = {
            "last_ts": current_last_ts,
            "summary": summary,
            "fig": fig,
            "updated": updated,
        }

        return summary, fig, updated

    except Exception:
        # On any error, keep last state (no flashing)
        return cached["summary"], cached["fig"], cached["updated"]

def build_ui():
    with gr.Blocks(title="Stock Viewer (Custom Ticker)") as demo:
        gr.Markdown("# 📈 AgenticStonks")

        with gr.Row():
            ticker_dropdown = gr.Dropdown(
                label="Select Stock Symbol (Quick Picks)",
                choices=["AAPL", "TSLA", "MSFT", "AMZN", "GOOG", "META", "NVDA"],
                value="AAPL"
            )
            ticker_textbox = gr.Textbox(
                label="Or type your own ticker",
                placeholder="e.g. AMD, SPY, NFLX",
                value="",
            )

        # Interval selector
        interval = gr.Radio(
            label="Interval (minutes/hours)",
            choices=["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"],
            value="5m"
        )

        # Day-length selector
        period_choice = gr.Radio(
            label="Day length",
            choices=["1d", "5d", "7d", "1mo", "3mo"],
            value="1d",
            info="Combinations are clamped to what Yahoo allows for each interval."
        )

        # Optional features
        show_ma = gr.Checkbox(label="Show Moving Averages (MA-20, MA-50)", value=True)
        show_volume = gr.Checkbox(label="Show Volume Bars", value=True)

        # Outputs
        stock_output = gr.Markdown()
        stock_chart = gr.Plot()
        last_updated = gr.Markdown()

        timer = gr.Timer(30.0)

        # --- Logic for ticker selection ---
        # When dropdown changes, update chart
        ticker_dropdown.change(
            fn=get_stock_info,
            inputs=[ticker_dropdown, interval, period_choice, show_ma, show_volume],
            outputs=[stock_output, stock_chart, last_updated]
        )

        # When textbox changes, update chart
        ticker_textbox.change(
            fn=get_stock_info,
            inputs=[ticker_textbox, interval, period_choice, show_ma, show_volume],
            outputs=[stock_output, stock_chart, last_updated]
        )

        # Timer refresh → use textbox if filled, otherwise dropdown
        def pick_ticker(drop_val, text_val, *args):
            ticker = text_val.strip().upper() if text_val.strip() else drop_val
            return get_stock_info(ticker, *args)

        timer.tick(
            fn=pick_ticker,
            inputs=[ticker_dropdown, ticker_textbox, interval, period_choice, show_ma, show_volume],
            outputs=[stock_output, stock_chart, last_updated]
        )

    return demo
