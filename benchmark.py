import time
import random
import csv
import sys
from pathlib import Path

# Fix seed for reproducibility
random.seed(42)

# Import functions from main.py
from main import download_and_process_graph, custom_dijkstra, FloydWarshallSolver

def extract_connected_subgraph(graph, start_node, target_size):
    """
    Ekstrak subgraph yang terhubung (connected) menggunakan BFS.
    """
    visited = set([start_node])
    queue = [start_node]
    
    while queue and len(visited) < target_size:
        curr = queue.pop(0)
        for nb in graph.get(curr, {}):
            if nb not in visited:
                visited.add(nb)
                queue.append(nb)
                if len(visited) >= target_size:
                    break

    subgraph = {}
    for u in visited:
        subgraph[u] = {}
        for v, w in graph.get(u, {}).items():
            if v in visited:
                subgraph[u][v] = w
                
    return subgraph

def run_benchmark():
    print("="*60)
    print(" LOGISTICS DISPATCH SIMULATOR - ALGORITHM BENCHMARK")
    print("="*60)
    print("Memuat graf utama dari cache...")
    graph_data = download_and_process_graph()
    full_graph = graph_data["custom_graph"]
    
    # Pilih satu node awal yang terhubung ke banyak node
    # Ambil node dari komponen utama (kita ambil acak tapi valid)
    all_nodes = list(full_graph.keys())
    
    # Cari start node yang punya tetangga cukup (menghindari pulau kecil terisolasi)
    start_node = None
    for n in all_nodes:
        if len(full_graph[n]) >= 3:
            start_node = n
            break

    # Sizes to benchmark: V = 100, 250, 500, 1000, 1500
    sizes = [100, 250, 500, 1000, 1500]
    num_pairs_dijkstra = 50  # Kita rata-rata dari 50 pasangan agar stabil
    
    results = []
    
    print("\nMemulai Benchmark (Dijkstra SSSP vs Floyd-Warshall APSP)...")
    print(f"{'V':<8} {'E':<8} {'Dijkstra (ms)':<15} {'FW (ms)':<15} {'Same Cost?':<12}")
    print("-" * 60)
    
    for V in sizes:
        subgraph = extract_connected_subgraph(full_graph, start_node, V)
        actual_V = len(subgraph)
        actual_E = sum(len(nb) for nb in subgraph.values()) // 2
        
        nodes_list = list(subgraph.keys())
        
        # 1. Test Floyd-Warshall (All Pairs)
        fw = FloydWarshallSolver()
        # FW berjalan secara synchronous di sini karena dipanggil langsung fungsinya
        t0_fw = time.perf_counter()
        fw._compute(subgraph)
        t1_fw = time.perf_counter()
        fw_time_ms = (t1_fw - t0_fw) * 1000
        
        # 2. Test Dijkstra (Single Pair, dirata-rata)
        dijkstra_total_time = 0
        same_cost_all = True
        
        for _ in range(num_pairs_dijkstra):
            src = random.choice(nodes_list)
            dst = random.choice(nodes_list)
            while src == dst:
                dst = random.choice(nodes_list)
                
            t0_d = time.perf_counter()
            d_path, d_cost = custom_dijkstra(subgraph, src, dst)
            t1_d = time.perf_counter()
            dijkstra_total_time += (t1_d - t0_d) * 1000
            
            # Cross-check dengan Floyd-Warshall
            src_idx = fw.node_to_idx[src]
            dst_idx = fw.node_to_idx[dst]
            fw_cost = fw.dist[src_idx][dst_idx]
            
            # Toleransi float error (0.1 meter)
            if d_cost == float('inf') and fw_cost == float('inf'):
                continue
            if abs(d_cost - fw_cost) > 0.1:
                same_cost_all = False
                
        dijkstra_avg_ms = dijkstra_total_time / num_pairs_dijkstra
        
        res = {
            "V": actual_V,
            "E": actual_E,
            "Dijkstra_Avg_ms": round(dijkstra_avg_ms, 3),
            "FW_Total_ms": round(fw_time_ms, 1),
            "Same_Cost": "Yes" if same_cost_all else "No"
        }
        results.append(res)
        
        print(f"{actual_V:<8} {actual_E:<8} {res['Dijkstra_Avg_ms']:<15.3f} {res['FW_Total_ms']:<15.1f} {res['Same_Cost']:<12}")
        
    # Write to CSV
    csv_file = "benchmark_results.csv"
    with open(csv_file, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["V", "E", "Dijkstra_Avg_ms", "FW_Total_ms", "Same_Cost"])
        writer.writeheader()
        writer.writerows(results)
        
    print("\nBenchmark selesai!")
    print(f"Data disimpan ke {csv_file}")
    print("Catatan: Dijkstra diukur sebagai rata-rata Single-Source Single-Pair (SSSP).")
    print("Catatan: Floyd-Warshall diukur sebagai total waktu All-Pairs Shortest Path (APSP).")

if __name__ == "__main__":
    run_benchmark()
