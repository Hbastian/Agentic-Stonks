from flask import Flask, jsonify
import threading
import os
import atexit
from gradio_ui import build_ui

# ------------------------------------------------------------
# Flask + Gradio dual-server project
# ------------------------------------------------------------
# Architecture Overview:
# - Flask (port 5000) exposes a tiny JSON API showing status
# - Gradio runs a UI on its own port (default 7861 or auto)
# - Gradio launches in a background daemon thread so Flask
#   remains responsive and both servers run simultaneously
# - On shutdown, Gradio is cleanly closed with atexit hooks
# ------------------------------------------------------------


# ------------------------------------------------------------
# Flask App Creation
# ------------------------------------------------------------
# Central Flask instance that serves:
#   GET /
#     → Returns JSON with status + Gradio URL (if running)
# ------------------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------------------
# Global State
# ------------------------------------------------------------
# gradio_port: stores whichever port Gradio ends up using
#   - first tries GRADIO_SERVER_PORT env var
#   - fallback: 7861
#   - last fallback: auto-selected open port
#
# gradio_demo: reference to launched demo instance
#   - needed to shut down Gradio cleanly via .close()
# ------------------------------------------------------------
gradio_port = {"port": None}
gradio_demo = None


# ------------------------------------------------------------
# home()
# ------------------------------------------------------------
# Flask root endpoint.
#
# Used as a simple health check to:
#   - confirm Flask is alive
#   - return the active Gradio URL if launched
#
# Returns JSON only. No HTML.
# ------------------------------------------------------------
@app.get("/")
def home():
    if gradio_port["port"]:
        return jsonify({
            "message": "Flask is running",
            "gradio_url": f"http://127.0.0.1:{gradio_port['port']}/"
        })
    else:
        return jsonify({"message": "Flask is running. Gradio not started yet."})


# ------------------------------------------------------------
# launch_gradio()
# ------------------------------------------------------------
# Handles starting the Gradio interface in its own thread.
#
# Behavior:
# 1. Builds UI using build_ui()
# 2. Tries to bind to:
#       - $GRADIO_SERVER_PORT   (explicit env override)
#       - 7861                  (default)
#       - None                  (auto-pick a free port)
# 3. Stores final port in gradio_port for use by Flask API
#
# prevent_thread_lock=True:
#   - Allows Gradio to run without blocking the thread.
# ------------------------------------------------------------
def launch_gradio():
    global gradio_demo
    demo = build_ui()

    # Try environment override first, then default 7861
    port = int(os.getenv("GRADIO_SERVER_PORT", 7861))

    try:
        demo.launch(server_name="127.0.0.1", server_port=port, prevent_thread_lock=True)
        gradio_port["port"] = port
    except OSError:
        # Port in use → let Gradio choose a free one
        demo.launch(server_name="127.0.0.1", server_port=None, prevent_thread_lock=True)
        gradio_port["port"] = demo.server_port  # store auto-assigned port

    gradio_demo = demo


# ------------------------------------------------------------
# cleanup()
# ------------------------------------------------------------
# Called automatically at Python interpreter exit (atexit).
#
# Purpose:
#   - Ensure Gradio server shuts down cleanly
#   - Release occupied ports
#   - Avoid lingering background processes
#
# Only runs if Gradio was actually launched.
# ------------------------------------------------------------
def cleanup():
    global gradio_demo
    if gradio_demo is not None:
        print("Shutting down Gradio server...")
        gradio_demo.close()


# Register cleanup() so it's always executed on exit
atexit.register(cleanup)


# ------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------
# Execution flow:
#
# 1. Start Gradio inside a daemon thread
#       - Non-blocking
#       - Automatically closes when main process exits
#
# 2. Start Flask on 127.0.0.1:5000
#       - debug=True: useful for development
#       - use_reloader=False: avoids double-thread startup
# ------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=launch_gradio, daemon=True).start()

    # Flask root API lives at:
    #   http://127.0.0.1:5000/
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
