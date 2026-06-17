import os
import urllib.request
import subprocess

def download_with_progress(url, dest_path):
    print(f"Mendownload {url}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'LogisticsSimulator/1.0'})
    
    ctx = urllib.request.ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = urllib.request.ssl.CERT_NONE
    
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

if __name__ == "__main__":
    url = "https://download.openstreetmap.fr/extracts/asia/indonesia-latest.osm.pbf"
    pbf_file = "indonesia-latest.osm.pbf"
    o5m_file = "indonesia.o5m"
    osm_filtered = "indonesia_highway_ferry.osm"

    # 1. Download
    if not os.path.exists(pbf_file) or os.path.getsize(pbf_file) < 1000000:
        download_with_progress(url, pbf_file)
    
    # 2. Convert to o5m
    if not os.path.exists(o5m_file):
        print("Konversi PBF ke o5m...")
        subprocess.run(["osmconvert.exe", pbf_file, f"-o={o5m_file}"], check=True)
        
    # Delete PBF to save space
    if os.path.exists(pbf_file):
        os.remove(pbf_file)
        print("PBF dihapus untuk menghemat ruang.")

    # 3. Filter
    print("Filtering jalan utama + feri...")
    subprocess.run([
        "osmfilter.exe", o5m_file,
        "--keep=highway=motorway =trunk =primary =secondary route=ferry",
        f"-o={osm_filtered}"
    ], check=True)
    
    # Delete o5m to save space
    if os.path.exists(o5m_file):
        os.remove(o5m_file)
        print("o5m dihapus untuk menghemat ruang.")

    print(f"SELESAI! File final siap: {osm_filtered} ({os.path.getsize(osm_filtered)/1024/1024:.1f} MB)")
