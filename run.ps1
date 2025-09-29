# run.ps1
# One-shot setup, run, and clean exit for Agentic-Stonks (Windows PowerShell)

$ErrorActionPreference = "Stop"

# Path to venv
$venvPath = ".venv"

# Create venv if it doesn't exist
if (-Not (Test-Path $venvPath)) {
    Write-Output "Creating virtual environment..."
    python -m venv $venvPath
}

# Activate venv
Write-Output "Activating virtual environment..."
& "$venvPath\Scripts\Activate.ps1"

# Upgrade pip quietly
python -m pip install --upgrade pip -q

# Hash requirements.txt to detect changes
$reqHashFile = "$venvPath\.requirements_hash"
$newHash = (Get-FileHash requirements.txt -Algorithm MD5).Hash

if (-Not (Test-Path $reqHashFile) -or (Get-Content $reqHashFile) -ne $newHash) {
    Write-Output "Installing/updating requirements..."
    python -m pip install -r requirements.txt
    $newHash | Out-File $reqHashFile -Encoding ASCII
} else {
    Write-Output "Requirements are up to date. Skipping reinstall."
}

# Load .env if present
if (Test-Path ".env") {
    Write-Output "Loading environment variables from .env..."
    Get-Content .env | ForEach-Object {
        if ($_ -match "^\s*#") { return } # skip comments
        if ($_ -match "^\s*$") { return } # skip empty lines
        $parts = $_ -split '=', 2
        if ($parts.Count -eq 2) {
            $key = $parts[0].Trim()
            $val = $parts[1].Trim()
            $env:$key = $val
        }
    }
}

# Run the app
Write-Output "Starting Flask + Gradio app..."
python app.py

# Deactivate venv
Write-Output "Deactivating virtual environment..."
deactivate