#!/bin/bash

# Cek command python yang tersedia (python3 atau python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Python is not installed. Please install Python 3.9+ first."
    exit 1
fi

# Buat virtual environment jika belum ada
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Aktivasi venv (Gunakan bin/activate untuk Linux/Mac, bukan Scripts/)
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependensi
echo "Installing dependencies..."
pip install -r requirements.txt

# Jalankan server
echo "Starting server..."
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
