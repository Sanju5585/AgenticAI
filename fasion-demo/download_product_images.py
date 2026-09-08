"""
Download product images from Hybris using product codes from product.csv.
Images are saved to product_images/ folder as {product_id}.jpg
"""

import csv
import os
import requests
import urllib3
import time
from pathlib import Path

# Suppress SSL warnings (Hybris uses self-signed cert on localhost)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuration ──────────────────────────────────────────────────────────────
PRODUCT_CSV   = Path(__file__).parent / "data" / "product.csv"
OUTPUT_FOLDER = Path(__file__).parent / "product_images"
TIMEOUT       = 15          # seconds per request
RETRY_DELAY   = 2           # seconds between retries
MAX_RETRIES   = 2
# ──────────────────────────────────────────────────────────────────────────────


def read_products(csv_path: Path) -> list[dict]:
    """Return list of {product_id, image_url} dicts from product.csv."""
    products = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id = row.get("PRODUCT_ID", "").strip()
            image_url  = row.get("IMAGE_URL",  "").strip()
            if product_id and image_url:
                products.append({"product_id": product_id, "image_url": image_url})
    return products


def download_image(product_id: str, url: str, output_dir: Path) -> bool:
    """Download a single image and save it; returns True on success."""
    # Determine file extension from Content-Type or default to .jpg
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, verify=False, timeout=TIMEOUT, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "image/jpeg")
                ext = ".jpg"
                if "png" in content_type:
                    ext = ".png"
                elif "gif" in content_type:
                    ext = ".gif"
                elif "webp" in content_type:
                    ext = ".webp"

                file_path = output_dir / f"{product_id}{ext}"
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"  [OK]  {product_id}{ext}")
                return True
            elif response.status_code == 404:
                print(f"  [404] {product_id} — image not found on server")
                return False
            else:
                print(f"  [ERR] {product_id} — HTTP {response.status_code} (attempt {attempt})")
        except requests.exceptions.ConnectionError:
            print(f"  [ERR] {product_id} — cannot connect to Hybris (is it running?)")
            return False
        except requests.exceptions.Timeout:
            print(f"  [ERR] {product_id} — request timed out (attempt {attempt})")
        except Exception as e:
            print(f"  [ERR] {product_id} — {e}")
            return False

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    return False


def main():
    # Create output folder
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    print(f"Output folder : {OUTPUT_FOLDER}")
    print(f"Product CSV   : {PRODUCT_CSV}\n")

    products = read_products(PRODUCT_CSV)
    print(f"Found {len(products)} products in CSV\n")

    success_count = 0
    skip_count    = 0
    fail_count    = 0

    for i, p in enumerate(products, 1):
        product_id = p["product_id"]
        url        = p["image_url"]

        # Skip if already downloaded
        existing = list(OUTPUT_FOLDER.glob(f"{product_id}.*"))
        if existing:
            print(f"  [SKIP] {product_id} — already downloaded")
            skip_count += 1
            continue

        print(f"[{i}/{len(products)}] Downloading {product_id} ...")
        ok = download_image(product_id, url, OUTPUT_FOLDER)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*50}")
    print(f"Done!  Success: {success_count}  |  Skipped: {skip_count}  |  Failed: {fail_count}")
    print(f"Images saved to: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()
