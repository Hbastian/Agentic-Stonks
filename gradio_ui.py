
import gradio as gr
import yfinance as yf
import plotly.graph_objects as go
import datetime
import os
from typing import Dict, Tuple, Any
from openai import OpenAI
#import the following if running locally, otehrwise comment out
from dotenv import load_dotenv
from analysis import analyze_rsi, analyze_ema, analyze_macd
import gradio as gr

# ----- Data analysis -----
def stock_advisor(stock_symbol):
    rsi_result, _ = analyze_rsi(stock_symbol)
    ema_result, _ = analyze_ema(stock_symbol)
    macd_result, _ = analyze_macd(stock_symbol)

    return f"""
📊 Stock Analysis for {stock_symbol}:

- {rsi_result}
- {ema_result}
- {macd_result}
"""

# --- Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("# 📈 Agentic-Stonks")
    with gr.Tab("Stock Advisor"):
        stock_input = gr.Textbox(label="Stock Symbol", placeholder="e.g. AAPL")
        stock_output = gr.Textbox(label="Analysis")
        run_btn = gr.Button("Analyze")
        run_btn.click(stock_advisor, inputs=stock_input, outputs=stock_output)

#use if key is stored locally
load_dotenv()

# ---------- OpenAI setup ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- Allowed periods per interval ----------
ALLOWED_PERIODS: Dict[str, Tuple[str, ...]] = {
    "1m":  ("1d", "5d", "7d"),
    "2m":  ("1d", "5d", "7d", "1mo"),
    "5m":  ("1d", "5d", "7d", "1mo", "3mo"),
    "15m": ("1d", "5d", "7d", "1mo", "3mo"),
    "30m": ("1d", "5d", "7d", "1mo", "3mo"),
    "60m": ("1d", "5d", "7d", "1mo", "3mo"),
    "90m": ("1d", "5d", "7d", "1mo", "3mo"),
    "1h":  ("1d", "5d", "7d", "1mo", "3mo"),
}

_last_outputs: Dict[Tuple[str, str, str, bool, bool], Dict[str, Any]] = {}

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

def _clamp_period(interval: str, period_choice: str) -> Tuple[str, str]:
    allowed = ALLOWED_PERIODS.get(interval, ALLOWED_PERIODS["5m"])
    if period_choice in allowed:
        return period_choice, ""
    return allowed[-1], f"(clamped to {allowed[-1]} for {interval} data)"

def get_stock_info(ticker: str, interval: str, period_choice: str, show_ma: bool, show_volume: bool):
    interval = interval or "5m"
    period_choice = period_choice or "1d"
    effective_period, clamp_note = _clamp_period(interval, period_choice)
    key = (ticker or "", interval, effective_period, bool(show_ma), bool(show_volume))
    cached = _last_outputs.get(key, {"last_ts": None, "summary": "Waiting for data...", "fig": None, "updated": "—"})
    if not (ticker and ticker.strip()):
        return cached["summary"], cached["fig"], cached["updated"]
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=effective_period, interval=interval)
        if hist is None or hist.empty:
            return cached["summary"], cached["fig"], cached["updated"]
        current_last_ts = hist.index[-1]
        if cached["last_ts"] is not None and current_last_ts == cached["last_ts"]:
            return gr.update(), gr.update(), cached["updated"]
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
        _last_outputs[key] = {"last_ts": current_last_ts, "summary": summary, "fig": fig, "updated": updated}
        return summary, fig, updated
    except Exception:
        return cached["summary"], cached["fig"], cached["updated"]

# ---------- Chatbot ----------
def stock_chat(message, history):
    try:
        messages = [{"role": "system",
                     "content": "You are a helpful financial assistant. Answer questions about stocks clearly."}]

        # Flatten chat history safely
        for user, bot in history:
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": bot})

        # Add new user message
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

        with gr.Tab("Stock Advisor"): #Attaches the Stock Advisor to the UI
            stock_input = gr.Textbox(label="Stock Symbol", placeholder="e.g. AAPL")
            stock_output = gr.Markdown(label="Analysis")  # switched to Markdown
            run_btn = gr.Button("Analyze")
            run_btn.click(stock_advisor, inputs=stock_input, outputs=stock_output)

        with gr.Row():   # Side-by-side layout
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

                interval = gr.Radio(
                    label="Interval (minutes/hours)",
                    choices=["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"],
                    value="5m"
                )
                period_choice = gr.Radio(
                    label="Day length",
                    choices=["1d", "5d", "7d", "1mo", "3mo"],
                    value="1d",
                    info="Clamped to Yahoo limits."
                )
                show_ma = gr.Checkbox(label="Show MA-20 / MA-50", value=True)
                show_volume = gr.Checkbox(label="Show Volume Bars", value=True)

                stock_output = gr.Markdown()
                stock_chart = gr.Plot()
                last_updated = gr.Markdown()

                timer = gr.Timer(30.0)

                # logic for updates
                def pick_ticker(drop_val, text_val, *args):
                    ticker = text_val.strip().upper() if text_val.strip() else drop_val
                    return get_stock_info(ticker, *args)

                ticker_dropdown.change(
                    fn=get_stock_info,
                    inputs=[ticker_dropdown, interval, period_choice, show_ma, show_volume],
                    outputs=[stock_output, stock_chart, last_updated]
                )
                ticker_textbox.change(
                    fn=get_stock_info,
                    inputs=[ticker_textbox, interval, period_choice, show_ma, show_volume],
                    outputs=[stock_output, stock_chart, last_updated]
                )
                timer.tick(
                    fn=pick_ticker,
                    inputs=[ticker_dropdown, ticker_textbox, interval, period_choice, show_ma, show_volume],
                    outputs=[stock_output, stock_chart, last_updated]
                )

            # ----- RIGHT: Chatbox -----
            with gr.Column(scale=1):
                gr.ChatInterface(
                    fn=stock_chat,
                    title="💬 Stock Assistant",
                    description="Ask me questions about stocks while watching the chart!"
                )
    return demo


# ------ Entry point -----
if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860) # Change server port to match the server you're using