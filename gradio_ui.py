import gradio as gr
import yfinance as yf
import plotly.graph_objects as go
import datetime
import os
import math
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load env for local dev
load_dotenv()

# ---------- OpenAI setup ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- View to interval mapping ----------
VIEW_INTERVALS = {
    "Daily": "1h",   # hourly candles
    "Weekly": "1d",  # daily candles
}

# ---------- Allowed periods ----------
ALLOWED_PERIODS = ["3mo", "6mo", "1y", "2y", "3y"]

# ---------- Cache + top-of-hour guard ----------
_last_outputs: Dict[tuple, Dict[str, Any]] = {}
_last_top_hour_key = None  # (year, month, day, hour)

# ---------- Chart builder ----------
def _build_chart(hist, show_ma: bool, show_volume: bool, title: str):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"], name="Price"
    ))
    if show_ma and not hist.empty:
        ma20 = hist["Close"].rolling(window=20).mean()
        ma50 = hist["Close"].rolling(window=50).mean()
        fig.add_trace(go.Scatter(x=hist.index, y=ma20, mode="lines",
                                 name="MA-20", line=dict(color="yellow", width=1.5)))
        fig.add_trace(go.Scatter(x=hist.index, y=ma50, mode="lines",
                                 name="MA-50", line=dict(color="cyan", width=1.5)))
    if show_volume and "Volume" in hist.columns:
        colors = ["green" if row["Close"] > row["Open"] else "red" for _, row in hist.iterrows()]
        fig.add_trace(go.Bar(
            x=hist.index, y=hist["Volume"], name="Volume",
            marker_color=colors, yaxis="y2", opacity=0.3
        ))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Volume"))
    fig.update_layout(
        title=title, yaxis_title="Price (USD)", xaxis_title="Date",
        xaxis_rangeslider_visible=False, template="plotly_dark",
        legend=dict(orientation="h", y=-0.25)
    )
    return fig

# ---------- Formatter for summary ----------
def _format_number(val):
    """Format large numbers into human-friendly strings (e.g., 1.2B)."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/A"
    try:
        val = float(val)
        if val >= 1e12:
            return f"{val/1e12:.2f}T"
        elif val >= 1e9:
            return f"{val/1e9:.2f}B"
        elif val >= 1e6:
            return f"{val/1e6:.2f}M"
        elif val >= 1e3:
            return f"{val/1e3:.2f}K"
        else:
            return f"{val:.2f}"
    except Exception:
        return str(val)

# ---------- Summary builder ----------
def _build_summary(info, ticker: str):
    return (
        f"### {info.get('shortName', ticker)} ({ticker.upper()})\n\n"
        f"💰 **Current Price:** {info.get('currentPrice', 'N/A')}\n"
        f"📉 **Previous Close:** {info.get('previousClose', 'N/A')}\n\n"
        f"🏦 **Market Cap:** {_format_number(info.get('marketCap'))}\n"
        f"📊 **Volume:** {_format_number(info.get('volume'))}\n\n"
        f"📈 **52W High:** {info.get('fiftyTwoWeekHigh', 'N/A')}\n"
        f"📉 **52W Low:** {info.get('fiftyTwoWeekLow', 'N/A')}\n"
    )

# ---------- Interval chooser ----------
def _choose_interval(view_choice: str, period_choice: str) -> str:
    """
    Pick a safe interval for Yahoo Finance:
    - If period is 1y, 2y, or 3y → use daily candles (1d)
    - Else → follow the view mapping (Daily=1h, Weekly=1d)
    """
    if period_choice in ["1y", "2y", "3y"]:
        return "1d"
    return VIEW_INTERVALS.get(view_choice, "1d")

# ---------- Data fetcher ----------
def get_stock_info(ticker: str, view_choice: str, period_choice: str,
                   show_ma: bool, show_volume: bool):
    interval = _choose_interval(view_choice, period_choice)
    effective_period = period_choice or "6mo"

    key = (ticker or "", view_choice, effective_period, bool(show_ma), bool(show_volume))
    cached = _last_outputs.get(key, {"last_ts": None, "summary": "Waiting for data...",
                                     "fig": None, "updated": "—"})

    if not (ticker and ticker.strip()):
        return cached["summary"], cached["fig"], cached["updated"]

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=effective_period, interval=interval)
        if hist is None or hist.empty:
            return cached["summary"], cached["fig"], cached["updated"]

        current_last_ts = hist.index[-1]
        if cached["last_ts"] is not None and current_last_ts == cached["last_ts"]:
            # No new data point → keep existing components
            return gr.update(), gr.update(), cached["updated"]

        info = stock.info
        summary = _build_summary(info, ticker)

        title = f"{ticker.upper()} — {view_choice} view over {effective_period} (interval={interval})"
        fig = _build_chart(hist, show_ma, show_volume, title)
        updated = datetime.datetime.now().strftime("Last updated: %Y-%m-%d %H:%M:%S")

        _last_outputs[key] = {"last_ts": current_last_ts,
                              "summary": summary, "fig": fig, "updated": updated}
        return summary, fig, updated
    except Exception:
        return cached["summary"], cached["fig"], cached["updated"]

# ---------- Top-of-hour timer callback ----------
def _maybe_top_of_hour_refresh(drop_val, text_val, view_choice, period_choice, show_ma, show_volume):
    """Refresh exactly once per hour at minute==00, else no-op."""
    global _last_top_hour_key
    now = datetime.datetime.now()
    top_key = (now.year, now.month, now.day, now.hour)

    if now.minute == 0:
        if _last_top_hour_key != top_key:
            _last_top_hour_key = top_key
            ticker = text_val.strip().upper() if text_val.strip() else drop_val
            return get_stock_info(ticker, view_choice, period_choice, show_ma, show_volume)

    # No changes → keep current UI
    return gr.update(), gr.update(), gr.update()

# ---------- Chatbot ----------
def stock_chat(message, history):
    try:
        messages = [{"role": "system",
                     "content": "You are a helpful financial assistant. Answer questions about stocks clearly."}]
        for user, bot in history:
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": bot})
        messages.append({"role": "user", "content": message})

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# ---------- UI Builder ----------
def build_ui():
    with gr.Blocks(title="Stock Viewer + Chat") as demo:
        gr.Markdown("# 📈 AgenticStonks Dashboard")

        with gr.Row():
            # ----- LEFT: Stock Viewer -----
            with gr.Column(scale=2):
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

                view_choice = gr.Radio(
                    label="View Type",
                    choices=["Daily", "Weekly"],
                    value="Daily"
                )

                period_choice = gr.Radio(
                    label="Time Frame",
                    choices=ALLOWED_PERIODS,
                    value="6mo"
                )

                show_ma = gr.Checkbox(label="Show MA-20 / MA-50", value=True)
                show_volume = gr.Checkbox(label="Show Volume Bars", value=True)

                # 🔹 Preload AAPL so the app isn't blank on open
                default_summary, default_chart, default_updated = get_stock_info(
                    "AAPL", "Daily", "6mo", True, True
                )

                stock_output = gr.Markdown(value=default_summary)
                stock_chart = gr.Plot(value=default_chart)
                last_updated = gr.Markdown(value=default_updated)

                # --- Refresh on user changes ---
                def _inputs_for(fn):
                    return dict(
                        fn=fn,
                        inputs=[ticker_dropdown, view_choice, period_choice, show_ma, show_volume],
                        outputs=[stock_output, stock_chart, last_updated]
                    )

                ticker_dropdown.change(**_inputs_for(get_stock_info))
                ticker_textbox.change(
                    fn=lambda text_val, *rest: get_stock_info(
                        text_val.strip().upper() if text_val.strip() else ticker_dropdown.value, *rest
                    ),
                    inputs=[ticker_textbox, view_choice, period_choice, show_ma, show_volume],
                    outputs=[stock_output, stock_chart, last_updated]
                )

                view_choice.change(**_inputs_for(get_stock_info))
                period_choice.change(**_inputs_for(get_stock_info))
                show_ma.change(**_inputs_for(get_stock_info))
                show_volume.change(**_inputs_for(get_stock_info))

                # --- Top-of-hour auto refresh ---
                gr.Timer(30.0).tick(
                    fn=_maybe_top_of_hour_refresh,
                    inputs=[ticker_dropdown, ticker_textbox, view_choice, period_choice, show_ma, show_volume],
                    outputs=[stock_output, stock_chart, last_updated]
                )

            # ----- RIGHT: Chatbox -----
            with gr.Column(scale=1):
                gr.ChatInterface(
                    fn=stock_chat,
                    type="messages",
                    title="💬 Stonk Assistant",
                    description="Ask me questions about stocks while watching the chart!"
                )

    return demo