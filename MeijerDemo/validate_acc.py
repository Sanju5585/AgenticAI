import csv

data = list(csv.DictReader(open(r'c:\Agentic Ai\BunningsDemo\data\bunnings_accessories.csv')))

checks = [
    ('300099', 'Samsung S25 Ultra'),
    ('300100', 'Aspera FLIP'),
    ('300097', 'OPPO A58'),
    ('300056', 'DeWALT Drill'),
    ('300053', 'Ryobi Drill'),
    ('300061', 'Makita Drill'),
    ('300133', 'Canon DSLR'),
    ('300139', 'Digital Camera'),
    ('300001', 'Pendant Light'),
]

for chk_pid, label in checks:
    items = [r for r in data if r['PRODUCT_ID'] == chk_pid]
    print('===', chk_pid, label)
    for r in items:
        a_id   = r['ACCESSORY_ID']
        a_name = r['ACCESSORY_NAME'][:52]
        a_cat  = r['ACCESSORY_CATEGORY']
        print(' ', a_id, '|', a_name, '|', a_cat)
    print()
