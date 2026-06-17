# Logistics Dispatch Simulator (Java Edition)

Simulator rute logistik untuk Pulau Jawa yang mencari rute tercepat dan termurah (Dijkstra vs Floyd-Warshall) pada jaringan jalan asli dari OpenStreetMap (OSM).

Proyek ini dibangun untuk memenuhi kriteria Final Exam DAA: *Design It, Prove It, Build It, Measure It*.

## Fitur Utama
1. **Dua Algoritma dari Nol**: Menggunakan implementasi murni (tanpa library) untuk `Dijkstra` (O((V+E)log V)) dan `Floyd-Warshall` (O(V³)).
2. **Peta Asli OSM Jawa**: Memproses file PBF Jawa menjadi graf berbobot (jarak Haversine) dengan >64.000 *nodes* jalan utama dan feri.
3. **Reproducibility Benchmark**: Disediakan satu script (`benchmark.py`) untuk menghasilkan data CSV komparasi kecepatan dan membuktikan verifikasi hasil (*correctness cross-check*).
4. **Interactive Web UI**: Antarmuka Leaflet interaktif untuk memilih titik awal dan tujuan.

## Persyaratan (Requirements)
- Python 3.9+
- `fastapi`, `uvicorn`, `pydantic` (hanya untuk server web)

Install dependencies dengan:
```bash
pip install -r requirements.txt
```

## Cara Menjalankan (Build & Run)
1. **(Opsional) Generate Peta Baru**: Jika Anda belum memiliki `jawa_highway_ferry.osm`, Anda bisa membuatnya dari PBF mentah menggunakan *tools* OSM bawaan (osmconvert & osmfilter):
   ```bash
   osmconvert.exe jawa-latest.osm.pbf -o=jawa.o5m
   osmfilter.exe jawa.o5m --keep="highway=motorway =trunk =primary =secondary route=ferry" -o=jawa_highway_ferry.osm
   ```
2. **Jalankan Server Web**:
   ```bash
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   *Catatan: Saat dijalankan pertama kali, backend akan mem-parsing file .osm yang butuh waktu sekitar 1 menit. Setelah itu graf akan di-cache ke dalam `graph_cache/` agar instan di masa mendatang.*
3. **Buka Browser**: Akses `http://127.0.0.1:8000/` untuk menggunakan simulator.

## Cara Menjalankan Benchmark (Reproducibility)
Untuk menguji eksperimen kompleksitas dan verifikasi *cut property* (apakah Dijkstra = Floyd-Warshall), jalankan satu command berikut:

```bash
python benchmark.py
```

Script ini akan:
- Memotong graf ke beberapa ukuran spesifik (V = 100, 250, 500, 1000, 1500).
- Menjalankan Floyd-Warshall secara penuh dan mencatat waktunya.
- Menjalankan Dijkstra SSSP sebanyak 50 kali dan merata-ratakan waktunya.
- Menulis hasilnya ke `benchmark_results.csv`.
*(Catatan: Random seed telah di-fix ke angka 42 agar hasil konsisten di berbagai perangkat).*

## Struktur File Penting
- `main.py` - Core logic, routing algorithm, graph parser, and web server.
- `benchmark.py` - Script untuk menguji empiris komparasi Dijkstra vs FW.
- `static/` - Berisi file frontend (`index.html`, `app.js`, `style.css`).
