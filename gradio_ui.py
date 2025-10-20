# gradio_ui.py — v2 (two columns: chart + collapsible insight card | chat on right)
import os
import gradio as gr
image_path = os.path.join("images", "Agentic-Stonks.png")
from dotenv import load_dotenv
from analysis import analyze_ticker

# Optional OpenAI chat (conversational replies)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    try:
        from openai import OpenAI

        _client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        _client = None
else:
    _client = None

load_dotenv()
DEFAULT_TICKER = "AAPL"
LATEST_CONTEXT = {"ticker": DEFAULT_TICKER}


def run_analysis(ticker_dd, ticker_txt, period, interval):
    ticker = (ticker_txt or "").strip().upper() or (ticker_dd or DEFAULT_TICKER)
    fig, card_html, ctx = analyze_ticker(ticker, period=period, interval=interval)
    global LATEST_CONTEXT
    LATEST_CONTEXT = ctx or {"ticker": ticker}
    return fig, card_html


def chat_reply(message, history):
    """
    Conversational, beginner-friendly helper.
    Uses OpenAI if available; otherwise a simple on-device explainer.
    """
    ctx = LATEST_CONTEXT or {}
    t = ctx.get("ticker", "?")

    if _client:
        # Rich prompt for conversation
        fibs = ctx.get("fibs", {})
        fib_str = ", ".join([f"{k}: ${v:.2f}" for k, v in fibs.items()]) if fibs else "None"
        poc = f"${ctx['poc']:.2f}" if ctx.get("poc") else "None"

        prompt = f"""
You are a friendly stock-analysis educator. Keep it simple and helpful.

Ticker: {t}
Price: ${ctx.get('price')}
Trend: {ctx.get('trend')}
RSI: {ctx.get('rsi')}
MACD: {ctx.get('macd')} vs Signal {ctx.get('macd_signal')}
POC (Most-traded price): {poc}
Fibonacci levels: {fibs and fib_str or 'None'}

User message: {message}

Rules:
- Explain terms briefly first (as if to a beginner), then relate them to this chart's numbers.
- You can discuss tradeoffs and what traders might *watch for*, but do NOT give personal financial advice.
- If asked for “how many shares to buy” or similar, explain position sizing concepts (risk per trade, ATR/stop), not directives.
- Be conversational and concise.
"""
        try:
            resp = _client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a friendly financial educator."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            pass  # fall through to offline mode

    # Offline fallback (no API key): still be helpful using context
    txt = [f"You're asking about **{t}**."]
    p = ctx.get("price")
    if p is not None: txt.append(f"- Latest price: **${p:.2f}**.")
    tr = ctx.get("trend")
    if tr: txt.append(f"- Trend: **{tr}** (20/50-day averages).")
    m, s = ctx.get("macd"), ctx.get("macd_signal")
    if (m is not None) and (s is not None):
        bias = "above" if m > s else "below"
        txt.append(f"- MACD line is **{bias}** its signal ({m:.2f} vs {s:.2f}).")
    r = ctx.get("rsi")
    if r is not None:
        zone = "hot/overbought" if r >= 70 else "cool/oversold" if r <= 30 else "normal"
        txt.append(f"- RSI: **{r:.1f}** ({zone}).")
    if ctx.get("poc") is not None:
        txt.append(f"- Most-traded price (POC): ~${ctx['poc']:.2f}.")
    f = ctx.get("fibs", {});
    imp = [k for k in ("38%", "50%", "62%", "61%") if k in f]
    if imp:
        txt.append("- Fibonacci zones: " + ", ".join([f"{k} ≈ ${f[k]:.2f}" for k in imp]))
    txt.append(
        "\nI'm running in offline mode (no model connected), so this is a quick summary. Add your OpenAI key to get conversational replies.")
    return "\n".join(txt)


def build_ui():
    with gr.Blocks(
            title="Agentic-Stonks",
            theme=gr.themes.Soft(primary_hue="orange", neutral_hue="gray"),
            css="""
            /* Theme adaptive colors */
            :root {
                --bg-light: #f9f9fb;
                --text-light: #000;
                --panel-light: #fff;
                --muted-light: #555;

                --bg-dark: #0b0c10;
                --text-dark: #eaeaea;
                --panel-dark: #13151a;
                --muted-dark: #a1a1a1;
            }
                .logo-box,.logo-box img {
                    max-width: 120px !important;
                    height: auto !important;
                    background: transparent !important;
            }


            @media (prefers-color-scheme: dark) {
                :root {
                    --bg: var(--bg-dark);
                    --text: var(--text-dark);
                    --panel: var(--panel-dark);
                    --muted: var(--muted-dark);
                }
            }

            @media (prefers-color-scheme: light) {
                :root {
                    --bg: var(--bg-light);
                    --text: var(--text-light);
                    --panel: var(--panel-light);
                    --muted: var(--muted-light);
                }
            }

            body, .gradio-container {
                background: var(--bg) !important;
                color: var(--text);
            }

            .header { font-size: 1.6rem; font-weight: 700; margin: 12px 0 4px; color: var(--text); }
            .subtext { font-size: .95rem; color: var(--muted); margin-bottom: 12px; }
            .insight { background: var(--panel); border: 1px solid #2223; border-radius: 12px; padding: 10px 12px; color: var(--text); }
            .insight > summary { cursor: pointer; font-weight: 700; margin-bottom: 8px; }
            .i-row { display:flex; justify-content:space-between; gap: 16px; padding: 6px 0; border-bottom: 1px dashed #2a2a2a44;}
            .i-row:last-child { border-bottom: none; }
            .i-foot { color: var(--muted); font-size: .9rem; margin-top: 8px; }
            .plotly-graph-div { height: 650px !important; }
            .chatbot { border-radius: 10px; border: 1px solid #2223; background: var(--panel); color: var(--text); }
            .footer { color: var(--muted); font-size: .85rem; text-align:center; margin: 14px 0 6px; }
        """
    ) as demo:

        with gr.Row():
            gr.Image(
                value="images/Agentic_Stonks.png",
                show_label=False,

                elem_id="logo",
                elem_classes=["logo-box"]
            )
            gr.HTML("<div class='header'>"
                    "<span>Agentic-Stonks — Explain, Advise, Interpret</span>"
                    "<div class='subtext'>Educational use only. Not financial advice.</div>"
                    "</div>")


        with gr.Row(equal_height=True):
            # Left column: controls, chart, insight card
            with gr.Column(scale=6):
                with gr.Row():
                    ticker_dd = gr.Dropdown(label="Choose stock",
                                            choices=["AAPL", "TSLA", "MSFT", "AMZN", "GOOG", "META", "NVDA", "NFLX",
                                                     "SPY", "QQQ", "KO", "AMD"],
                                            value=DEFAULT_TICKER, scale=2)
                    ticker_txt = gr.Textbox(label="Or type symbol", placeholder="e.g. AMD, BTC-USD", scale=2)
                    period = gr.Dropdown(label="Period",
                                         choices=["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"], value="1y",
                                         scale=1)
                    interval = gr.Dropdown(label="Interval",
                                           choices=["1d", "1h", "30m", "15m", "5m", "1m"], value="1d", scale=1)
                    run_btn = gr.Button("Analyze", variant="primary")

                chart = gr.Plot(label="Chart (Price + EMA/BB + Volume Profile • MACD • RSI • Volume)")
                insight = gr.HTML()

            # Right column: conversational AI
            with gr.Column(scale=4):
                gr.Markdown("### 💬 Ask the AI about the chart below:")
                gr.ChatInterface(
                    fn=chat_reply,
                    type="messages",
                    chatbot=gr.Chatbot(height=520, elem_classes=["chatbot"]),
                    examples=["What does MACD mean here?",
                              "Where is the strongest support?",
                              "Is RSI telling me it's overheated?"]
                )

        # Wiring
        run_btn.click(run_analysis, [ticker_dd, ticker_txt, period, interval], [chart, insight])
        ticker_dd.change(run_analysis, [ticker_dd, ticker_txt, period, interval], [chart, insight])
        ticker_txt.submit(run_analysis, [ticker_dd, ticker_txt, period, interval], [chart, insight])

        # Initial content
        fig, card = run_analysis(DEFAULT_TICKER, "", "1y", "1d")
        chart.value, insight.value = fig, card

        gr.HTML("<div class='footer'>© Agentic-Stonks · Educational only · Built with Gradio</div>")

    return demo


if __name__ == "__main__":
    ui = build_ui()
    ui.launch(server_name="127.0.0.1", server_port=7861)
