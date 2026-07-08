import csv

SRC  = r"c:\Agentic Ai\BunningsDemo\data\bunnings_products.csv"
DEST = r"c:\Agentic Ai\BunningsDemo\data\bunnings_accessories.csv"

products = {p["PRODUCT_ID"]: p for p in csv.DictReader(open(SRC, encoding="utf-8"))}

def by_cat(keyword):
    return [p for p in products.values() if keyword in p["CATEGORY_IDS"]]

def pid(p): return p["PRODUCT_ID"]

def acc_row(main, acc):
    return [
        main["PRODUCT_ID"], main["PRODUCT_NAME"],
        acc["PRODUCT_ID"],  acc["PRODUCT_NAME"],
        acc["CATEGORY_IDS"].split("|")[-1],
        acc["PRICE"],       acc["IMAGE_URL"],
    ]

def get(ids):
    return [products[i] for i in ids if i in products]

# ── Main product pools ──────────────────────────────────────────────────────
pendant_lights = by_cat("Lighting|PendantLights")
dslr_cameras   = by_cat("Cameras|DSLR Cameras")
digital_cams   = by_cat("Cameras|Digital Cameras")
mobile_phones  = by_cat("Phones|Mobile Phones")
power_drills   = by_cat("Power Tools|Drills|Drill Drivers")

rows = []
seen = set()

def add(main, acc):
    key = (main["PRODUCT_ID"], acc["PRODUCT_ID"])
    if key not in seen:
        seen.add(key)
        rows.append(acc_row(main, acc))

# ── 1. MOBILE PHONES ───────────────────────────────────────────────────────
# Explicit accessory ID lists per phone type to avoid substring-match bugs
# USB-C cables: 300157, 300159
# Micro-USB cables: 300155 (3-in-1), 300156 (pure Micro-USB)
# Lightning cables: 300155 (3-in-1), 300160
# Chargers: 300158 (2-port worksite), 300164 (GaN 65W)
# Power banks: 300165 (wireless solar), 300166 (22.5W 20k), 300167 (mini 5k), 300168 (magsafe), 300169 (solar 10k), 300170 (slim 10k)
# Car holders: 300161 (windscreen), 300162 (air outlet)
# Screen protector: 300163 (Samsung Galaxy S25)

SAMSUNG_S25_PIDS = {"300099", "300112"}
SAMSUNG_PIDS     = {"300098","300099","300103","300106","300108","300110","300112"}
FLIP_PIDS        = {"300100"}

for phone in mobile_phones:
    _pid = pid(phone)
    if _pid in FLIP_PIDS:
        # Seniors flip - Micro-USB
        for a in get(["300155","300156","300158","300167","300161"]):
            add(phone, a)
    elif _pid in SAMSUNG_PIDS:
        # Samsung - USB-C
        acc_ids = ["300157","300159","300158","300164","300165","300166","300167","300168","300169","300170","300161","300162"]
        if _pid in SAMSUNG_S25_PIDS:
            acc_ids.append("300163")  # S25 screen protector
        for a in get(acc_ids):
            add(phone, a)
    else:
        # OPPO, Nokia, DOOGEE, Blackview, Iqu, Optus, Nubia - USB-C / 3-in-1
        for a in get(["300155","300157","300159","300158","300164","300165","300166","300167","300161","300162"]):
            add(phone, a)

# ── 2. DSLR / MIRRORLESS CAMERAS ──────────────────────────────────────────
# All camera accessories: 300147-300154
all_cam_acc = get(["300147","300148","300149","300150","300151","300152","300153","300154"])
for cam in dslr_cameras:
    for a in all_cam_acc:
        add(cam, a)

# ── 3. DIGITAL / ACTION / BODY CAMERAS ────────────────────────────────────
# Battery, card reader, tripod, SD card, photo frame
dig_cam_acc = get(["300147","300148","300150","300152","300154"])
for cam in digital_cams:
    for a in dig_cam_acc:
        add(cam, a)

# ── 4. POWER TOOLS / DRILL DRIVERS ────────────────────────────────────────
RYOBI_BITS   = ["300215","300216","300220"]
DEWALT_BITS  = ["300217"]
MAKITA_BITS  = ["300222"]
GENERIC_BITS = ["300218","300219","300221"]

for tool in power_drills:
    _name = tool["PRODUCT_NAME"]
    if "Ryobi" in _name:
        assigned = RYOBI_BITS + GENERIC_BITS
    elif "DeWALT" in _name:
        assigned = DEWALT_BITS + GENERIC_BITS
    elif "Makita" in _name:
        assigned = MAKITA_BITS + GENERIC_BITS
    else:
        assigned = GENERIC_BITS
    for a in get(assigned):
        add(tool, a)

# ── 5. LIGHTING PENDANTS ──────────────────────────────────────────────────
lighting_acc = get(["300008"])
for light in pendant_lights:
    for a in lighting_acc:
        add(light, a)

# ── Write ──────────────────────────────────────────────────────────────────
header = ["PRODUCT_ID","PRODUCT_NAME","ACCESSORY_ID","ACCESSORY_NAME",
          "ACCESSORY_CATEGORY","ACCESSORY_PRICE","ACCESSORY_IMAGE"]
with open(DEST, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([header] + rows)

mob_pids   = set(pid(p) for p in mobile_phones)
dslr_pids  = set(pid(p) for p in dslr_cameras)
dig_pids   = set(pid(p) for p in digital_cams)
drill_pids = set(pid(p) for p in power_drills)
light_pids = set(pid(p) for p in pendant_lights)

print(f"bunnings_accessories.csv  --  {len(rows)} rows  |  {len(set(r[0] for r in rows))} products")
print()
print(f"  Mobile Phones  ({len(mobile_phones)} products): {len([r for r in rows if r[0] in mob_pids])} rows")
print(f"  DSLR Cameras   ({len(dslr_cameras)} products): {len([r for r in rows if r[0] in dslr_pids])} rows")
print(f"  Digital Cameras({len(digital_cams)} products): {len([r for r in rows if r[0] in dig_pids])} rows")
print(f"  Power Drills   ({len(power_drills)} products): {len([r for r in rows if r[0] in drill_pids])} rows")
print(f"  Pendant Lights ({len(pendant_lights)} products): {len([r for r in rows if r[0] in light_pids])} rows")
