#!/bin/bash
# One-shot setup, run, and clean exit for Agentic-Stonks

set -e  # exit immediately on error

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip quietly
python -m pip install --upgrade pip -q

# Check if requirements.txt is newer than installed packages
REQ_HASH_FILE=".venv/.requirements_hash"
NEW_HASH=$(md5sum requirements.txt | awk '{print $1}')

if [ ! -f "$REQ_HASH_FILE" ] || [ "$NEW_HASH" != "$(cat $REQ_HASH_FILE)" ]; then
    echo "Installing/updating requirements..."
    python -m pip install -r requirements.txt
    echo "$NEW_HASH" > "$REQ_HASH_FILE"
else
    echo "Requirements are up to date. Skipping reinstall."
fi

# Run the app
echo "Starting Flask + Gradio app..."
python app.py

# Deactivate venv when done
echo "Deactivating virtual environment..."
deactivate