# One-shot setup, run, and clean exit for Agentic-Stonks (Windows)

# Exit immediately if a command fails
$ErrorActionPreference = "Stop"

# Check if .venv folder exists, if not create it
if (-Not (Test-Path ".venv")) {
    Write-Output "Creating virtual environment..."
    python -m venv .venv
}

# Activate the virtual environment
Write-Output "Activating virtual environment..."
# This loads the activation script for PowerShell
. .\.venv\Scripts\Activate.ps1

# Upgrade pip quietly
Write-Output "Upgrading pip..."
python -m pip install --upgrade pip | Out-Null

# Compute hash of requirements.txt
$reqFile = "requirements.txt"
$hashFile = ".venv\.requirements_hash"

if (Test-Path $reqFile) {
    $newHash = Get-FileHash $reqFile -Algorithm MD5 | Select-Object -ExpandProperty Hash

    if (-Not (Test-Path $hashFile) -or (Get-Content $hashFile) -ne $newHash) {
        Write-Output "Installing/updating requirements..."
        python -m pip install -r requirements.txt
        $newHash | Out-File $hashFile -Encoding ascii
    }
    else {
        Write-Output "Requirements are up to date. Skipping reinstall."
    }
}

# Run the app
Write-Output "Starting Flask + Gradio app..."
python app.py

# Deactivate venv when done
Write-Output "Deactivating virtual environment..."
deactivate

