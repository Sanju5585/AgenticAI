"""
Update IMAGE_URL column in product.csv to use local static images.
Rows where a matching image exists in static/product_images/ get updated;
rows without a local image keep their original URL.
"""

import csv
import os
from pathlib import Path

PRODUCT_CSV   = Path(__file__).parent / "data" / "product.csv"
IMAGES_DIR    = Path(__file__).parent / "static" / "product_images"
URL_PREFIX    = "/static/product_images"

def main():
    # Read existing CSV (preserve encoding and whitespace in values)
    with open(PRODUCT_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows   = list(reader)

    # Find IMAGE_URL and PRODUCT_ID column indices
    col_names    = [h.strip() for h in header]
    id_col_idx   = col_names.index("PRODUCT_ID")
    url_col_idx  = col_names.index("IMAGE_URL")

    updated = 0
    kept    = 0

    for row in rows:
        if len(row) <= max(id_col_idx, url_col_idx):
            continue
        product_id = row[id_col_idx].strip()
        # Check for any extension (jpg, png, gif, webp)
        matches = list(IMAGES_DIR.glob(f"{product_id}.*"))
        if matches:
            filename = matches[0].name
            row[url_col_idx] = f"{URL_PREFIX}/{filename}"
            updated += 1
        else:
            kept += 1

    # Write back — keep original quoting style
    with open(PRODUCT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Updated : {updated} rows → /static/product_images/<id>.jpg")
    print(f"Kept    : {kept} rows  (no local image found)")
    print(f"Saved   : {PRODUCT_CSV}")

if __name__ == "__main__":
    main()
