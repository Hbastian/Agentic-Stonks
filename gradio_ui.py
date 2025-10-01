import gradio as gr
import yfinance as yf
import plotly.graph_objects as go
import datetime
import os
import math
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
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

# ---------- Helper: Format large numbers ----------
def _format_number(val):
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

# ---------- Technical Indicators ----------
def analyze_rsi(hist):
    delta = hist["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1)
    rsi = 100 - (100 / (1 + rs))
    latest = rsi.iloc[-1]
    if latest > 70:
        verdict = "Overbought"
    elif latest < 30:
        verdict = "Oversold"
    else:
        verdict = "Neutral"
    return f"RSI: {latest:.2f} ({verdict})"

def analyze_ema(hist):
    ema20 = hist["Close"].ewm(span=20, adjust=False).mean()
    ema50 = hist["Close"].ewm(span=50, adjust=False).mean()
    latest20, latest50 = ema20.iloc[-1], ema50.iloc[-1]
    if latest20 > latest50:
        verdict = "Bullish (EMA20 above EMA50)"
    else:
        verdict = "Bearish (EMA20 below EMA50)"
    return f"EMA: 20-day={latest20:.2f}, 50-day={latest50:.2f} → {verdict}"

def analyze_macd(hist):
    ema12 = hist["Close"].ewm(span=12, adjust=False).mean()
    ema26 = hist["Close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    latest_macd, latest_signal = macd.iloc[-1], signal.iloc[-1]
    if latest_macd > latest_signal:
        verdict = "Bullish (MACD above Signal)"
    else:
        verdict = "Bearish (MACD below Signal)"
    return f"MACD: {latest_macd:.2f} vs Signal={latest_signal:.2f} → {verdict}"

# ---------- Indicator Collector ----------
def collect_indicators(ticker: str, view_choice: str, period_choice: str):
    interval = _choose_interval(view_choice, period_choice)
    effective_period = period_choice or "6mo"

    stock = yf.Ticker(ticker)
    hist = stock.history(period=effective_period, interval=interval)
    if hist.empty:
        return {}

    ma20 = hist["Close"].rolling(window=20).mean().iloc[-1]
    ma50 = hist["Close"].rolling(window=50).mean().iloc[-1]

    return {
        "MA20": f"MA20: {ma20:.2f}",
        "MA50": f"MA50: {ma50:.2f}",
        "RSI": analyze_rsi(hist),
        "EMA": analyze_ema(hist),
        "MACD": analyze_macd(hist),
        "Timeframe": f"{effective_period}, interval={interval}"
    }

# ---------- Interval chooser ----------
def _choose_interval(view_choice: str, period_choice: str) -> str:
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
                                     "fig": None, "updated": "—",
                                     "indicators": {}})

    if not (ticker and ticker.strip()):
        return cached["summary"], cached["fig"], cached["updated"], cached["indicators"]
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=effective_period, interval=interval)
        if hist is None or hist.empty:
            return cached["summary"], cached["fig"], cached["updated"], cached["indicators"]
        current_last_ts = hist.index[-1]
        if cached["last_ts"] is not None and current_last_ts == cached["last_ts"]:
            return gr.update(), gr.update(), cached["updated"], cached["indicators"]

        info = stock.info
        summary = (
            f"### {info.get('shortName', ticker)} ({ticker.upper()})\n\n"
            f"💰 **Current Price:** {info.get('currentPrice', 'N/A')}\n"
            f"📉 **Previous Close:** {info.get('previousClose', 'N/A')}\n\n"
            f"🏦 **Market Cap:** {_format_number(info.get('marketCap'))}\n"
            f"📊 **Volume:** {_format_number(info.get('volume'))}\n\n"
            f"📈 **52W High:** {info.get('fiftyTwoWeekHigh', 'N/A')}\n"
            f"📉 **52W Low:** {info.get('fiftyTwoWeekLow', 'N/A')}\n"
        )

        title = f"{ticker.upper()} — {view_choice} view over {effective_period} (interval={interval})"
        fig = _build_chart(hist, show_ma, show_volume, title)
        updated = datetime.datetime.now().strftime("Last updated: %Y-%m-%d %H:%M:%S")

        indicators = collect_indicators(ticker, view_choice, period_choice)

        _last_outputs[key] = {"last_ts": current_last_ts,
                              "summary": summary, "fig": fig, "updated": updated, "indicators": indicators}
        return summary, fig, updated, indicators
    except Exception:
        return cached["summary"], cached["fig"], cached["updated"], cached["indicators"]

# ---------- Chatbot ----------
def stock_chat(message, history, ticker="AAPL", view_choice="Daily", period_choice="6mo"):
    try:
        indicators = collect_indicators(ticker, view_choice, period_choice)
        context = (
            f"Ticker: {ticker.upper()} | View: {view_choice}, Timeframe: {period_choice}\n" +
            "\n".join([f"{v}" for v in indicators.values() if v]) + "\n\n"
        )

        messages = [
            {"role": "system", "content": "You are a helpful financial assistant. Use the stock indicators provided when answering."},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": context + message})

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# ---------- UI Builder ----------
def build_ui():
    with gr.Blocks(title="AgenticStonks Dashboard") as demo:
        gr.Markdown("# 📈 AgenticStonks Dashboard")

        current_ticker = gr.State("AAPL")
        current_view = gr.State("Daily")
        current_period = gr.State("6mo")

        with gr.Row():
            # ----- LEFT: Stock Viewer (wider) -----
            with gr.Column(scale=3):
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
                    view_choice = gr.Radio(label="View Type", choices=["Daily", "Weekly"], value="Daily")
                    period_choice = gr.Radio(label="Time Frame", choices=ALLOWED_PERIODS, value="6mo")
                    show_ma = gr.Checkbox(label="Show MA-20 / MA-50", value=True)
                    show_volume = gr.Checkbox(label="Show Volume Bars", value=True)

                default_summary, default_chart, default_updated, default_indicators = get_stock_info("AAPL", "Daily", "6mo", True, True)

                with gr.Row():
                    with gr.Column(scale=2):
                        stock_output = gr.Markdown(value=default_summary)
                    with gr.Column(scale=1):
                        gr.Markdown("### 📊 Indicators")
                        rsi_out = gr.Markdown(value=default_indicators.get("RSI", ""))
                        ema_out = gr.Markdown(value=default_indicators.get("EMA", ""))
                        macd_out = gr.Markdown(value=default_indicators.get("MACD", ""))
                        ma20_out = gr.Markdown(value=default_indicators.get("MA20", ""))
                        ma50_out = gr.Markdown(value=default_indicators.get("MA50", ""))

                stock_chart = gr.Plot(value=default_chart)
                last_updated = gr.Markdown(value=default_updated)

                def _inputs_for(fn):
                    return dict(
                        fn=lambda dropdown_val, textbox_val, view, period, ma, volume: fn(
                            textbox_val.strip().upper() if textbox_val.strip() else dropdown_val,
                            view, period, ma, volume
                        ),
                        inputs=[ticker_dropdown, ticker_textbox, view_choice, period_choice, show_ma, show_volume],
                        outputs=[stock_output, stock_chart, last_updated, rsi_out, ema_out, macd_out, ma20_out, ma50_out]
                    )

                ticker_dropdown.change(**_inputs_for(get_stock_info))
                ticker_textbox.change(**_inputs_for(get_stock_info))
                view_choice.change(**_inputs_for(get_stock_info))
                period_choice.change(**_inputs_for(get_stock_info))
                show_ma.change(**_inputs_for(get_stock_info))
                show_volume.change(**_inputs_for(get_stock_info))

                gr.Timer(30.0).tick(
                    fn=lambda dropdown_val, textbox_val, view, period, ma, volume: get_stock_info(
                        textbox_val.strip().upper() if textbox_val.strip() else dropdown_val,
                        view, period, ma, volume
                    ),
                    inputs=[ticker_dropdown, ticker_textbox, view_choice, period_choice, show_ma, show_volume],
                    outputs=[stock_output, stock_chart, last_updated, rsi_out, ema_out, macd_out, ma20_out, ma50_out]
                )

            # ----- RIGHT: Chatbox (narrower) -----
            with gr.Column(scale=1):
                gr.ChatInterface(
                    fn=lambda m, h: stock_chat(m, h, ticker_dropdown.value or ticker_textbox.value or "AAPL",
                                               view_choice.value, period_choice.value),
                    type="messages",
                    title="💬 Stonk Assistant",
                    description="Ask me questions about stocks while watching the chart!"
                )

    return demo

# ---------- Entry Point ----------
if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860)
