import os
import sys
import urllib.request
import subprocess

# Cross-platform tool names
OSMCONVERT = os.path.join("data_tools", "osmconvert.exe") if sys.platform == "win32" else "osmconvert"
OSMFILTER = os.path.join("data_tools", "osmfilter.exe") if sys.platform == "win32" else "osmfilter"

def download_with_progress(urls, dest_path):
    if isinstance(urls, str):
        urls = [urls]
        
    for url in urls:
        print(f"Mencoba mendownload dari {url}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'LogisticsSimulator/1.0'})
        
        ctx = urllib.request.ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = urllib.request.ssl.CERT_NONE
        
        try:
            with urllib.request.urlopen(req, context=ctx) as response:
                total_size = int(response.getheader('content-length', 0))
                downloaded = 0
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024) if hasattr(response, 'iter_content') else iter(lambda: response.read(1024*1024), b''):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            print(f"\rProgress: {percent}% ({downloaded/(1024*1024):.1f} MB / {total_size/(1024*1024):.1f} MB)", end="")
                print("\nDownload selesai.")
                return # Berhasil
        except Exception as e:
            print(f"\nGagal mendownload dari {url}: {e}")
            continue
            
    print("\nSemua mirror gagal. Proses dihentikan.")
    sys.exit(1)

if __name__ == "__main__":
    urls = [
        "https://download.geofabrik.de/asia/indonesia-latest.osm.pbf",
        "https://download.openstreetmap.fr/extracts/asia/indonesia.osm.pbf"
    ]
    # Simpan semua file di data_tools/ agar sesuai dengan path yang diharapkan main.py
    os.makedirs("data_tools", exist_ok=True)
    pbf_file = "data_tools/indonesia-latest.osm.pbf"
    o5m_file = "data_tools/indonesia.o5m"
    osm_filtered = "data_tools/indonesia_optimized.osm"

    # 1. Download
    if not os.path.exists(pbf_file) or os.path.getsize(pbf_file) < 1000000:
        download_with_progress(urls, pbf_file)
    
    # 2. Convert to o5m
    if not os.path.exists(o5m_file):
        print("Konversi PBF ke o5m...")
        subprocess.run([OSMCONVERT, pbf_file, f"-o={o5m_file}"], check=True)
        
    # Delete PBF to save space
    if os.path.exists(pbf_file):
        os.remove(pbf_file)
        print("PBF dihapus untuk menghemat ruang.")

    # 3. Filter — seluruh Indonesia (tanpa crop bounding box)
    print("Filtering jalan utama, provinsi, kabupaten & desa di Seluruh Indonesia...")
    subprocess.run([
        OSMFILTER, o5m_file,
        "--keep=highway=motorway =trunk =primary =secondary =tertiary =unclassified route=ferry",
        f"-o={osm_filtered}"
    ], check=True)
    
    # Delete o5m to save space
    if os.path.exists(o5m_file):
        os.remove(o5m_file)
        print("o5m dihapus untuk menghemat ruang.")

    print(f"SELESAI! File final siap: {osm_filtered} ({os.path.getsize(osm_filtered)/1024/1024:.1f} MB)")
