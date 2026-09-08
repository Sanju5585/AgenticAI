from modules.outfit_builder_a2ui import get_outfit_looks, detect_category
from agent import hana_connect

conn = hana_connect()
cursor = conn.cursor()

# Test jacket
sections = get_outfit_looks('97602', 'Leather Jacket', cursor)
print(f'Jacket -> {len(sections)} sections')
for s in sections:
    label = s['complement_label']
    prio  = s['priority']
    prods = s['products']
    print(f'  [{prio}] {label}: {len(prods)} products')
    for p in prods:
        print(f'    - {p["product_id"]} | {p["product_name"]} | GBP {p["final_price"]:.2f}')

print()

# Test tshirt
sections2 = get_outfit_looks('300147490', 'T-Shirt Men Playboard Skull SS black S', cursor)
print(f'T-Shirt -> {len(sections2)} sections')
for s in sections2:
    print(f'  [{s["priority"]}] {s["complement_label"]}: {len(s["products"])} products')

print()

# Test dress
sections3 = get_outfit_looks('300610923', 'Strybal Dress Women black L', cursor)
print(f'Dress -> {len(sections3)} sections')
for s in sections3:
    print(f'  [{s["priority"]}] {s["complement_label"]}: {len(s["products"])} products')

cursor.close()
conn.close()
print('DONE')
