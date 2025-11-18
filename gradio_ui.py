# ============================================================
# Gradio UI Layer for Agentic-Stonks
# ============================================================
# Responsibilities:
# - Defines the full Gradio user interface (charts + chat)
# - Routes user inputs into the analysis pipeline
# - Handles:
#       • Symbol resolution
#       • Timeframes + indicator toggles
#       • Data fetch + indicator computation
#       • Plot creation
#       • Insight summary card
#       • Integrated AI chat (OpenAI optional)
#
# The UI exposes:
#   - Chart visualization
#   - Insight card with trend/momentum/RSI/VWAP/etc.
#   - Conversational chat assistant referencing chart context
#
# ============================================================

from __future__ import annotations
import os
from typing import Dict, Any, List, Tuple

from dotenv import load_dotenv

load_dotenv()

import gradio as gr
from analysis import fetch_ohlcv, compute_indicators, make_figure, make_chat_snapshot

# ============================================================
# Constants & Lookup Tables
# ============================================================

# Timeframe presets → human-friendly names
TIMEFRAME_PRESETS = {
    "Hourly (1h)": "1h",
    "4 Hours (4h)": "4h",
    "Daily (1d)": "1d",
}

# VWAP computation modes
VWAP_MODES = {
    "Session (intraday reset)": "session",
    "Rolling Window": "rolling",
    "Anchored* (uses rolling fallback)": "anchored",
}

# Ticker alias mapping
NAME_TO_TICKER = {
    "APPLE": "AAPL", "AMAZON": "AMZN", "MICROSOFT": "MSFT", "META": "META",
    "ALPHABET": "GOOGL", "GOOGLE": "GOOGL", "TESLA": "TSLA", "NVIDIA": "NVDA"
}

# ============================================================
# Optional OpenAI Chat Client Setup
# ============================================================
# - Allows providing deeper indicator explanations
# - If no API key is set, uses fallback rule-based responses
# ============================================================

try:
    from openai import OpenAI

    if os.getenv("OPENAI_API_KEY"):
        _client = OpenAI()
        _OPENAI_OK = True
    else:
        _OPENAI_OK = False
        _client = None
except Exception:
    _OPENAI_OK = False
    _client = None


# System instruction given to OpenAI models
_SYSTEM_PROMPT = (
    "You are a helpful stock-analysis assistant embedded in a charting app. "
    "Provide conversational, insightful responses that explain technical indicators clearly. "
    "Use the provided context (symbol, timeframe, toggles, last values) to give specific, actionable insights. "
    "Be concise but thorough. Explain what the indicators suggest about the current market conditions. "
    "Educational use only - avoid giving direct buy/sell recommendations."
)

# ============================================================
# Context Formatting for Chat Model
# ============================================================
# Converts the analysis snapshot into a human-readable
# text block. Used as supplemental context for the LLM.
# ============================================================

def _context_to_text(ctx: Dict[str, Any]) -> str:
    if not isinstance(ctx, dict) or not ctx.get("ok"):
        return "Context: (no current chart loaded)"
    lines = [
        f"Current Analysis Context:",
        f"Symbol: {ctx.get('symbol')}",
        f"Timeframe: {ctx.get('timeframe')}",
        f"Active Indicators: "
        f"{'EMA200 ' if ctx.get('show_ema200') else ''}"
        f"{'ATR(14) ' if ctx.get('show_atr') else ''}"
        f"{'VWAP ' if ctx.get('show_vwap') else ''}"
        f"{'VTVR ' if ctx.get('show_vtvr') else ''}".strip(),
    ]

    # Add latest values
    values_section = []
    if ctx.get("last_close") is not None:
        values_section.append(f"Last Close: ${ctx['last_close']}")
    if ctx.get("last_ema200") is not None:
        values_section.append(f"EMA200: ${ctx['last_ema200']}")
    if ctx.get("last_atr14") is not None:
        values_section.append(f"ATR(14): {ctx['last_atr14']}")
    if ctx.get("last_vwap") is not None:
        values_section.append(f"VWAP: ${ctx['last_vwap']}")
    if ctx.get("last_rsi") is not None:
        values_section.append(f"RSI: {ctx['last_rsi']}")
    if ctx.get("last_macd") is not None and ctx.get("last_signal") is not None:
        values_section.append(f"MACD: {ctx['last_macd']}, Signal: {ctx['last_signal']}")
    if ctx.get("last_vtvr") is not None:
        vtvr_str = f"VTVR: {ctx['last_vtvr']}"
        if ctx.get("last_vtvr_z") is not None:
            vtvr_str += f" (z-score: {ctx['last_vtvr_z']})"
        values_section.append(vtvr_str)


    if values_section:
        lines.append("\nCurrent Values:")
        lines.extend(values_section)

    notes = ctx.get("notes", [])
    if notes:
        lines.append(f"\nKey Observations: {' '.join(notes)}")

    return "\n".join(lines)

# ============================================================
# Chat Function Logic for Gradio
# ============================================================
# chat_fn():
# - Handles both user messages and system responses
# - Supports OpenAI if available
# - Otherwise uses rule-based fallback analysis
# - Must return proper Gradio "messages" format
# ============================================================

def chat_fn(message: str, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Handle chat with proper dictionary format for Gradio Chatbot with type='messages'"""
    ctx_state = getattr(chat_fn, "analysis_context", None)
    ctx_val = ctx_state.value if isinstance(ctx_state, gr.State) else (ctx_state or {})
    ctx_text = _context_to_text(ctx_val)

    if _OPENAI_OK:
        try:
            messages = [{"role": "system", "content": _SYSTEM_PROMPT + "\n\n" + ctx_text}]

            # Convert history to OpenAI format
            for msg in history:
                if isinstance(msg, dict):
                    messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

            messages.append({"role": "user", "content": str(message)})

            resp = _client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.3,
                max_tokens=800,
            )
            response_text = resp.choices[0].message.content.strip()

        except Exception as e:
            response_text = f"I'm having trouble connecting to the AI service. Let me give you what I can see from the chart data.\n\n{_generate_fallback_response(ctx_val)}"
    else:
        response_text = _generate_fallback_response(ctx_val)

    # *** FIXED: Return proper message format ***
    new_history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": response_text}
    ]
    return new_history


# ============================================================
# Fallback Response Generation
# ============================================================
# Used when OpenAI is unavailable. Produces a structured,
# indicator-aware explanation of price, trend, RSI, MACD,
# VWAP, ATR, and overall chart conditions.
# ============================================================

def _generate_fallback_response(ctx_val: Dict[str, Any]) -> str:
    """Generate intelligent fallback response when OpenAI is unavailable"""
    if not isinstance(ctx_val, dict) or not ctx_val.get("ok"):
        return "I don't have chart data loaded yet. Click **Analyze** first, and I'll be able to help you understand the indicators and trends."

    symbol = ctx_val.get('symbol', 'the stock')
    tf = ctx_val.get('timeframe', 'this timeframe')

    response = f"Looking at **{symbol}** on the **{tf}** chart:\n\n"

    # Price and trend analysis
    if ctx_val.get("last_close") is not None:
        response += f"**Current Price**: ${ctx_val['last_close']}\n"

        if ctx_val.get("show_ema200") and ctx_val.get("last_ema200") is not None:
            if ctx_val["last_close"] > ctx_val["last_ema200"]:
                diff_pct = ((ctx_val["last_close"] - ctx_val["last_ema200"]) / ctx_val["last_ema200"] * 100)
                response += f"The price is **{diff_pct:.1f}% above** the 200-period EMA (${ctx_val['last_ema200']}), suggesting a bullish long-term trend.\n"
            else:
                diff_pct = ((ctx_val["last_ema200"] - ctx_val["last_close"]) / ctx_val["last_ema200"] * 100)
                response += f"The price is **{diff_pct:.1f}% below** the 200-period EMA (${ctx_val['last_ema200']}), indicating a bearish long-term trend.\n"

    response += "\n"

    # Momentum analysis
    if ctx_val.get("last_macd") is not None and ctx_val.get("last_signal") is not None:
        if ctx_val["last_macd"] > ctx_val["last_signal"]:
            response += f"**MACD** ({ctx_val['last_macd']:.2f}) is above the signal line ({ctx_val['last_signal']:.2f}), showing **bullish momentum**.\n"
        else:
            response += f"**MACD** ({ctx_val['last_macd']:.2f}) is below the signal line ({ctx_val['last_signal']:.2f}), showing **bearish momentum**.\n"

    # RSI analysis
    if ctx_val.get("last_rsi") is not None:
        rsi = ctx_val["last_rsi"]
        if rsi >= 70:
            response += f"**RSI** is at {rsi:.1f}, in **overbought territory**. This could signal a potential pullback or consolidation.\n"
        elif rsi <= 30:
            response += f"**RSI** is at {rsi:.1f}, in **oversold territory**. This could signal a potential bounce or reversal.\n"
        else:
            response += f"**RSI** is at {rsi:.1f}, in neutral territory with room to move in either direction.\n"

    response += "\n"

    # Volume and volatility
    if ctx_val.get("show_vwap") and ctx_val.get("last_vwap") is not None:
        if ctx_val["last_close"] > ctx_val["last_vwap"]:
            response += f"Price is trading **above VWAP** (${ctx_val['last_vwap']}), suggesting buyers are in control.\n"
        else:
            response += f"Price is trading **below VWAP** (${ctx_val['last_vwap']}), suggesting sellers have the edge.\n"

    if ctx_val.get("show_atr") and ctx_val.get("last_atr14") is not None:
        response += f"**ATR(14)** is {ctx_val['last_atr14']:.2f}, indicating current volatility levels.\n"

    # Notes from analysis
    notes = ctx_val.get("notes", [])
    if notes:
        response += f"\n**Key takeaways**: {' '.join(notes)}\n"

    response += "\n*Remember: This is educational analysis only, not financial advice.*"

    return response

# ============================================================
# analyze_handler()
# ============================================================
# CENTRAL DATA PIPELINE
# ---------------------
# Steps:
#   1. Resolve symbol input (typed or dropdown)
#   2. Fetch OHLCV data
#   3. Compute EMA/VWAP/ATR/VTVR/MACD/RSI
#   4. Build Plotly chart
#   5. Build analysis context state
#   6. Build Insight Card (Trend, Momentum, RSI, ATR, VWAP, VTVR)
#
# Returns (for Gradio):
#   - figure
#   - context dict
#   - insight dict
# ============================================================

def analyze_handler(chosen_sym: str, typed_sym: str,
                    tf_key: str,
                    show_ema200: bool, show_atr: bool, show_vwap: bool, show_vtvr: bool,
                    vwap_mode_key: str, vwap_n_val: float, vtvr_use_tr_val: bool, vtvr_z_on_val: bool,
                    ctx: Dict[str, Any]):
    raw = (typed_sym or "").strip() or (chosen_sym or "").strip()
    resolved = NAME_TO_TICKER.get(raw.upper(), raw.upper())

    tf = TIMEFRAME_PRESETS[tf_key]
    vwap_mode_val = VWAP_MODES[vwap_mode_key]
    vwap_n_int = int(vwap_n_val) if vwap_n_val is not None else 20

    df, _, _ = fetch_ohlcv(resolved, tf)
    if df.empty:
        import plotly.graph_objects as go
        f = go.Figure()
        f.update_layout(title=f"No data for '{raw}' (resolved: {resolved}) / {tf}", height=420)
        ctx = {"symbol": resolved, "timeframe": tf, "ok": False}
        insight = {
            "Trend": "—", "Momentum": "—", "RSI": "—", "ATR": "—", "VWAP": "—", "VTVR": "—", "Notes": "No data."
        }
        return f, ctx, insight

    dfi = compute_indicators(
        df,
        want_ema200=bool(show_ema200),
        want_atr=bool(show_atr),
        vwap_mode=vwap_mode_val,
        vwap_n=vwap_n_int,
        want_vtvr=bool(show_vtvr),
        vtvr_use_tr=bool(vtvr_use_tr_val),
        vtvr_z_on=bool(vtvr_z_on_val),
        vtvr_z_window=60,
        ensure_macd_rsi=True,
    )

    fig = make_figure(
        dfi,
        show_ema200=bool(show_ema200),
        show_atr=bool(show_atr),
        show_vwap=bool(show_vwap),
        show_vtvr=bool(show_vtvr),
        show_vtvr_z=bool(vtvr_z_on_val and show_vtvr),
    )

    snap = make_chat_snapshot(dfi)
    ctx = {
        "symbol": resolved,
        "timeframe": tf,
        "show_ema200": bool(show_ema200),
        "show_atr": bool(show_atr),
        "show_vwap": bool(show_vwap),
        "show_vtvr": bool(show_vtvr),
        "vwap_mode": vwap_mode_val,
        "vwap_n": vwap_n_int,
        "vtvr_use_tr": bool(vtvr_use_tr_val),
        "vtvr_z_on": bool(vtvr_z_on_val),
        **snap,
        "ok": True,
    }

    trend = "Up" if (snap.get("last_close") and snap.get("last_ema200") and snap["last_close"] > snap["last_ema200"]) \
        else ("Down" if (snap.get("last_close") and snap.get("last_ema200")) else "—")
    momentum = "Bullish" if (
                snap.get("last_macd") is not None and snap.get("last_signal") is not None and snap["last_macd"] > snap[
            "last_signal"]) \
        else ("Bearish" if (snap.get("last_macd") is not None and snap.get("last_signal") is not None) else "—")
    rsi_txt = f'{snap["last_rsi"]}' if snap.get("last_rsi") is not None else "—"
    atr_txt = f'{snap["last_atr14"]}' if snap.get("last_atr14") is not None else "—"
    vwap_txt = f'{snap["last_vwap"]}' if snap.get("last_vwap") is not None else "—"
    vtvr_txt = f'{snap["last_vtvr"]}' if snap.get("last_vtvr") is not None else "—"
    notes = " ".join(snap.get("notes", [])) or "—"

    insight = {
        "Trend": trend,
        "Momentum": momentum,
        "RSI": rsi_txt,
        "ATR": atr_txt,
        "VWAP": vwap_txt,
        "VTVR": vtvr_txt,
        "Notes": notes
    }

    return fig, ctx, insight

# ============================================================
# build_ui()
# ============================================================
# The MAIN UI definition.
#
# Creates:
#   - Header + logo
#   - Symbol input + timeframe selector
#   - Indicator toggle panel
#   - Chart display (Plotly)
#   - Insight Card
#   - AI Chat Section
#   - Settings accordions
#
# Returns:
#   A fully configured Gradio Blocks() app.
# ============================================================

def build_ui():
    # Blue theme
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="blue",
    )

    css = """
    .gradio-container {max-width: 1400px; margin: 0 auto;}
    .header-bar {
        display: flex; 
        align-items: center; 
        gap: 0.75rem; 
        background: linear-gradient(to right, #ffffff, #fafafa);
        border: 1px solid #e5e7eb;
        border-radius: 16px; 
        padding: 14px 20px; 
        box-shadow: 0 2px 8px rgba(0,0,0,.06);
        margin-bottom: 1.5rem;
    }
    .app-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        box-shadow: 0 2px 4px rgba(59,130,246,0.3);
    }
    .header-title {
        font-weight: 600;
        font-size: 1.1rem;
        color: #1a1a1a;
    }
    .header-subtitle {
        opacity: 0.7;
        font-weight: 400;
    }
    .badge {
        font-size: 0.75rem; 
        padding: 4px 12px; 
        border-radius: 999px; 
        background: #dbeafe;
        border: 1px solid #3b82f6; 
        color: #1e40af;
        font-weight: 500;
    }
    .insight-card {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        border: 1px solid #bae6fd;
        border-radius: 12px;
        padding: 16px;
        margin-top: 1rem;
    }
    .insight-card h3 {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 12px;
        color: #0c4a6e;
    }
    .chat-container {
        border: 1px solid #e5e7eb !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }
    input[type="checkbox"]:checked {
        background-color: #3b82f6 !important;
        border-color: #3b82f6 !important;
    }
    .primary {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        border: none !important;
    }
    .primary:hover {
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    }
     .logo-box,.logo-box img {
                    max-width: 120px !important;
                    height: auto !important;
                    background: transparent !important;
            }

    """

    with gr.Blocks(title="Agentic-Stonks", theme=theme, css=css) as demo:
        # Header with blue accent
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

        analysis_context = gr.State(value={"ok": False})
        chat_fn.analysis_context = analysis_context

        with gr.Row(equal_height=False):
            with gr.Column(scale=7):
                with gr.Row():
                    choose_symbol = gr.Dropdown(
                        label="Choose stock / symbol",
                        choices=["AAPL", "AMZN", "MSFT", "META", "NVDA", "TSLA", "GOOGL"],
                        value="META",
                    )
                    symbol_text = gr.Textbox(label="Or type symbol", placeholder="e.g., AAPL")
                    timeframe = gr.Dropdown(
                        choices=list(TIMEFRAME_PRESETS.keys()),
                        value="Daily (1d)",
                        label="Timeframe",
                    )
                    analyze_btn = gr.Button("Analyze", variant="primary")

                with gr.Row():
                    cb_ema200 = gr.Checkbox(True, label="EMA200")
                    cb_atr = gr.Checkbox(True, label="ATR(14)")
                    cb_vwap = gr.Checkbox(True, label="VWAP")
                    cb_vtvr = gr.Checkbox(True, label="VTVR")

                with gr.Accordion("⚙️ Settings", open=False):
                    with gr.Row():
                        vwap_mode = gr.Dropdown(choices=list(VWAP_MODES.keys()), value="Session (intraday reset)",
                                                label="VWAP mode")
                        vwap_n = gr.Slider(5, 120, value=20, step=1, label="VWAP window (rolling)")
                    with gr.Row():
                        vtvr_use_tr = gr.Checkbox(False, label="VTVR: use TrueRange instead of ATR(14)")
                        vtvr_z_on = gr.Checkbox(True, label="VTVR z-score overlay")

                fig_out = gr.Plot(label="Chart")

                # Insight Card with blue theme
                with gr.Group(elem_classes=["insight-card"]):
                    gr.HTML("<h3>📊 Insight Card</h3>")
                    with gr.Row():
                        insight_trend = gr.Textbox(value="—", label="Trend", interactive=False, scale=1)
                        insight_momo = gr.Textbox(value="—", label="Momentum", interactive=False, scale=1)
                        insight_rsi = gr.Textbox(value="—", label="RSI", interactive=False, scale=1)
                    with gr.Row():
                        insight_atr = gr.Textbox(value="—", label="ATR", interactive=False, scale=1)
                        insight_vwap = gr.Textbox(value="—", label="VWAP", interactive=False, scale=1)
                        insight_vtvr = gr.Textbox(value="—", label="VTVR", interactive=False, scale=1)
                    insight_notes = gr.Textbox(value="—", label="Notes", interactive=False, lines=2)

            with gr.Column(scale=5):
                gr.Markdown("### 💬 Ask the AI about the chart")
                gr.Markdown("*Get insights on trends, indicators, and market conditions*")

                # *** FIXED: Proper chatbot with messages type ***
                chatbot = gr.Chatbot(
                    value=[],
                    height=450,
                    elem_classes=["chat-container"],
                    show_label=False,
                    type="messages"
                )

                # Combined input area
                with gr.Row():
                    chat_input = gr.Textbox(
                        placeholder="Ask about RSI, MACD, trend direction, support levels...",
                        show_label=False,
                        scale=9,
                        lines=1,
                        container=False
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1, size="sm")

                with gr.Row():
                    clear_btn = gr.ClearButton([chatbot], value="Clear Chat", size="sm")
                    gr.Markdown("*Powered by market data analysis*", elem_classes=["text-xs"])

                # *** FIXED: Proper message handling ***
                def submit_message(msg, history):
                    if not msg.strip():
                        return "", history
                    return "", chat_fn(msg, history)

                send_btn.click(
                    fn=submit_message,
                    inputs=[chat_input, chatbot],
                    outputs=[chat_input, chatbot],
                )

                chat_input.submit(
                    fn=submit_message,
                    inputs=[chat_input, chatbot],
                    outputs=[chat_input, chatbot],
                )

        # Insight state management
        insight_state = gr.State({})

        def _insight_to_outputs(d: Dict[str, str]):
            d = d or {}
            return (
                d.get("Trend", "—"),
                d.get("Momentum", "—"),
                d.get("RSI", "—"),
                d.get("ATR", "—"),
                d.get("VWAP", "—"),
                d.get("VTVR", "—"),
                d.get("Notes", "—"),
            )

        analyze_btn.click(
            analyze_handler,
            inputs=[choose_symbol, symbol_text,
                    timeframe,
                    cb_ema200, cb_atr, cb_vwap, cb_vtvr,
                    vwap_mode, vwap_n, vtvr_use_tr, vtvr_z_on,
                    analysis_context],
            outputs=[fig_out, analysis_context, insight_state],
        ).then(
            fn=_insight_to_outputs,
            inputs=insight_state,
            outputs=[insight_trend, insight_momo, insight_rsi, insight_atr, insight_vwap, insight_vtvr, insight_notes]
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch()