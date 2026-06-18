import os
import json
import lzma
import pickle
import math
import urllib.request
import urllib.parse
import time

def fetch_toll_links():
    """Mengambil data gerbang tol dan ramp dari Overpass API"""
    print("[1/4] Mengambil data jalan tol dari Overpass API...")
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = """
    [out:json][timeout:250];
    (
      way["highway"~"motorway_link|trunk_link|primary_link|secondary_link"](-8.8,105.0,-5.8,114.6);
    );
    out body;
    >;
    out skel qt;
    """
    
    # Encode sebagai form data (Content-Type: application/x-www-form-urlencoded)
    post_data = urllib.parse.urlencode({"data": overpass_query}).encode("utf-8")
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                overpass_url,
                data=post_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "LogisticsSimulator/1.0",
                }
            )
            with urllib.request.urlopen(req, timeout=300) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            print(f"  ⚠️ Percobaan {attempt}/{max_retries} gagal: HTTP {e.code} {e.reason}")
            if attempt < max_retries:
                wait = 10 * attempt
                print(f"  Menunggu {wait} detik sebelum mencoba lagi...")
                time.sleep(wait)
            else:
                raise
        except urllib.error.URLError as e:
            print(f"  ⚠️ Percobaan {attempt}/{max_retries} gagal: {e.reason}")
            if attempt < max_retries:
                wait = 10 * attempt
                print(f"  Menunggu {wait} detik sebelum mencoba lagi...")
                time.sleep(wait)
            else:
                raise

def haversine(lat1, lon1, lat2, lon2):
    """Menghitung jarak Haversine dalam meter"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def inject_to_graph(links_data):
    """Menyuntikkan data jalan tol ke dalam graf cache lzma"""
    cache_file = "graph_cache/jawa_offline_graph.pkl.xz"
    if not os.path.exists(cache_file):
        print("Cache graf tidak ditemukan.")
        return
        
    print("[2/4] Memuat cache graf original...")
    with lzma.open(cache_file, "rb") as f:
        data = pickle.load(f)
        
    custom_graph = data["custom_graph"]
    node_coords = data["node_coords"]
    
    print("[3/4] Memproses dan menginjeksi node & edge jalan tol...")
    added_nodes = 0
    added_edges = 0
    
    # Tambah node
    for el in links_data["elements"]:
        if el["type"] == "node":
            node_id = el["id"]
            node_coords[node_id] = {
                "lat": el["lat"],
                "lng": el["lon"],
                "is_its": False
            }
            if node_id not in custom_graph:
                custom_graph[node_id] = {}
            added_nodes += 1
            
    # Tambah jalan penghubung (edges)
    for el in links_data["elements"]:
        if el["type"] == "way":
            nodes = el["nodes"]
            oneway = el.get("tags", {}).get("oneway", "no") == "yes"
            for i in range(len(nodes) - 1):
                u, v = nodes[i], nodes[i+1]
                if u in node_coords and v in node_coords:
                    lat1, lon1 = node_coords[u]["lat"], node_coords[u]["lng"]
                    lat2, lon2 = node_coords[v]["lat"], node_coords[v]["lng"]
                    
                    dist = haversine(lat1, lon1, lat2, lon2)
                    weight = max(dist, 1.0) # Bobot dalam meter
                    
                    if u not in custom_graph: custom_graph[u] = {}
                    if v not in custom_graph: custom_graph[v] = {}
                    
                    custom_graph[u][v] = weight
                    added_edges += 1
                    if not oneway:
                        custom_graph[v][u] = weight
                        added_edges += 1
                        
    print(f"Berhasil menginjeksi {added_nodes} titik gerbang tol dan {added_edges} ruas jalan.")
    
    print("[4/4] Menyimpan ulang graf ke cache terkompresi...")
    data["custom_graph"] = custom_graph
    data["node_coords"] = node_coords
    with lzma.open(cache_file, "wb") as f:
        pickle.dump(data, f)
        
    print("Injeksi jalan tol Selesai! Silakan restart server.")

if __name__ == "__main__":
    links = fetch_toll_links()
    inject_to_graph(links)
