# Buat virtual environment jika belum ada
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
}

# Aktivasi venv
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1

# Install dependensi
Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt

# Jalankan server
Write-Host "Starting server..." -ForegroundColor Green
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
