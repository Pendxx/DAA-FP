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

---

## 🚀 Cara Menjalankan (Paling Cepat & Mudah)

**Langkah 1: Persiapan Environment**
Duplikat (*copy-paste*) file `.env.example` yang ada di dalam folder proyek ini, lalu ubah namanya (*rename*) menjadi `.env`. File ini menyimpan konfigurasi port dan lingkungan server.

**Langkah 2: Instalasi Library**
Pastikan Anda sudah meng-install semua library Python yang dibutuhkan. Buka terminal di folder ini dan jalankan:
```bash
pip install -r requirements.txt
```

**Langkah 3: Menjalankan Server**
Anda **TIDAK PERLU** mendownload file peta mentah (`jawa_highway_ferry.osm` atau `.pbf`) karena graf jalan rayanya sudah kami *Pre-Build* dan simpan di dalam folder `graph_cache/jawa_offline_graph.pkl.xz`. Sistem akan langsung membaca data cache ini sehingga server menyala dalam hitungan detik.

Untuk menjalankan server di komputer Anda, Anda bisa menggunakan perintah manual `python -m uvicorn main:app --reload` atau cukup gunakan *runner script* otomatis berikut:

**Pengguna Windows:**
Klik ganda (*Double Click*) file `run.ps1` atau jalankan via PowerShell:
```powershell
.\run.ps1
```

**Pengguna Mac/Linux:**
```bash
./run.sh
```

Script tersebut akan secara otomatis:
1. Membuat virtual environment Python (`venv`).
2. Meng-install dependencies (`fastapi`, `uvicorn`, dll) dari `requirements.txt`.
3. Menjalankan *Web Server* di port 8000.

Buka browser Anda dan kunjungi: **http://127.0.0.1:8000/**

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
- `graph_cache/` - Menyimpan database graf pre-built yang sudah dikompresi agar tidak perlu me-load XML lagi.
- `static/` - Berisi file frontend UI (`index.html`, `app.js`, `style.css`).
- `data_tools/` - *(Opsional)* Berisi alat-alat dan script pendukung yang dipakai untuk meracik/membangun ulang peta dari mentah (Overpass API, PBF, dll). Anda tidak perlu menyentuh folder ini jika hanya ingin menjalankan aplikasi.
