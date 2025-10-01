#!/bin/bash
# macOS setup + run script for Agentic-Stonks
# Ensures Python 3.12+ (via Homebrew), venv exists, and dependencies are current.

set -e  # exit on error

# --- Step 1: Ensure Homebrew is installed ---
if ! command -v brew >/dev/null 2>&1; then
    echo "❌ Homebrew not found."
    echo "👉 Install Homebrew first: https://brew.sh/"
    exit 1
fi

# --- Step 2: Ensure Python 3.12+ is installed ---
if ! command -v python3.12 >/dev/null 2>&1; then
    echo "⚠️ Python 3.12 not found on your system."
    read -p "Would you like to install Python 3.12 with Homebrew? (y/n): " choice
    case "$choice" in
        y|Y )
            echo "📦 Installing Python 3.12..."
            brew install python@3.12
            brew link --overwrite python@3.12
            ;;
        n|N )
            echo "❌ Python 3.12 is required. Please install it manually with:"
            echo "   brew install python@3.12"
            exit 1
            ;;
        * )
            echo "❌ Invalid input. Please run the script again and enter 'y' or 'n'."
            exit 1
            ;;
    esac
fi

PYTHON=python3.12
VERSION=$($PYTHON -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
MAJOR=$(echo $VERSION | cut -d. -f1)
MINOR=$(echo $VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || [ "$MINOR" -lt 12 ]; then
    echo "❌ Detected Python $VERSION"
    echo "⚠️ Agentic-Stonks requires Python 3.12 or newer."
    echo "👉 Please upgrade with: brew install python@3.12"
    exit 1
fi

echo "✅ Using Python $VERSION"

# --- Step 3: Create venv if missing ---
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON -m venv .venv
fi

# --- Step 4: Activate venv ---
echo "🔗 Activating virtual environment..."
source .venv/bin/activate

# Always use venv Python explicitly
VENV_PYTHON=$(pwd)/.venv/bin/python

# --- Step 5: Upgrade pip/setuptools/wheel ---
echo "⬆️ Upgrading pip, setuptools, wheel..."
$VENV_PYTHON -m pip install --upgrade pip setuptools wheel -q

# --- Step 6: Install/upgrade requirements ---
echo "📥 Installing project requirements..."
$VENV_PYTHON -m pip install --upgrade -r requirements.txt -q

# --- Step 7: Sanity check pandas ---
$VENV_PYTHON -c "import pandas" 2>/dev/null || {
    echo "⚠️ Pandas seems broken. Reinstalling cleanly..."
    $VENV_PYTHON -m pip install --force-reinstall --no-cache-dir pandas
}

# --- Step 8: Load environment variables ---
if [ -f ".env" ]; then
    echo "🌱 Loading .env variables..."
    export $(grep -v '^#' .env | xargs)
fi

# --- Step 9: Run the app ---
echo "🚀 Starting Flask + Gradio app..."
$VENV_PYTHON app.py

# --- Step 10: Cleanup ---
echo "🛑 Deactivating virtual environment..."
deactivate
