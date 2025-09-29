# app.py
# ------------------------------------------------------------
# Flask + Gradio project
# - Flask serves a simple JSON API at port 5000
# - Gradio runs on port 7860 with stock assistant UI
# ------------------------------------------------------------

from flask import Flask, jsonify
import threading
from gradio_ui import build_ui

# Create Flask app
app = Flask(__name__)


# Simple endpoint to confirm Flask is alive
@app.get("/")
def home():
    return jsonify({"message": "Flask is running. Visit the Gradio UI at http://127.0.0.1:7860/"})


# Function to launch Gradio in a background thread
def launch_gradio():
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7820)


# Main entry point
if __name__ == "__main__":
    # Start Gradio in its own thread
    threading.Thread(target=launch_gradio, daemon=True).start()

    # Start Flask server (http://127.0.0.1:5000/)
    app.run(host="127.0.0.1", port=5050, debug=True)


def _df_to_records(df):
    records = []
    for ts, row in df.iterrows():
        t = ts.isoformat()
        records.append({
            "time": t,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"])
        })
    return records

# --- Hourly endpoint ---
# Example: GET /api/hourly?symbol=AAPL&period=7d
@app.get("/api/hourly")
def api_hourly():
    symbol = request.args.get("symbol", type=str)
    period = request.args.get("period", default="7d", type=str)
    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    key = f"hourly:{symbol.upper()}:{period}"
    cached = _cache_get(key)
    if cached is not None:
        return jsonify({"symbol": symbol.upper(), "period": period, "data": cached})

    interval = "1m" if period in ("1d", "2d", "5d") else "5m"
    ticker = yf.Ticker(symbol)
    try:
        df = ticker.history(period=period, interval=interval, actions=False)
    except Exception as e:
        return jsonify({"error": "error fetching data", "detail": str(e)}), 502

    if df is None or df.empty:
        return jsonify({"error": "no data returned from provider"}), 502

    df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
    df.index = pd.DatetimeIndex(df.index)

    hourly = df.resample("60T", label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna(how="any")

    records = _df_to_records(hourly)
    _cache_set(key, records)
    return jsonify({"symbol": symbol.upper(), "period": period, "data": records})

# --- Weekly endpoint ---
# Example: GET /api/weekly?symbol=AAPL&period=1y
@app.get("/api/weekly")
def api_weekly():
    symbol = request.args.get("symbol", type=str)
    period = request.args.get("period", default="1y", type=str)
    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    key = f"weekly:{symbol.upper()}:{period}"
    cached = _cache_get(key)
    if cached is not None:
        return jsonify({"symbol": symbol.upper(), "period": period, "data": cached})

    ticker = yf.Ticker(symbol)
    try:
        df = ticker.history(period=period, interval="1d", actions=False)
    except Exception as e:
        return jsonify({"error": "error fetching data", "detail": str(e)}), 502

    if df is None or df.empty:
        return jsonify({"error": "no data returned from provider"}), 502

    df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
    df.index = pd.DatetimeIndex(df.index)

    weekly = df.resample("W").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna(how="any")

    records = _df_to_records(weekly)
    _cache_set(key, records)
    return jsonify({"symbol": symbol.upper(), "period": period, "data": records})


