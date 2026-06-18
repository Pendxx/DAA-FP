# Logistics Dispatch Simulator (Java Edition)

Simulator rute logistik untuk Pulau Jawa yang mencari rute tercepat dan termurah (Dijkstra vs Floyd-Warshall) pada jaringan jalan asli dari OpenStreetMap (OSM).

Proyek ini dibangun untuk memenuhi kriteria Final Exam DAA: *Design It, Prove It, Build It, Measure It*.

## Fitur Utama
1. **Dua Algoritma dari Nol**: Menggunakan implementasi murni (tanpa library) untuk `Dijkstra` (O((V+E)log V)) dan `Floyd-Warshall` (O(V³)).
2. **Peta Asli OSM Jawa (Termasuk Tol)**: Memproses data PBF Jawa menjadi graf berbobot (jarak Haversine) dengan >114.000 *nodes* persimpangan, gerbang tol, dan feri pelabuhan.
3. **Kendaraan & Larangan Tol Dinamis**: Memiliki logika restriksi kendaraan spesifik (cth: Motor dilarang melewati rute dengan properti *Motorway/Toll*), yang dieksekusi secara efisien (O(1) checks) langsung di dalam fase relaksasi Dijkstra dan graf pembangun Floyd-Warshall. Jika pengguna berpindah opsi ke Mobil, otomatis rute akan mengalkulasi ulang jalur terefisien tanpa batasan.
4. **Multi-Stop TSP**: Pengguna dapat menambahkan lebih dari 2 (dua) titik destinasi sekaligus. Algoritma akan mencari rute optimal/permutasi terpendek untuk mengunjungi semua titik tersebut seperti permasalahan *Traveling Salesperson Problem (TSP)*.
5. **Reproducibility Benchmark**: Disediakan satu script (`benchmark.py`) untuk menghasilkan data CSV komparasi kecepatan dan membuktikan verifikasi hasil (*correctness cross-check*).
6. **Interactive Web UI**: Antarmuka Leaflet interaktif untuk memilih titik awal, tujuan, serta penyesuaian kendaraan (*Auto Re-Route*).

## Persyaratan (Requirements)
- Python 3.9+
- Library pendukung (tertera di `requirements.txt`):
  - `fastapi`
  - `uvicorn`
  - `pydantic`
  - `osmnx`
  - `networkx`
  - `shapely`
  - `beautifulsoup4`

---

## 🚀 Cara Menjalankan (Paling Cepat & Mudah)

Aplikasi ini menggunakan peta jalan asli sehingga memerlukan unduhan data OSM. Kami menyediakan *script* otomatis agar Anda tidak repot mengetik perintah manual.

### 🪟 Pengguna Windows (1-Click Auto Run)
Cara paling mudah untuk pengguna Windows:
1. Buka folder proyek (`DAA-FP`) di File Explorer Anda.
2. Cari dan klik dua kali (*double-click*) file **`run_windows.bat`**.
3. Script akan berjalan secara otomatis:
   - Mencari versi Python yang sesuai dan membuat *virtual environment*.
   - Meng-install seluruh library yang diperlukan (FastAPI, uvicorn, dll).
   - Mengunduh dan memproses peta offline Jawa dari OSM secara otomatis (hanya pada run pertama, membutuhkan waktu sekitar 10-15 menit).
   - Menyalakan server lokal dan langsung membuka browser Anda ke **http://127.0.0.1:8000/**.

*(Catatan: Jangan tutup jendela terminal/cmd warna hitam selama Anda masih ingin memakai aplikasinya).*

### 🍎/🐧 Pengguna Mac / Linux
Anda dapat menggunakan script Bash universal yang telah disediakan:
1. Buka terminal di folder ini.
2. Jalankan perintah:
   ```bash
   ./run.sh
   ```
3. Script akan berjalan secara otomatis:
   - Membuat *virtual environment* dan meng-install semua library.
   - Mengunduh, memfilter, dan membangun cache peta offline Jawa dari OSM secara otomatis (hanya pada run pertama, membutuhkan waktu sekitar 10-15 menit).
   - Menyalakan server lokal.
4. Buka browser dan kunjungi: **http://127.0.0.1:8001/**

### 🛠️ Cara Menjalankan Secara Manual (Semua OS)
Jika Anda tidak ingin menggunakan script otomatis:
1. Buat dan aktifkan virtual environment: `python3 -m venv venv && source venv/bin/activate`
2. Install library: `pip install -r requirements.txt`
3. Download & *build* peta (jika belum ada): `python data_tools/build_offline_map.py`
4. Jalankan server: `python -m uvicorn main:app --reload --port 8001`

### 🧹 Membersihkan / Uninstall
Untuk menghapus semua file yang dibuat oleh `run.sh` (virtual environment, cache peta, data download, dll), jalankan:
```bash
./clean.sh
```
Script ini kompatibel dengan **Linux**, **macOS**, dan **Windows** (via Git Bash/MSYS2).

File yang akan dihapus:
- `venv/` — virtual environment beserta semua pip packages
- `graph_cache/` — cache graf `.pkl` / `.pkl.xz`
- `data_tools/jawa_optimized.osm` — peta terfilter (~800MB)
- `*.pbf` — file PBF hasil download
- `__pycache__/` — Python bytecode cache

---

## Cara Menjalankan Benchmark (Reproducibility)
Untuk menguji eksperimen kompleksitas dan verifikasi *cut property* (apakah jarak Dijkstra = Floyd-Warshall), jalankan command berikut:

```bash
python benchmark.py
```

Script ini akan:
- Memotong graf utama menjadi beberapa *subgraph* dengan ukuran spesifik (V = 100, 250, 500, 1000, 1500).
- Menjalankan Floyd-Warshall secara penuh dan mencatat waktu O(V³) nya.
- Menjalankan Dijkstra SSSP sebanyak 50 kali dan merata-ratakan waktunya.
- Menulis hasilnya ke `benchmark_results.csv`.
*(Catatan: Random seed telah di-fix ke angka 42 agar hasil konsisten di berbagai perangkat).*

## Struktur Direktori Utama
- `main.py` - Core logic, routing algorithm, graph parser, dan backend web server.
- `benchmark.py` - Script untuk pengujian empiris komparasi Dijkstra vs Floyd-Warshall.
- `run.sh` - Script otomatis untuk menjalankan aplikasi di Linux dan macOS.
- `run_windows.bat` - Script otomatis untuk menjalankan aplikasi di Windows (double-click).
- `clean.sh` - Script untuk menghapus semua file yang di-generate (kompatibel Linux, macOS, dan Windows via Git Bash).
- `graph_cache/` - Menyimpan database graf pre-built yang sudah dikompresi agar tidak perlu me-load XML lagi.
- `static/` - Berisi file frontend UI (`index.html`, `app.js`, `style.css`).
- `data_tools/` - *(Opsional)* Berisi alat-alat dan script pendukung yang dipakai untuk meracik/membangun ulang peta dari mentah (Overpass API, PBF, dll). Anda tidak perlu menyentuh folder ini jika hanya ingin menjalankan aplikasi.
