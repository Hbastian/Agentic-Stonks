# Windows setup + run script for Agentic-Stonks
# Ensures Python 3.12+, venv exists, and dependencies are current.

$ErrorActionPreference = "Stop"

# --- Step 1: Ensure Python 3.12+ is installed ---
$python = Get-Command python3.12 -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "⚠️ Python 3.12 not found on your system."
    $choice = Read-Host "Would you like to install Python 3.12 via winget? (y/n)"
    if ($choice -eq "y" -or $choice -eq "Y") {
        Write-Host "📦 Installing Python 3.12..."
        winget install -e --id Python.Python.3.12
    } else {
        Write-Host "❌ Python 3.12 is required. Install it manually first."
        exit 1
    }
}

$PYTHON = "python3.12"
$VERSION = & $PYTHON -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
$parts = $VERSION.Split(".")
if ([int]$parts[0] -lt 3 -or [int]$parts[1] -lt 12) {
    Write-Host "❌ Detected Python $VERSION"
    Write-Host "⚠️ Agentic-Stonks requires Python 3.12 or newer."
    exit 1
}

Write-Host "✅ Using Python $VERSION"

# --- Step 2: Create venv if missing ---
if (-Not (Test-Path ".venv")) {
    Write-Host "📦 Creating virtual environment..."
    & $PYTHON -m venv .venv
}

# --- Step 3: Activate venv ---
Write-Host "🔗 Activating virtual environment..."
. .\.venv\Scripts\Activate.ps1

$VENV_PYTHON = ".\.venv\Scripts\python.exe"

# --- Step 4: Upgrade pip/setuptools/wheel ---
Write-Host "⬆️ Upgrading pip, setuptools, wheel..."
& $VENV_PYTHON -m pip install --upgrade pip setuptools wheel -q

# --- Step 5: Install/upgrade requirements ---
Write-Host "📥 Installing project requirements..."
& $VENV_PYTHON -m pip install --upgrade -r requirements.txt -q

# --- Step 6: Sanity check pandas ---
try {
    & $VENV_PYTHON -c "import pandas"
} catch {
    Write-Host "⚠️ Pandas seems broken. Reinstalling cleanly..."
    & $VENV_PYTHON -m pip install --force-reinstall --no-cache-dir pandas -q
}

# --- Step 7: Load environment variables ---
if (Test-Path ".env") {
    Write-Host "🌱 Loading .env variables..."
    Get-Content .env | ForEach-Object {
        if ($_ -match "^\s*#") { return }
        $var = $_.Split("=",2)
        if ($var.Length -eq 2) {
            [System.Environment]::SetEnvironmentVariable($var[0], $var[1])
        }
    }
}

# --- Step 8: Run the app ---
Write-Host "🚀 Starting Flask + Gradio app..."
& $VENV_PYTHON app.py

# --- Step 9: Cleanup ---
Write-Host "🛑 Deactivating virtual environment..."
deactivate
