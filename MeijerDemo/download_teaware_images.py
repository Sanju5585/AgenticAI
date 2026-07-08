"""
Download Twinings Teaware & Tea Accessories images from twinings.co.uk
Save as TW100.jpeg ... TW114.jpeg in static/twinings_images/
"""

import requests, os, time, re
from pathlib import Path

DEST = Path(r"c:\Agentic Ai\TwningDemo\static\twinings_images")
DEST.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}

# Map: filename → keywords ALL must appear in product title (case-insensitive)
PRODUCT_MAP = {
    "TW100": ["stainless steel tea strainer"],
    "TW101": ["twinings tea tidy"],
    "TW102": ["loose tea scoop"],
    "TW103": ["birdhouse tea infuser"],
    "TW104": ["matcha bamboo whisk"],
    "TW105": ["matcha bowl"],
    "TW106": ["matcha bamboo spoon"],
    "TW107": ["over ice tea shaker"],
    "TW108": ["majorelle hare tea infuser"],
    "TW109": ["pack of 3 pocket tins"],
    "TW110": ["pack of 2 pocket tins", "mixed"],
    "TW111": ["pack of 2 pocket tins", "pink"],
    "TW112": ["fruitful selection gift bag"],
    "TW113": ["small white gift bag"],
    "TW114": ["twinings tea caddy"],
}

def fetch_all_products():
    products = []
    for page in range(1, 5):
        r = requests.get(
            f"https://www.twinings.co.uk/products.json?limit=250&page={page}",
            headers=HEADERS, timeout=30
        )
        r.raise_for_status()
        batch = r.json().get("products", [])
        if not batch:
            break
        products.extend(batch)
        print(f"  Page {page}: {len(batch)} products (total: {len(products)})")
        if len(batch) < 250:
            break
        time.sleep(0.4)
    return products

print("Fetching Twinings product catalogue...")
all_products = fetch_all_products()
print(f"Total: {len(all_products)} products\n")

def best_image_url(product):
    imgs = product.get("images", [])
    if not imgs:
        return None
    src = imgs[0]["src"]
    src = re.sub(r'_\d+x\d+(?=\.\w)', '', src)
    return src

def find_best_match(keywords, products):
    kws = [k.lower() for k in keywords]

    # Pass 1: all keywords must match
    for p in products:
        t = p["title"].lower()
        if all(k in t for k in kws):
            img = best_image_url(p)
            if img:
                return img, p["title"]

    # Pass 2: first two keywords
    if len(kws) >= 2:
        for p in products:
            t = p["title"].lower()
            if kws[0] in t and kws[1] in t:
                img = best_image_url(p)
                if img:
                    return img, p["title"]

    # Pass 3: first keyword only
    for p in products:
        t = p["title"].lower()
        if kws[0] in t:
            img = best_image_url(p)
            if img:
                return img, p["title"]

    return None, None

def download_image(url, dest_path):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)
    return len(r.content)

print("Downloading Teaware & Tea Accessories images...")
ok = 0
fail = 0
not_found = []

for code, keywords in PRODUCT_MAP.items():
    dest = DEST / f"{code}.jpeg"
    img_url, matched_title = find_best_match(keywords, all_products)

    if img_url:
        try:
            size = download_image(img_url, dest)
            kb = size // 1024
            print(f"  ✅ {code} — '{matched_title}' ({kb}KB)")
            ok += 1
        except Exception as e:
            print(f"  ❌ {code} — download error: {e}")
            fail += 1
            not_found.append(code)
    else:
        print(f"  ❌ {code} — NOT FOUND (keywords: {keywords})")
        fail += 1
        not_found.append(code)

    time.sleep(0.2)

print(f"\n{'='*58}")
print(f"✅ Downloaded: {ok}/{ok+fail}")
if fail == 0:
    print("🎉 All Teaware images downloaded successfully!")
else:
    print(f"⚠️  {fail} image(s) not found: {not_found}")

print("\nFiles saved:")
for code in PRODUCT_MAP:
    f = DEST / f"{code}.jpeg"
    if f.exists():
        print(f"  {code}.jpeg ({f.stat().st_size // 1024}KB)")
    else:
        print(f"  {code}.jpeg — MISSING")
