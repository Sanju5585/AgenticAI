"""
Generate crosssell_products.csv from bunnings_products.csv.
Rules:
  similar   - same broad category, different product, up to 6 per product
  crosssell - complementary category (drills→bits, phones→accessories, etc.), up to 4
  upsell    - same category, price >= 1.2x current product, up to 2
"""
import csv, random, os
from collections import defaultdict

INPUT  = os.path.join("data", "bunnings_products.csv")
OUTPUT = os.path.join("data", "crosssell_products.csv")

# ── load products ──────────────────────────────────────────────────────────────
products = {}
with open(INPUT, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        pid = row["PRODUCT_ID"].strip()
        cats = [c.strip() for c in row["CATEGORY_IDS"].split("|") if c.strip()]
        products[pid] = {
            "name": row["PRODUCT_NAME"],
            "price": float(row["PRICE"]) if row["PRICE"] else 0.0,
            "cats": cats,
            "top": cats[0] if cats else "Other",
        }

# ── group by top-level category ───────────────────────────────────────────────
by_top = defaultdict(list)
for pid, info in products.items():
    by_top[info["top"]].append(pid)

# ── complementary category map ────────────────────────────────────────────────
CROSSSELL_MAP = {
    "Tools":              ["Tool Accessories", "Drill Bits"],
    "Power Tools":        ["Tool Accessories", "Drill Bits"],
    "Drill Drivers":      ["Drill Bits", "Tool Accessories"],
    "Drill Bits":         ["Power Tools", "Tool Accessories"],
    "Tool Accessories":   ["Power Tools", "Tools"],
    "Welding & Soldering Irons": ["Tool Accessories"],
    "Lighting":           ["Accessories", "Indoor Living"],
    "PendantLights":      ["Accessories", "Lighting"],
    "Mobile Phones":      ["Accessories", "Electronics"],
    "Electronics":        ["Accessories", "Mobile Phones"],
    "Accessories":        ["Mobile Phones", "Electronics"],
    "Kitchen":            ["Kitchen Appliances", "Small Appliances"],
    "Kitchen Appliances": ["Small Appliances", "Kitchen"],
    "Small Appliances":   ["Kitchen Appliances", "Kitchen"],
    "Garden":             ["Plants", "Indoor Living"],
    "Plants":             ["Garden", "Indoor Living"],
    "BuildingHardware":   ["DoorHardware"],
    "DoorHardware":       ["BuildingHardware"],
    "Home Decor":         ["Indoor Living", "Candle Holders"],
    "Indoor Living":      ["Home Decor"],
}

# ── build crosssell pool per top-category ─────────────────────────────────────
crosssell_pool = {}
for top, comp_tops in CROSSSELL_MAP.items():
    pool = []
    for ct in comp_tops:
        pool.extend(by_top.get(ct, []))
    crosssell_pool[top] = pool

# ── generate pairs ─────────────────────────────────────────────────────────────
rows = []
for pid, info in products.items():
    top = info["top"]
    price = info["price"]
    order = 1

    # --- similar (same top category, up to 6) ---
    same_cat = [p for p in by_top[top] if p != pid]
    random.shuffle(same_cat)
    for related in same_cat[:6]:
        rows.append((pid, related, "similar", order))
        order += 1

    # --- crosssell (complementary category, up to 4) ---
    comp = [p for p in crosssell_pool.get(top, []) if p != pid]
    random.shuffle(comp)
    for related in comp[:4]:
        rows.append((pid, related, "crosssell", order))
        order += 1

    # --- upsell (same category, price ≥ 120% of current, up to 2) ---
    upsell_candidates = [
        p for p in same_cat
        if products[p]["price"] >= price * 1.2
    ]
    upsell_candidates.sort(key=lambda p: products[p]["price"])
    for related in upsell_candidates[:2]:
        rows.append((pid, related, "upsell", order))
        order += 1

# ── write CSV ─────────────────────────────────────────────────────────────────
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["PRODUCT_ID", "RELATED_PRODUCT_ID", "RELATION_TYPE", "DISPLAY_ORDER"])
    writer.writerows(rows)

print(f"✅  Written {len(rows):,} rows to {OUTPUT}")
print(f"    Unique source products: {len(set(r[0] for r in rows))}")
print(f"    Relation type counts:")
from collections import Counter
for rel, cnt in Counter(r[2] for r in rows).items():
    print(f"      {rel}: {cnt}")
