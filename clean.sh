#!/bin/bash

#   LOGISTICS DISPATCH SIMULATOR - CLEAN / UNINSTALL
#   Kompatibel: Linux (Ubuntu/Debian), macOS, Windows (Git Bash/MSYS2)
#
#   Menghapus semua file yang dibuat oleh run.sh:
#     - Virtual environment (venv/)
#     - Graph cache (graph_cache/)
#     - Downloaded/processed map data (data_tools/*.osm, *.pbf, *.o5m)
#     - Python cache (__pycache__/)
#     - Downloaded PBF file di root

set -e

echo "  LOGISTICS DISPATCH SIMULATOR - CLEANUP TOOL"

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
echo ""

# Pindah ke direktori script ini berada
cd "$(dirname "$0")"

# Fungsi helper untuk menghapus file/folder
remove_item() {
    local path="$1"
    local label="$2"

    if [ -e "$path" ]; then
        rm -rf "$path"
        echo "  [✅] Dihapus: $label ($path)"
    else
        echo "  [—]  Tidak ada: $label ($path)"
    fi
}

# 1. Hapus Virtual Environment
echo "[1/5] Menghapus Virtual Environment..."
remove_item "venv" "Virtual Environment"

# 2. Hapus Graph Cache
echo ""
echo "[2/5] Menghapus Graph Cache..."
remove_item "graph_cache/indonesia_optimized_graph.pkl.xz" "Cache graf Indonesia (compressed)"
remove_item "graph_cache/indonesia_optimized_graph.pkl" "Cache graf Indonesia (uncompressed)"
remove_item "graph_cache/jawa_optimized_graph.pkl.xz" "Cache graf Jawa lama (compressed)"
remove_item "graph_cache/jawa_optimized_graph.pkl" "Cache graf Jawa lama (uncompressed)"
# Hapus folder graph_cache jika kosong
if [ -d "graph_cache" ]; then
    if [ -z "$(ls -A graph_cache 2>/dev/null)" ]; then
        rmdir "graph_cache"
        echo "  [✅] Dihapus: Folder graph_cache/ (kosong)"
    else
        echo "  [⚠️]  Folder graph_cache/ masih berisi file lain, tidak dihapus."
    fi
fi

# 3. Hapus Data Peta yang Didownload/Diproses
echo ""
echo "[3/5] Menghapus Data Peta (OSM, PBF, O5M)..."
# File hasil download & filter di data_tools/
remove_item "data_tools/indonesia_optimized.osm" "Peta OSM Indonesia terfilter"
remove_item "data_tools/indonesia.o5m" "File O5M Indonesia sementara"
remove_item "data_tools/indonesia-latest.osm.pbf" "PBF Indonesia di data_tools"
# File lama (Jawa)
remove_item "data_tools/jawa_optimized.osm" "Peta OSM Jawa lama"
remove_item "data_tools/jawa_optimized.o5m" "File O5M Jawa lama"
remove_item "data_tools/java-latest.osm.pbf" "PBF Jawa di data_tools"
# File PBF di root project
remove_item "indonesia-latest.osm.pbf" "PBF Indonesia di root"
remove_item "jawa-latest.osm.pbf" "PBF Jawa lama di root"
remove_item "java-latest.osm.pbf" "PBF Jawa lama di root (alt)"

# 4. Hapus Python Cache
echo ""
echo "[4/5] Menghapus Python Cache (__pycache__)..."
# Cari dan hapus semua __pycache__ secara rekursif
CACHE_COUNT=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
if [ "$CACHE_COUNT" -gt 0 ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    echo "  [✅] Dihapus: $CACHE_COUNT folder __pycache__"
else
    echo "  [—]  Tidak ada folder __pycache__"
fi
# Hapus .pyc files yang mungkin tersisa
PYC_COUNT=$(find . -name "*.pyc" -type f 2>/dev/null | wc -l)
if [ "$PYC_COUNT" -gt 0 ]; then
    find . -name "*.pyc" -type f -delete 2>/dev/null
    echo "  [✅] Dihapus: $PYC_COUNT file .pyc"
fi

# 5. Hapus file sementara lain
echo ""
echo "[5/5] Menghapus file sementara lainnya..."
remove_item "benchmark_results.csv" "Hasil benchmark"

# Ringkasan
echo ""
echo "  🧹 CLEANUP SELESAI!"
echo ""
echo "  Yang sudah dihapus:"
echo "    • venv/              (virtual environment + semua pip packages)"
echo "    • graph_cache/       (cache graf .pkl / .pkl.xz)"
echo "    • data_tools/*.osm   (peta terfilter ~800MB)"
echo "    • *.pbf              (file PBF download)"
echo "    • __pycache__/       (Python bytecode cache)"
echo ""
echo "  Untuk menjalankan ulang, cukup eksekusi:"
echo "    ./run.sh"
echo ""
