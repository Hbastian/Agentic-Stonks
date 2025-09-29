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
    demo.launch(server_name="127.0.0.1", server_port=7861)

# Main entry point
if __name__ == "__main__":
    # Start Gradio in its own thread
    threading.Thread(target=launch_gradio, daemon=True).start()

    # Start Flask server (http://127.0.0.1:5000/)
    app.run(host="127.0.0.1", port=5000, debug=True)
