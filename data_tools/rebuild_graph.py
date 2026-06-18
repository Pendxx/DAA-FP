import os
import urllib.request
import subprocess
import time
from main import download_and_process_graph, CACHE_FILE
import lzma
import pickle

def download_with_progress(url, dest_path):
    print(f"Mendownload {url}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    with urllib.request.urlopen(req) as response:
        total_size = int(response.getheader('content-length', 0))
        downloaded = 0
        with open(dest_path, 'wb') as f:
            for chunk in iter(lambda: response.read(4096*1024), b''):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = int((downloaded / total_size) * 100)
                    print(f"\rProgress: {percent}% ({downloaded/(1024*1024):.1f} MB / {total_size/(1024*1024):.1f} MB)", end="", flush=True)
                else:
                    print(f"\rDownloaded {downloaded/(1024*1024):.1f} MB", end="", flush=True)
    print("\nDownload selesai.")

if __name__ == "__main__":
    url = "http://download.openstreetmap.fr/extracts/asia/indonesia-latest.osm.pbf"
    pbf_file = "indonesia-latest.osm.pbf"
    o5m_file = "jawa.o5m"
    osm_filtered = "jawa_highway_ferry.osm"

    # 1. Download
    if not os.path.exists(pbf_file) or os.path.getsize(pbf_file) < 1000000:
        download_with_progress(url, pbf_file)
    
    # 2. Convert to o5m + crop to Java!
    if not os.path.exists(o5m_file):
        print("Konversi PBF ke o5m dan memotong ke koordinat Pulau Jawa...")
        subprocess.run(["osmconvert.exe", pbf_file, "-b=105.0,-8.9,114.6,-5.8", f"-o={o5m_file}"], check=True)

    # 3. Filter with ALL links!
    print("Filtering jalan utama + ramp tol + feri...")
    subprocess.run([
        "osmfilter.exe", o5m_file,
        "--keep=highway=motorway =motorway_link =trunk =trunk_link =primary =primary_link =secondary =secondary_link route=ferry",
        f"-o={osm_filtered}"
    ], check=True)
    
    # Remove old cache
    cache_xz = CACHE_FILE.with_suffix(".pkl.xz")
    if cache_xz.exists():
        os.remove(cache_xz)
    if CACHE_FILE.exists():
        os.remove(CACHE_FILE)

    print("Parsing XML dan membangun Graf...")
    data = download_and_process_graph()
    
    print("Memampatkan cache ke LZMA...")
    with lzma.open(cache_xz, "wb") as f:
        pickle.dump(data, f)
        
    print("Membersihkan file sampah...")
    for f in [pbf_file, o5m_file, osm_filtered, CACHE_FILE]:
        if os.path.exists(f):
            os.remove(f)
            
    print("REBUILD SELESAI!")
