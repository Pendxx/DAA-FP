#!/bin/bash

echo "========================================================="
echo "  LOGISTICS DISPATCH SIMULATOR - AUTOMATED LAUNCHER"
echo "========================================================="

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

# =========================================================================
# AUTO-BUILD MAP LOGIC (Only runs if cache is missing)
# =========================================================================
CACHE_FILE="graph_cache/jawa_optimized_graph.pkl.xz"

if [ ! -f "$CACHE_FILE" ]; then
    echo ""
    echo "⚠️ CACHE PETA TIDAK DITEMUKAN ($CACHE_FILE) ⚠️"
    echo "Sistem akan otomatis mengunduh dan membangun cache peta untuk Anda."
    echo "Proses ini membutuhkan waktu 10-15 menit (Hanya dilakukan satu kali)."
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
    if [ -f "graph_cache/jawa_optimized_graph.pkl" ] && [ ! -f "$CACHE_FILE" ]; then
        echo "     Mengecilkan ukuran file cache (LZMA Compression)..."
        $PYTHON_CMD -c "import pickle, lzma, os; lzma.open('$CACHE_FILE', 'wb').write(pickle.dumps(pickle.load(open('graph_cache/jawa_optimized_graph.pkl', 'rb')))); os.remove('graph_cache/jawa_optimized_graph.pkl')"
    fi
    echo "[✅] SELESAI: Cache Graf berhasil dibuat!"

    if [ -f "data_tools/split_cache.py" ]; then
        show_progress "Memecah File Cache (< 100MB untuk GitHub)" "data_tools/split_cache.py"
    fi

    echo ""
    echo "========================================================="
    echo " 🎉 PROSES BUILD PETA & CACHE TELAH SELESAI SEMPURNA! 🎉"
    echo "========================================================="
    echo ""
else
    echo "[INFO] Cache peta siap digunakan: $CACHE_FILE"
fi

# Run the application
echo "========================================================="
echo "🚀 STARTING LOGISTICS ROUTING SIMULATOR SERVER..."
echo "========================================================="
python -m uvicorn main:app --reload
