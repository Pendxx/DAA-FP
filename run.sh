#!/bin/bash

echo "  LOGISTICS DISPATCH SIMULATOR - AUTOMATED LAUNCHER"

# Detect OS
OS_TYPE="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="mac"
elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    OS_TYPE="windows"
fi

echo "[INFO] Operating System detected: $OS_TYPE"

# Set python command
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Check/Create virtual environment
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
echo "[INFO] Activating virtual environment..."
if [ "$OS_TYPE" == "windows" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install dependencies
echo "[INFO] Verifying dependencies..."
pip install -r requirements.txt -q

# AUTO-BUILD MAP LOGIC (Only runs if cache is missing)
CACHE_FILE="graph_cache/indonesia_optimized_graph.pkl.xz"

if [ ! -f "$CACHE_FILE" ]; then
    echo ""
    echo "⚠️ CACHE PETA TIDAK DITEMUKAN ($CACHE_FILE) ⚠️"
    echo "Sistem akan otomatis mengunduh dan membangun cache peta untuk Anda."
    echo "Proses ini membutuhkan waktu 10-15 menit (Hanya dilakukan satu kali)."
    echo ""
    
    # Install osmctools (osmconvert & osmfilter) jika belum ada
    if ! command -v osmconvert &>/dev/null || ! command -v osmfilter &>/dev/null; then
        echo "[INFO] osmctools (osmconvert/osmfilter) belum terinstall. Menginstall..."
        if [ "$OS_TYPE" == "linux" ]; then
            sudo apt-get update -qq && sudo apt-get install -y -qq osmctools
        elif [ "$OS_TYPE" == "mac" ]; then
            if command -v brew &>/dev/null; then
                brew install osmctools
            else
                echo "[❌] Homebrew tidak ditemukan. Install dulu: https://brew.sh"
                exit 1
            fi
        elif [ "$OS_TYPE" == "windows" ]; then
            if command -v choco &>/dev/null; then
                choco install osmctools -y
            else
                echo "[❌] osmconvert.exe / osmfilter.exe tidak ditemukan di PATH."
                echo "     Download manual dari: https://wiki.openstreetmap.org/wiki/Osmconvert"
                echo "     Letakkan di folder proyek atau tambahkan ke PATH."
                exit 1
            fi
        else
            echo "[❌] OS tidak dikenali. Install osmctools secara manual."
            exit 1
        fi

        # Verifikasi instalasi berhasil
        if ! command -v osmconvert &>/dev/null; then
            echo "[❌] GAGAL: osmconvert tidak berhasil diinstall."
            exit 1
        fi
        echo "[✅] osmctools berhasil diinstall."
    else
        echo "[INFO] osmctools sudah terinstall."
    fi
    echo ""

    
    function show_progress() {
        local task_name=$1
        local script_name=$2
        
        echo -e "\n[⏳] SEDANG BERJALAN: $task_name..."
        echo "     Mengeksekusi $script_name"
        
        $PYTHON_CMD $script_name
        
        if [ $? -eq 0 ]; then
            echo "[✅] SELESAI: $task_name"
        else
            echo "[❌] GAGAL: $task_name. Proses dihentikan."
            exit 1
        fi
    }

    # Tahapan Setup Data
    if [ -f "data_tools/download_pbf.py" ]; then
        show_progress "Mendownload Peta PBF Terbaru" "data_tools/download_pbf.py"
    fi
    
    show_progress "Memfilter Peta (Motorway -> Unclassified)" "data_tools/build_offline_map.py"

    if [ -f "data_tools/inject_toll_roads.py" ]; then
        show_progress "Menginjeksi Data Tarif Tol & Ferries" "data_tools/inject_toll_roads.py"
    fi

    echo -e "\n[⏳] SEDANG BERJALAN: Membuat Cache Graf .pkl.xz..."
    echo "     (Proses ini memakan waktu 1-2 menit)"
    $PYTHON_CMD -c "from main import download_and_process_graph; download_and_process_graph()"
    
    # Compress manual jika main.py belum mengompres
    if [ -f "graph_cache/indonesia_optimized_graph.pkl" ] && [ ! -f "$CACHE_FILE" ]; then
        echo "     Mengecilkan ukuran file cache (LZMA Compression)..."
        $PYTHON_CMD -c "import pickle, lzma, os; lzma.open('$CACHE_FILE', 'wb').write(pickle.dumps(pickle.load(open('graph_cache/indonesia_optimized_graph.pkl', 'rb')))); os.remove('graph_cache/indonesia_optimized_graph.pkl')"
    fi
    echo "[✅] SELESAI: Cache Graf berhasil dibuat!"

    if [ -f "data_tools/split_cache.py" ]; then
        show_progress "Memecah File Cache (< 100MB untuk GitHub)" "data_tools/split_cache.py"
    fi

    echo ""
    echo " 🎉 PROSES BUILD PETA & CACHE TELAH SELESAI SEMPURNA! 🎉"
    echo ""
else
    echo "[INFO] Cache peta siap digunakan: $CACHE_FILE"
fi

# Run the application
echo "🚀 STARTING LOGISTICS ROUTING SIMULATOR SERVER..."
python -m uvicorn main:app --reload --port 8001
