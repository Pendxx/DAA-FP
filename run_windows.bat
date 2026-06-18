@echo off
title Logistics Dispatch Simulator
echo ============================================================
echo   LOGISTICS DISPATCH SIMULATOR - WINDOWS AUTO LAUNCHER
echo ============================================================

:: Pindah ke direktori tempat file .bat ini berada
cd /d "%~dp0"

echo [1/4] Menyiapkan Virtual Environment...
if not exist "venv\Scripts\activate.bat" (
    echo   Membuat virtual environment baru...
    py -m venv venv
)

echo [2/4] Mengaktifkan Virtual Environment...
call venv\Scripts\activate.bat

echo [3/4] Memeriksa dan Menginstal Library...
pip install -r requirements.txt > nul 2>&1
if %errorlevel% neq 0 (
    echo   [INFO] Menginstal library untuk pertama kalinya...
    pip install -r requirements.txt
) else (
    echo   [INFO] Library sudah terinstal.
)

echo [4/4] Memeriksa Peta Offline...
if not exist "data_tools\jawa_optimized.osm" (
    if not exist "graph_cache\jawa_optimized_graph.pkl.xz" (
        if not exist "graph_cache\jawa_optimized_graph.pkl" (
            echo   [INFO] Peta offline belum ditemukan. Memulai proses download dan build peta.
            python data_tools\build_offline_map.py
        )
    )
)

echo ============================================================
echo   SERVER SEDANG DINYALAKAN...
echo   Membuka browser ke http://127.0.0.1:8001
echo   (Mohon jangan tutup jendela hitam ini selama aplikasi dipakai)
echo ============================================================

:: Tunggu 2 detik, lalu buka browser otomatis
timeout /t 2 /nobreak > nul
start http://127.0.0.1:8001

:: Jalankan server uvicorn
python -m uvicorn main:app --reload --port 8001

pause
