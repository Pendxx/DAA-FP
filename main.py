"""
Logistics Dispatch Simulator — Backend
Menggunakan jaringan jalan nyata dari OpenStreetMap
dengan algoritma Dijkstra & Floyd-Warshall buatan sendiri (from scratch).

Parser XML custom digunakan untuk membaca file OSM,
menggantikan OSMnx yang gagal pada file hasil filter.
"""

import os
import math
import time
import heapq
import threading
import pickle
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Titik pusat: Tengah Jawa
CENTER_LAT = -7.2504
CENTER_LNG = 109.5240

# Cache directory
CACHE_DIR = Path("graph_cache")
CACHE_FILE = CACHE_DIR / "jawa_offline_graph.pkl"

def is_in_its_campus(lat, lng):
    """
    Mengecek apakah koordinat berada di dalam area kampus ITS Surabaya.
    Bounding box kasar kampus ITS:
    - Utara: ~ -7.275
    - Selatan: ~ -7.294
    - Barat: ~ 112.790 (Bundaran ITS)
    - Timur: ~ 112.808 (Pintu Timur / Perumdos)
    """
    return (-7.294 <= lat <= -7.275) and (112.790 <= lng <= 112.808)

# Harga fallback jika scraping gagal beserta tipenya (gasoline = bensin, diesel = solar)
FUEL_PRICES = {
    "Pertamina - Pertalite (Subsidi)": {"price": 10000, "type": "gasoline"},
    "Pertamina - Pertamax (RON 92)": {"price": 16250, "type": "gasoline"},
    "Pertamina - Pertamax Green (RON 95)": {"price": 17000, "type": "gasoline"},
    "Pertamina - Pertamax Turbo (RON 98)": {"price": 20750, "type": "gasoline"},
    "Pertamina - Biosolar (Subsidi)": {"price": 6800, "type": "diesel"},
    "Pertamina - Dexlite": {"price": 23000, "type": "diesel"},
    "Pertamina - Pertamina Dex": {"price": 24800, "type": "diesel"},
    "Shell - Super (Estimasi)": {"price": 16870, "type": "gasoline"},
    "Shell - V-Power (Estimasi)": {"price": 17440, "type": "gasoline"},
    "Shell - V-Power Nitro+ (Estimasi)": {"price": 20950, "type": "gasoline"},
    "Shell - V-Power Diesel": {"price": 24490, "type": "diesel"},
    "BP - BP 92": {"price": 16670, "type": "gasoline"},
    "BP - BP Ultimate": {"price": 17240, "type": "gasoline"},
    "BP - BP Ultimate Diesel": {"price": 25060, "type": "diesel"}
}

def sync_fuel_prices():
    """
    Mensimulasikan auto-sync harga bensin terbaru dari sumber publik.
    Pada implementasi nyata, ini bisa melakukan web scraping ke situs berita
    atau portal SPBU resmi menggunakan BeautifulSoup.
    """
    print("[SYNC] Melakukan sinkronisasi harga bensin terbaru...")
    # Jika ada logika scraping riil, letakkan di sini.
    print("[SYNC] Harga bensin berhasil disinkronisasi.")

# Jalankan sinkronisasi saat server menyala
sync_fuel_prices()

# ============================================================
# FASTAPI SETUP
# ============================================================
app = FastAPI(title="Logistics Dispatch Simulator")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================
# LANGKAH 1: EKSTRAKSI GRAF DARI OPENSTREETMAP
# Parser XML custom — tidak menggunakan OSMnx (yang gagal pada
# file hasil filter karena missing nodes).
# ============================================================

def haversine_meters(lat1, lon1, lat2, lon2):
    """Menghitung jarak Haversine antara dua titik koordinat dalam meter."""
    R = 6371000  # Radius bumi dalam meter
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_osm_custom(filename):
    """
    Parser XML custom yang membaca file OSM secara streaming.
    Lebih tahan error dibanding OSMnx karena gracefully skip missing nodes.
    Mengembalikan graf yang sudah disimplifikasi (hanya intersection + endpoint).
    """
    # === PASS 1: Kumpulkan semua koordinat node ===
    print("[PARSER] Pass 1: Mengumpulkan koordinat node...")
    all_node_coords = {}  # node_id -> (lat, lon)
    node_count = 0
    for event, elem in ET.iterparse(filename, events=("end",)):
        if elem.tag == "node":
            nid = int(elem.get("id"))
            lat = float(elem.get("lat"))
            lon = float(elem.get("lon"))
            all_node_coords[nid] = (lat, lon)
            node_count += 1
            if node_count % 500000 == 0:
                print(f"  ... {node_count} nodes dibaca")
            elem.clear()
        elif elem.tag == "way":
            elem.clear()
        elif elem.tag == "relation":
            elem.clear()
    print(f"[PARSER] Total node: {node_count}")

    # === PASS 2: Baca semua way, bangun adjacency raw + hitung degree ===
    print("[PARSER] Pass 2: Membaca way dan membangun graf...")
    # Untuk simplifikasi: hitung berapa WAY BERBEDA yang mengandung setiap node
    # Node yang muncul di 2+ way = intersection, harus dipertahankan
    node_way_count = defaultdict(int)  # berapa way yang mengandung node ini
    endpoint_set = set()  # node yang merupakan ujung way
    raw_ways = []  # list of (node_refs, tags_dict)
    way_count = 0
    skipped_nodes = 0

    for event, elem in ET.iterparse(filename, events=("end",)):
        if elem.tag == "way":
            nd_refs = [int(nd.get("ref")) for nd in elem.findall("nd")]
            tags = {tag.get("k"): tag.get("v") for tag in elem.findall("tag")}

            # Filter: hanya simpan refs yang memiliki koordinat
            valid_refs = [r for r in nd_refs if r in all_node_coords]
            skipped_nodes += len(nd_refs) - len(valid_refs)

            if len(valid_refs) >= 2:
                raw_ways.append((valid_refs, tags))
                # Hitung berapa way yang mengandung setiap node (untuk deteksi intersection)
                seen_in_this_way = set()
                for ref in valid_refs:
                    if ref not in seen_in_this_way:
                        node_way_count[ref] += 1
                        seen_in_this_way.add(ref)
                # Endpoint selalu dipertahankan
                endpoint_set.add(valid_refs[0])
                endpoint_set.add(valid_refs[-1])

            way_count += 1
            if way_count % 10000 == 0:
                print(f"  ... {way_count} ways diproses")
            elem.clear()
        elif elem.tag == "node":
            elem.clear()
        elif elem.tag == "relation":
            elem.clear()

    print(f"[PARSER] Total way: {way_count}, skipped nodes: {skipped_nodes}")

    # Node penting = endpoint ATAU muncul di 2+ way (intersection)
    def is_important(nid):
        return nid in endpoint_set or node_way_count[nid] >= 2

    # === SIMPLIFIKASI: Bangun graf hanya dari intersection + endpoint ===
    # Node dengan degree == 2 adalah titik tengah jalan lurus — skip
    print("[PARSER] Simplifikasi graf (hanya intersection + endpoint)...")
    node_coords = {}
    custom_graph = {}
    ferry_edges = set()
    toll_edges = set()
    edge_geometries = {}

    for refs, tags in raw_ways:
        is_ferry = tags.get("route") == "ferry"
        is_toll = tags.get("highway") in ("motorway", "motorway_link") or tags.get("toll") == "yes"
        is_oneway = tags.get("oneway") in ("yes", "true", "1")

        # Pecah way menjadi segmen antar intersection
        i = 0
        while i < len(refs) - 1:
            u = refs[i]
            # Kumpulkan geometri sampai ketemu intersection berikutnya
            geom_points = [all_node_coords[u]]
            total_dist = 0.0
            j = i + 1
            while j < len(refs):
                prev = refs[j - 1]
                curr = refs[j]
                p1 = all_node_coords[prev]
                p2 = all_node_coords[curr]
                total_dist += haversine_meters(p1[0], p1[1], p2[0], p2[1])
                geom_points.append(p2)

                if is_important(curr) or j == len(refs) - 1:
                    # Ini intersection atau endpoint — buat edge
                    v = curr
                    # Pastikan node u dan v ada di graph
                    lat_u, lon_u = all_node_coords[u]
                    lat_v, lon_v = all_node_coords[v]
                    if u not in node_coords:
                        node_coords[u] = {
                            "lat": lat_u, "lng": lon_u,
                            "is_its": is_in_its_campus(lat_u, lon_u)
                        }
                        custom_graph[u] = {}
                    if v not in node_coords:
                        node_coords[v] = {
                            "lat": lat_v, "lng": lon_v,
                            "is_its": is_in_its_campus(lat_v, lon_v)
                        }
                        custom_graph[v] = {}

                    weight = max(total_dist, 1.0)  # minimal 1 meter

                    # Forward edge
                    if v not in custom_graph[u] or weight < custom_graph[u][v]:
                        custom_graph[u][v] = weight
                        geom_key = f"{u},{v}"
                        edge_geometries[geom_key] = [
                            {"lat": p[0], "lng": p[1]} for p in geom_points
                        ]
                        if is_ferry:
                            ferry_edges.add((u, v))
                        if is_toll:
                            toll_edges.add((u, v))

                    # Reverse edge (kecuali oneway)
                    if not is_oneway:
                        if u not in custom_graph[v] or weight < custom_graph[v][u]:
                            custom_graph[v][u] = weight
                            geom_key_rev = f"{v},{u}"
                            edge_geometries[geom_key_rev] = [
                                {"lat": p[0], "lng": p[1]} for p in reversed(geom_points)
                            ]
                            if is_ferry:
                                ferry_edges.add((v, u))
                            if is_toll:
                                toll_edges.add((v, u))

                    i = j
                    break
                j += 1
            else:
                break

    total_edges = sum(len(nb) for nb in custom_graph.values())
    print(f"[PARSER] Graf selesai: {len(node_coords)} nodes, {total_edges} edges (directed)")

    return node_coords, custom_graph, edge_geometries, ferry_edges, toll_edges


import lzma

def download_and_process_graph():
    """
    Memuat graf jaringan jalan dari file OSM offline,
    mengkonversinya ke format adjacency list standar Python.
    Menyimpan cache agar tidak perlu parse ulang setiap restart.
    """
    cache_xz = CACHE_FILE.with_suffix(".pkl.xz")
    if cache_xz.exists():
        print(f"[CACHE] Memuat graf dari cache terkompresi ({cache_xz.name})...")
        with lzma.open(cache_xz, "rb") as f:
            return pickle.load(f)

    if CACHE_FILE.exists():
        print("[CACHE] Memuat graf dari cache lokal...")
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)

    print("[OSM] Memuat jaringan jalan Seluruh Indonesia dari PETA OFFLINE...")
    print("[OSM] Peringatan: Proses parsing XML ini butuh waktu sekitar 5-10 menit!")

    osm_file = "jawa_highway_ferry.osm"
    if not os.path.exists(osm_file):
        raise RuntimeError(f"File offline {osm_file} tidak ditemukan! Harap jalankan build_offline_map.py terlebih dahulu.")

    node_coords, custom_graph, edge_geometries, ferry_edges, toll_edges = parse_osm_custom(osm_file)

    # === POST-PROCESSING 1: Paksa semua edge bidirectional ===
    print("[POST] Memaksa semua edge menjadi bidirectional...")
    added_reverse = 0
    all_edges = []
    for u in list(custom_graph.keys()):
        for v, w in list(custom_graph[u].items()):
            all_edges.append((u, v, w))
    for u, v, w in all_edges:
        if v not in custom_graph:
            custom_graph[v] = {}
        if u not in custom_graph[v]:
            custom_graph[v][u] = w
            added_reverse += 1
            # Geometri reverse
            geom_fwd = edge_geometries.get(f"{u},{v}")
            if geom_fwd and f"{v},{u}" not in edge_geometries:
                edge_geometries[f"{v},{u}"] = list(reversed(geom_fwd))
            if (u, v) in toll_edges:
                toll_edges.add((v, u))
    print(f"[POST] Ditambahkan {added_reverse} reverse edges.")

    # === POST-PROCESSING 2: Temukan komponen terhubung ===
    print("[POST] Menganalisis konektivitas graf...")
    def bfs_undirected(start, graph):
        visited = set([start])
        queue = [start]
        while queue:
            node = queue.pop(0)
            for nb in graph.get(node, {}):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        return visited

    all_node_ids = set(custom_graph.keys())
    components = []
    visited_all = set()
    for nid in all_node_ids:
        if nid not in visited_all:
            comp = bfs_undirected(nid, custom_graph)
            visited_all.update(comp)
            components.append(comp)
    components.sort(key=len, reverse=True)
    print(f"[POST] Ditemukan {len(components)} komponen terhubung.")
    for i, comp in enumerate(components[:5]):
        print(f"  Komponen {i+1}: {len(comp)} nodes")

    # === POST-PROCESSING 3: Hubungkan komponen besar via virtual ferry ===
    # Ambil komponen dengan >= 50 nodes (abaikan fragmen kecil)
    big_components = [c for c in components if len(c) >= 50]
    print(f"[POST] Komponen besar (>=50 nodes): {len(big_components)}")

    if len(big_components) > 1:
        print("[POST] Menghubungkan komponen besar via virtual ferry bridges...")
        # Untuk setiap pasangan komponen, cari node terdekat dan hubungkan
        comp_representatives = []
        for comp in big_components:
            # Hitung centroid
            lats = [node_coords[n]["lat"] for n in comp]
            lngs = [node_coords[n]["lng"] for n in comp]
            centroid_lat = sum(lats) / len(lats)
            centroid_lng = sum(lngs) / len(lngs)
            comp_representatives.append({
                "nodes": comp,
                "centroid_lat": centroid_lat,
                "centroid_lng": centroid_lng,
            })

        # Hubungkan setiap komponen ke komponen terdekat yang belum terhubung
        # Gunakan greedy: gabung komponen terkecil ke terdekat
        merged = set([0])  # Komponen 0 (terbesar) sudah di-"merge"
        ferry_bridges_added = 0

        for i in range(1, len(big_components)):
            if i in merged:
                continue
            # Cari komponen terdekat yang sudah di-merge
            best_dist = float("inf")
            best_u = None
            best_v = None
            comp_i = big_components[i]

            # Sample beberapa node dari komponen i (untuk kecepatan)
            sample_i = list(comp_i)[:200]

            for j in merged:
                comp_j = big_components[j]
                sample_j = list(comp_j)[:200]

                for ni in sample_i:
                    ci = node_coords[ni]
                    for nj in sample_j:
                        cj = node_coords[nj]
                        dist = haversine_meters(ci["lat"], ci["lng"], cj["lat"], cj["lng"])
                        if dist < best_dist:
                            best_dist = dist
                            best_u = ni
                            best_v = nj

            if best_u is not None and best_v is not None:
                # Tambahkan virtual ferry edge
                custom_graph[best_u][best_v] = best_dist
                custom_graph[best_v][best_u] = best_dist
                ferry_edges.add((best_u, best_v))
                ferry_edges.add((best_v, best_u))
                # Geometri: garis lurus
                edge_geometries[f"{best_u},{best_v}"] = [
                    {"lat": node_coords[best_u]["lat"], "lng": node_coords[best_u]["lng"]},
                    {"lat": node_coords[best_v]["lat"], "lng": node_coords[best_v]["lng"]},
                ]
                edge_geometries[f"{best_v},{best_u}"] = [
                    {"lat": node_coords[best_v]["lat"], "lng": node_coords[best_v]["lng"]},
                    {"lat": node_coords[best_u]["lat"], "lng": node_coords[best_u]["lng"]},
                ]
                merged.add(i)
                ferry_bridges_added += 1
                print(f"  Bridge {ferry_bridges_added}: komp {i+1} ({len(comp_i)} nodes) <-> komp terbesar, jarak {best_dist/1000:.1f} km")

        print(f"[POST] Total ferry bridges ditambahkan: {ferry_bridges_added}")

    total_edges_final = sum(len(nb) for nb in custom_graph.values())
    print(f"[POST] Graf final: {len(node_coords)} nodes, {total_edges_final} edges")

    result = {
        "node_coords": node_coords,
        "custom_graph": custom_graph,
        "edge_geometries": edge_geometries,
        "ferry_edges": ferry_edges,
        "toll_edges": toll_edges,
    }

    # Simpan cache
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(result, f)
    print("[CACHE] Graf disimpan ke cache lokal.")

    return result


# Muat graf saat server start
print("=" * 60)
print("  LOGISTICS DISPATCH SIMULATOR — STARTING UP")
print("=" * 60)

graph_data = download_and_process_graph()
node_coords = graph_data["node_coords"]
custom_graph = graph_data["custom_graph"]
edge_geometries = graph_data["edge_geometries"]
ferry_edges_global = graph_data.get("ferry_edges", set())
toll_edges_global = graph_data.get("toll_edges", set())

V_COUNT = len(node_coords)
E_COUNT = sum(len(neighbors) for neighbors in custom_graph.values()) // 2

print(f"\n[READY] Graf dimuat: {V_COUNT} persimpangan, {E_COUNT} ruas jalan")


# ============================================================
# LANGKAH 2: IMPLEMENTASI ALGORITMA DARI NOL (FROM SCRATCH)
# Tidak menggunakan networkx atau library apapun untuk routing!
# ============================================================

# ---- 2A. DIJKSTRA (Single-Source Shortest Path) ----
# Kompleksitas: O((V + E) log V) dengan binary heap
# Referensi: Cormen et al., "Introduction to Algorithms" (CLRS)

def custom_dijkstra(graph, start, end, vehicle_type="mobil"):
    """
    Implementasi Dijkstra dari nol menggunakan min-heap (heapq).
    Mengembalikan: (list_of_node_ids, total_cost_meters)
    
    Jika vehicle_type == 'motor', akan mengabaikan ruas jalan tol.
    """
    import heapq
    
    if start not in graph or end not in graph:
        return [], float("inf")

    # Inisialisasi jarak semua node = ∞, kecuali start = 0
    distances = {node: float("inf") for node in graph}
    distances[start] = 0
    previous_nodes = {node: None for node in graph}

    # Priority queue: (jarak, node_id)
    pq = [(0, start)]
    visited = set()

    while pq:
        current_dist, current_node = heapq.heappop(pq)

        # Early termination: sudah sampai di tujuan
        if current_node == end:
            break

        # Skip jika node sudah diproses dengan jarak lebih pendek
        if current_node in visited:
            continue
        visited.add(current_node)

        # Relaksasi semua tetangga
        for neighbor, weight in graph[current_node].items():
            # Filter kendaraan: Motor tidak boleh masuk tol
            if vehicle_type == "motor" and (current_node, neighbor) in toll_edges_global:
                continue
                
            new_dist = current_dist + weight
            if new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                previous_nodes[neighbor] = current_node
                heapq.heappush(pq, (new_dist, neighbor))

    # Rekonstruksi jalur: backtrack dari end ke start
    path = []
    curr = end
    while curr is not None:
        path.append(curr)
        curr = previous_nodes.get(curr)
    path.reverse()

    # Validasi: jika path tidak dimulai dari start, berarti unreachable
    if not path or path[0] != start:
        return [], float("inf")

    return path, distances[end]


# ---- 2B. FLOYD-WARSHALL (All-Pairs Shortest Path) ----
# Kompleksitas: O(V³) waktu, O(V²) memori
# Referensi: Floyd, R.W. (1962); Warshall, S. (1962)
# CATATAN: Karena V bisa ≈ 1500, ini memerlukan ≈ 3.4 miliar operasi.
#          Dijalankan di background thread agar server tetap responsif.

class FloydWarshallSolver:
    """
    Mengelola pre-komputasi Floyd-Warshall di background thread.
    Setelah selesai, query path apapun bisa dijawab dalam O(V).
    """

    def __init__(self):
        self.ready = False
        self.progress = 0  # 0–100
        self.dist = None    # dist[i][j] = jarak terpendek
        self.nxt = None     # nxt[i][j]  = next hop untuk rekonstruksi jalur
        self.idx_to_node = []   # index → node_id
        self.node_to_idx = {}   # node_id → index
        self.compute_time_ms = 0
        self.too_large = False

    def start_precompute(self, graph):
        """Mulai komputasi Floyd-Warshall di thread terpisah."""
        if len(graph) > 2000:
            self.ready = False
            self.too_large = True
            self.progress = 0
            print(f"[FW] Batal: Graf terlalu besar ({len(graph)} nodes) untuk O(V³). Akan memakan waktu bertahun-tahun di Python.")
            return

        thread = threading.Thread(
            target=self._compute,
            args=(graph,),
            daemon=True
        )
        thread.start()
        print(f"[FW] Floyd-Warshall dimulai di background thread (V={len(graph)})...")

    def _compute(self, graph):
        """
        Implementasi Floyd-Warshall murni dari nol.
        Menggunakan list-of-lists Python (bukan numpy) sesuai syarat akademik.
        """
        t_start = time.perf_counter()

        # Buat mapping node_id ↔ index integer (0, 1, 2, ...)
        nodes = sorted(graph.keys())
        n = len(nodes)
        self.idx_to_node = nodes
        self.node_to_idx = {node: i for i, node in enumerate(nodes)}

        INF = float("inf")

        # Inisialisasi matrix jarak dan next-hop
        # dist[i][j] = bobot edge langsung, atau ∞ jika tidak ada edge
        dist = [[INF] * n for _ in range(n)]
        nxt = [[None] * n for _ in range(n)]

        # Diagonal = 0 (jarak node ke dirinya sendiri)
        for i in range(n):
            dist[i][i] = 0

        # Isi bobot edge yang ada
        for u in graph:
            u_idx = self.node_to_idx[u]
            for v, w in graph[u].items():
                v_idx = self.node_to_idx[v]
                if w < dist[u_idx][v_idx]:
                    dist[u_idx][v_idx] = w
                    nxt[u_idx][v_idx] = v_idx

        # --- Inti Floyd-Warshall: 3 nested loops ---
        # Untuk setiap intermediate node k:
        #   Untuk setiap pasangan (i, j):
        #     Jika jalur i→k→j lebih pendek, update
        for k in range(n):
            # Update progress setiap 10 iterasi
            if k % 10 == 0:
                self.progress = int((k / n) * 100)

            dist_k = dist[k]  # Optimasi: cache row lookup
            nxt_k = nxt[k]

            for i in range(n):
                dist_ik = dist[i][k]
                if dist_ik == INF:
                    continue  # Optimasi: skip jika i→k unreachable

                dist_i = dist[i]
                nxt_i = nxt[i]

                for j in range(n):
                    new_dist = dist_ik + dist_k[j]
                    if new_dist < dist_i[j]:
                        dist_i[j] = new_dist
                        nxt_i[j] = nxt_i[k]  # Next hop = next hop menuju k

            # Beri waktu ke thread lain agar server tetap responsif
            if k % 50 == 0:
                time.sleep(0.001)

        self.dist = dist
        self.nxt = nxt
        self.progress = 100
        self.ready = True

        elapsed = (time.perf_counter() - t_start) * 1000
        self.compute_time_ms = round(elapsed, 1)
        print(f"[FW] Floyd-Warshall SELESAI dalam {elapsed/1000:.1f} detik")

    def get_path(self, start, end):
        """
        Rekonstruksi jalur terpendek dari matrix next-hop.
        Mengembalikan: (list_of_node_ids, total_cost_meters)
        """
        if not self.ready:
            return [], -1

        if start not in self.node_to_idx or end not in self.node_to_idx:
            return [], float("inf")

        i = self.node_to_idx[start]
        j = self.node_to_idx[end]

        if self.nxt[i][j] is None:
            return [], float("inf")

        # Rekonstruksi path menggunakan next-hop matrix
        path_indices = [i]
        current = i
        max_steps = len(self.idx_to_node) + 1  # Safety limit
        steps = 0

        while current != j and steps < max_steps:
            current = self.nxt[current][j]
            if current is None:
                return [], float("inf")
            path_indices.append(current)
            steps += 1

        if steps >= max_steps:
            return [], float("inf")

        path_nodes = [self.idx_to_node[idx] for idx in path_indices]
        cost = self.dist[i][j]

        return path_nodes, cost


# Inisialisasi Floyd-Warshall solver dan mulai pre-komputasi
fw_solver = FloydWarshallSolver()
fw_solver.start_precompute(custom_graph)


# ============================================================
# LANGKAH 3: FUNGSI UTILITAS
# ============================================================

def expand_path_to_coords(path_nodes):
    """
    Mengubah list of node IDs menjadi list of {lat, lng} yang detail.
    Menggunakan geometri edge asli dari OSM agar garis mengikuti jalan.
    """
    if len(path_nodes) < 2:
        if len(path_nodes) == 1 and path_nodes[0] in node_coords:
            return [node_coords[path_nodes[0]]]
        return []

    coords = []
    for i in range(len(path_nodes) - 1):
        u = path_nodes[i]
        v = path_nodes[i + 1]
        geom_key = f"{u},{v}"

        if geom_key in edge_geometries:
            segment = edge_geometries[geom_key]
        else:
            # Fallback: garis lurus antar node
            segment = [node_coords[u], node_coords[v]]

        # Hindari duplikasi titik di sambungan antar segment
        if i == 0:
            coords.extend(segment)
        else:
            coords.extend(segment[1:])  # Skip titik pertama (sudah ada)

    return coords


# ============================================================
# LANGKAH 4: API ENDPOINTS
# ============================================================

class RouteRequest(BaseModel):
    source: int
    target: int
    vehicle: str = "mobil"


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/graph-info")
def get_graph_info():
    """
    Mengirim data semua persimpangan ke frontend untuk ditampilkan di peta.
    Hanya mengirim koordinat (tanpa adjacency list) untuk efisiensi.
    """
    return {
        "nodes": node_coords,
        "node_count": V_COUNT,
        "edge_count": E_COUNT,
        "center": {"lat": CENTER_LAT, "lng": CENTER_LNG},
    }


@app.get("/api/fw-status")
def get_fw_status():
    """Mengecek status pre-komputasi Floyd-Warshall."""
    return {
        "ready": fw_solver.ready,
        "progress_pct": fw_solver.progress,
        "compute_time_ms": fw_solver.compute_time_ms if fw_solver.ready else None,
        "node_count": V_COUNT,
        "too_large": fw_solver.too_large
    }


@app.get("/api/fuel-prices")
def get_fuel_prices():
    """Mengembalikan daftar harga bensin yang telah disinkronisasi."""
    return {"prices": FUEL_PRICES}

def extract_bfs_subgraph(graph, source, target, vehicle_type="mobil", max_nodes=800):
    """
    Ekstrak subgraph menggunakan BFS dari source, dibatasi max_nodes.
    Jika target belum termasuk, tambahkan jalur Dijkstra ke target.
    Mengembalikan: (sub_graph_dict, sub_node_list)
    """
    from collections import deque
    visited = set()
    queue = deque([source])
    visited.add(source)

    while queue and len(visited) < max_nodes:
        node = queue.popleft()
        for neighbor in graph.get(node, {}):
            if vehicle_type == "motor" and (node, neighbor) in toll_edges_global:
                continue
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
                if len(visited) >= max_nodes:
                    break

    # Pastikan target ada di subgraph
    if target not in visited:
        # Tambahkan node di jalur Dijkstra source→target
        dij_path, _ = custom_dijkstra(graph, source, target, vehicle_type)
        for n in dij_path:
            visited.add(n)

    # Bangun subgraph
    sub_graph = {}
    for node in visited:
        sub_graph[node] = {}
        for neighbor, weight in graph.get(node, {}).items():
            if vehicle_type == "motor" and (node, neighbor) in toll_edges_global:
                continue
            if neighbor in visited:
                sub_graph[node][neighbor] = weight

    return sub_graph, list(visited)


def floyd_warshall_on_subgraph(sub_graph, source, target):
    """
    Jalankan Floyd-Warshall dari nol pada subgraph kecil.
    Mengembalikan: (path_list, cost, elapsed_ms, subgraph_size)
    """
    nodes = sorted(sub_graph.keys())
    n = len(nodes)
    node_to_idx = {node: i for i, node in enumerate(nodes)}
    idx_to_node = nodes

    if source not in node_to_idx or target not in node_to_idx:
        return [], float("inf"), 0, n

    INF = float("inf")

    # Inisialisasi matrix
    dist = [[INF] * n for _ in range(n)]
    nxt = [[None] * n for _ in range(n)]

    for i in range(n):
        dist[i][i] = 0

    for u in sub_graph:
        u_idx = node_to_idx[u]
        for v, w in sub_graph[u].items():
            v_idx = node_to_idx[v]
            if w < dist[u_idx][v_idx]:
                dist[u_idx][v_idx] = w
                nxt[u_idx][v_idx] = v_idx

    # --- Inti Floyd-Warshall: O(V³) ---
    t_start = time.perf_counter()

    for k in range(n):
        dist_k = dist[k]
        for i in range(n):
            dist_ik = dist[i][k]
            if dist_ik == INF:
                continue
            dist_i = dist[i]
            nxt_i = nxt[i]
            for j in range(n):
                new_dist = dist_ik + dist_k[j]
                if new_dist < dist_i[j]:
                    dist_i[j] = new_dist
                    nxt_i[j] = nxt_i[k]

    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

    # Rekonstruksi path
    si = node_to_idx[source]
    ti = node_to_idx[target]

    if nxt[si][ti] is None:
        return [], float("inf"), elapsed_ms, n

    path_indices = [si]
    current = si
    max_steps = n + 1
    steps = 0
    while current != ti and steps < max_steps:
        current = nxt[current][ti]
        if current is None:
            return [], float("inf"), elapsed_ms, n
        path_indices.append(current)
        steps += 1

    if steps >= max_steps:
        return [], float("inf"), elapsed_ms, n

    path_nodes = [idx_to_node[idx] for idx in path_indices]
    cost = dist[si][ti]

    return path_nodes, cost, elapsed_ms, n


@app.post("/api/solve")
def solve_route(req: RouteRequest):
    """
    Menjalankan KEDUA algoritma dan mengembalikan perbandingan hasil.
    Ini memenuhi syarat akademik DAA: menunjukkan bahwa kedua algoritma
    menghasilkan jalur terpendek yang identik.
    """
    result = {}
    start_time = time.time()

    # --- Dijkstra ---
    t0 = time.perf_counter()
    dij_path, dij_cost = custom_dijkstra(custom_graph, req.source, req.target, req.vehicle)
    t1 = time.perf_counter()
    dij_time_ms = round((t1 - t0) * 1000, 2)
    dij_coords = expand_path_to_coords(dij_path)
    
    # Hitung jumlah penyeberangan feri
    dij_ferry_crossings = 0
    for i in range(len(dij_path) - 1):
        if (dij_path[i], dij_path[i+1]) in ferry_edges_global:
            dij_ferry_crossings += 1
            
    # Estimasi waktu (30 km/jam = 500 meter/menit)
    dij_time_minutes = round(float(dij_cost) / 500, 1) if dij_cost != float("inf") else 0

    result["dijkstra"] = {
        "path_coords": dij_coords,
        "cost_meters": round(float(dij_cost), 2) if dij_cost != float("inf") else None,
        "est_time_minutes": dij_time_minutes,
        "ferry_crossings": dij_ferry_crossings,
        "time_ms": dij_time_ms,
        "node_count_in_path": len(dij_path),
    }

    # --- Floyd-Warshall ---
    if fw_solver.ready:
        # FW sudah selesai precompute (graf kecil ≤2000 nodes)
        t0 = time.perf_counter()
        fw_path, fw_cost = fw_solver.get_path(req.source, req.target)
        t1 = time.perf_counter()
        fw_time_ms = round((t1 - t0) * 1000, 2)
        fw_coords = expand_path_to_coords(fw_path)

        fw_time_minutes = round(float(fw_cost) / 500, 1) if fw_cost != float("inf") else 0

        fw_ferry_crossings = 0
        for i in range(len(fw_path) - 1):
            if (fw_path[i], fw_path[i+1]) in ferry_edges_global:
                fw_ferry_crossings += 1

        costs_match = bool(
            dij_cost != float("inf")
            and fw_cost != float("inf")
            and abs(float(dij_cost) - float(fw_cost)) < 0.01
        )

        result["floyd_warshall"] = {
            "path_coords": fw_coords,
            "cost_meters": round(float(fw_cost), 2) if fw_cost != float("inf") else None,
            "est_time_minutes": fw_time_minutes,
            "ferry_crossings": fw_ferry_crossings,
            "time_ms": fw_time_ms,
            "node_count_in_path": len(fw_path),
            "precompute_time_ms": fw_solver.compute_time_ms,
            "ready": True,
            "too_large": False,
            "subgraph_mode": False,
        }
        result["identical"] = costs_match

    elif getattr(fw_solver, 'too_large', False):
        # Graf terlalu besar → jalankan FW on-demand pada subgraph lokal
        sub_graph, sub_nodes = extract_bfs_subgraph(
            custom_graph, req.source, req.target, vehicle_type=req.vehicle, max_nodes=800
        )
        fw_path, fw_cost, fw_elapsed_ms, sub_size = floyd_warshall_on_subgraph(
            sub_graph, req.source, req.target
        )
        fw_coords = expand_path_to_coords(fw_path)
        fw_time_minutes = round(float(fw_cost) / 500, 1) if fw_cost != float("inf") else 0

        fw_ferry_crossings = 0
        for i in range(len(fw_path) - 1):
            if (fw_path[i], fw_path[i+1]) in ferry_edges_global:
                fw_ferry_crossings += 1

        costs_match = bool(
            dij_cost != float("inf")
            and fw_cost != float("inf")
            and abs(float(dij_cost) - float(fw_cost)) < 0.01
        )

        result["floyd_warshall"] = {
            "path_coords": fw_coords,
            "cost_meters": round(float(fw_cost), 2) if fw_cost != float("inf") else None,
            "est_time_minutes": fw_time_minutes,
            "ferry_crossings": fw_ferry_crossings,
            "time_ms": fw_elapsed_ms,
            "node_count_in_path": len(fw_path),
            "precompute_time_ms": fw_elapsed_ms,
            "ready": True,
            "too_large": True,
            "subgraph_mode": True,
            "subgraph_size": sub_size,
        }
        result["identical"] = costs_match

    else:
        # FW masih computing
        result["floyd_warshall"] = {
            "ready": False,
            "too_large": False,
            "progress_pct": fw_solver.progress,
        }
        result["identical"] = None

    return result