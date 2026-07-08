import csv

data = list(csv.DictReader(open(r'c:\Agentic Ai\BunningsDemo\data\bunnings_accessories.csv')))

for pid in ['300133', '300172', '300191', '300001', '300097']:
    items = [r for r in data if r['PRODUCT_ID'] == pid]
    name = items[0]['PRODUCT_NAME'][:55]
    print("=== Product", pid, "-", name)
    for r in items:
        acc_id   = r['ACCESSORY_ID']
        acc_name = r['ACCESSORY_NAME'][:55]
        acc_cat  = r['ACCESSORY_CATEGORY']
        acc_price = r['ACCESSORY_PRICE']
        print("  ", acc_id, "|", acc_name, "|", acc_cat, "|", acc_price)
    print()
