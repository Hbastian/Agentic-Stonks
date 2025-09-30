# app.py
# ------------------------------------------------------------
# Flask + Gradio project
# - Flask serves a simple JSON API at port 5000
# - Gradio runs on a free port (default 7861, fallback auto-pick)
# ------------------------------------------------------------

from flask import Flask, jsonify
import threading
import os
import atexit
from gradio_ui import build_ui

# Create Flask app
app = Flask(__name__)

# Store chosen Gradio port + demo ref
gradio_port = {"port": None}
gradio_demo = None


# Simple endpoint to confirm Flask is alive
@app.get("/")
def home():
    if gradio_port["port"]:
        return jsonify({
            "message": "Flask is running",
            "gradio_url": f"http://127.0.0.1:{gradio_port['port']}/"
        })
    else:
        return jsonify({"message": "Flask is running. Gradio not started yet."})


# Function to launch Gradio in a background thread
def launch_gradio():
    global gradio_demo
    demo = build_ui()

    # Try GRADIO_SERVER_PORT or 7861, else auto-pick
    port = int(os.getenv("GRADIO_SERVER_PORT", 7861))
    try:
        demo.launch(server_name="127.0.0.1", server_port=port, prevent_thread_lock=True)
        gradio_port["port"] = port
    except OSError:
        demo.launch(server_name="127.0.0.1", server_port=None, prevent_thread_lock=True)
        gradio_port["port"] = demo.server_port  # capture auto-picked port

    gradio_demo = demo

# Ensure Gradio shuts down and releases port on exit
def cleanup():
    global gradio_demo
    if gradio_demo is not None:
        print("Shutting down Gradio server...")
        gradio_demo.close()


atexit.register(cleanup)


# Main entry point
if __name__ == "__main__":
    # Start Gradio in its own thread
    threading.Thread(target=launch_gradio, daemon=True).start()

    # Start Flask server (http://127.0.0.1:5000/)
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
