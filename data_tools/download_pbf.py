import urllib.request
import sys
import time

urls = [
    "https://download.geofabrik.de/asia/indonesia-latest.osm.pbf",
    "https://download.openstreetmap.fr/extracts/asia/indonesia.osm.pbf"
]
dest = "indonesia-latest.osm.pbf"

print("Downloading PBF Indonesia...")

success = False
for url in urls:
    print(f"Mencoba mendownload dari {url}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'LogisticsSimulator/1.0'})
    
    ctx = urllib.request.ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = urllib.request.ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            length = int(response.getheader('content-length', 0))
            downloaded = 0
            with open(dest, 'wb') as f:
                while True:
                    chunk = response.read(8192 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if length > 0:
                        pct = int((downloaded / length) * 100)
                        sys.stdout.write(f"\rProgress: {pct}% ({downloaded/(1024*1024):.1f} MB / {length/(1024*1024):.1f} MB)")
                    else:
                        sys.stdout.write(f"\rProgress: {downloaded/(1024*1024):.1f} MB")
                    sys.stdout.flush()
            print("\nDone")
            success = True
            break
    except Exception as e:
        print(f"\nGagal mendownload dari {url}: {e}")

if not success:
    print("\nSemua mirror gagal didownload.")
    sys.exit(1)
