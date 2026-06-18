import urllib.request
import sys
import time

url = "https://download.geofabrik.de/asia/indonesia-latest.osm.pbf"
dest = "indonesia-latest.osm.pbf"

print("Downloading PBF Indonesia...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
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
except Exception as e:
    print(e)
