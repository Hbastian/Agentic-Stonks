# run.ps1
# Windows setup + run script for Agentic-Stonks
# Ensures Python 3.12+, venv exists, and dependencies are current.

$ErrorActionPreference = "Stop"

Write-Host "=== Agentic-Stonks Setup (Windows PowerShell) ===`n"

# --- Step 1: Check for Python 3.12 ---
$pythonCmd = Get-Command python3.12 -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
}

if (-not $pythonCmd) {
    Write-Host "⚠️ Python 3.12 not found."
    $choice = Read-Host "Would you like to install Python 3.12 via winget? (y/n)"
    if ($choice -match '^[Yy]$') {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "📦 Installing Python 3.12..."
            winget install -e --id Python.Python.3.12 -h --accept-package-agreements --accept-source-agreements
            $pythonCmd = Get-Command python3.12 -ErrorAction SilentlyContinue
            if (-not $pythonCmd) {
                Write-Host "❌ Python 3.12 installation failed. Please install manually: https://www.python.org/downloads/"
                exit 1
            }
        } else {
            Write-Host "❌ winget not found. Please install Python 3.12 manually: https://www.python.org/downloads/"
            exit 1
        }
    } else {
        Write-Host "❌ Python 3.12 is required. Please install manually from https://www.python.org/downloads/"
        exit 1
    }
}

$PYTHON = $pythonCmd.Source
$VERSION = & $PYTHON -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
$MAJOR,$MINOR,$PATCH = $VERSION.Split(".")

if ([int]$MAJOR -lt 3 -or [int]$MINOR -lt 12) {
    Write-Host "❌ Detected Python $VERSION"
    Write-Host "⚠️ Agentic-Stonks requires Python 3.12 or newer."
    Write-Host "👉 Please upgrade from https://www.python.org/downloads/"
    exit 1
}

Write-Host "✅ Using Python $VERSION"

# --- Step 2: Create venv if missing ---
if (-not (Test-Path ".venv")) {
    Write-Host "📦 Creating virtual environment..."
    & $PYTHON -m venv .venv | Out-Null
}

# --- Step 3: Activate venv ---
Write-Host "🔗 Activating virtual environment..."
. .\.venv\Scripts\Activate.ps1

# --- Step 4: Upgrade pip/setuptools/wheel ---
Write-Host "⬆️ Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip setuptools wheel -q

# --- Step 5: Install/upgrade requirements ---
Write-Host "📥 Installing project requirements..."
python -m pip install --upgrade -r requirements.txt -q

# --- Step 6: Sanity check pandas ---
try {
    python -c "import pandas" | Out-Null
} catch {
    Write-Host "⚠️ Pandas seems broken. Reinstalling cleanly..."
    python -m pip install --force-reinstall --no-cache-dir pandas -q
}

# --- Step 7: Load environment variables ---
if (Test-Path ".env") {
    Write-Host "🌱 Loading .env variables..."
    Get-Content .env | ForEach-Object {
        if ($_ -match "^\s*#") { return } # skip comments
        $parts = $_.Split("=",2)
        if ($parts.Length -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1])
        }
    }
}

# --- Step 8: Run the app ---
Write-Host "🚀 Starting Flask + Gradio app..."
python app.py

# --- Step 9: Cleanup ---
Write-Host "🛑 Deactivating virtual environment..."
deactivate
