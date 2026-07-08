import sqlite3

# Connect to database
conn = sqlite3.connect('data/sap_commerce.db')
cursor = conn.cursor()

# List all tables
print("=" * 60)
print("AVAILABLE TABLES:")
print("=" * 60)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for t in tables:
    print(f"  - {t[0]}")

print("\n" + "=" * 60)
print("ORDER TABLE STRUCTURE:")
print("=" * 60)

# Check order table structure (try different possible names)
possible_names = ['SAP_ORDERS_COMMERCE_2211_V2', 'ORDERS', 'ORDER', 'SAP_ORDERS']
order_table = None

for name in possible_names:
    try:
        cursor.execute(f"PRAGMA table_info({name})")
        columns = cursor.fetchall()
        if columns:
            order_table = name
            print(f"\nFound table: {name}")
            print("\nColumns:")
            for col in columns:
                print(f"  {col[1]:25s} {col[2]}")
            break
    except:
        continue

if order_table:
    print("\n" + "=" * 60)
    print(f"ORDERS FOR aayushigupta@gmail.com:")
    print("=" * 60)
    
    # Get column names
    cursor.execute(f"PRAGMA table_info({order_table})")
    columns = cursor.fetchall()
    col_names = [col[1] for col in columns]
    
    print(f"\nColumn names: {col_names}")
    
    # Try to find orders
    cursor.execute(f"SELECT * FROM {order_table} WHERE CUSTOMER_ID = ? LIMIT 5", ('aayushigupta@gmail.com',))
    orders = cursor.fetchall()
    
    print(f"\nFound {len(orders)} orders:")
    for i, order in enumerate(orders, 1):
        print(f"\nOrder {i}:")
        for col_name, value in zip(col_names, order):
            print(f"  {col_name:25s}: {value}")

conn.close()
