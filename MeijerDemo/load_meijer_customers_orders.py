"""
load_meijer_customers_orders.py
Creates and loads:
  - SAP_MEIJER_CUSTOMERS_V1  (with INTEREST column for personalisation)
  - SAP_MEIJER_ORDERS_V1     (order history with line items)

Run: .\\venv\\Scripts\\python.exe load_meijer_customers_orders.py
"""

import csv
import os
import sys
from datetime import datetime

from werkzeug.security import generate_password_hash
from agent import hana_connect

CUSTOMERS_TABLE = "SAP_MEIJER_CUSTOMERS_V1"
ORDERS_TABLE    = "SAP_MEIJER_ORDERS_V1"

CUSTOMERS_CSV   = os.path.join("data", "Meijer_customers.csv")
ORDERS_CSV      = os.path.join("data", "Meijer_orders.csv")


def drop_table(cursor, table_name):
    try:
        cursor.execute(f"DROP TABLE {table_name} CASCADE")
        print(f"  🗑️  Dropped existing table {table_name}")
    except Exception:
        print(f"  ℹ️  Table {table_name} does not exist yet – will create fresh")


# ── Customers ─────────────────────────────────────────────────────────────────

def load_customers(conn):
    print(f"\n{'='*65}")
    print(f"👤  CUSTOMERS  →  {CUSTOMERS_TABLE}")
    print(f"{'='*65}")

    if not os.path.exists(CUSTOMERS_CSV):
        print(f"❌ {CUSTOMERS_CSV} not found – aborting")
        return False

    cursor = conn.cursor()
    drop_table(cursor, CUSTOMERS_TABLE)

    cursor.execute(f"""
        CREATE TABLE {CUSTOMERS_TABLE} (
            CUSTOMER_ID   NVARCHAR(100)  NOT NULL PRIMARY KEY,
            CUSTOMER_NAME NVARCHAR(100)  NOT NULL,
            PASSWORD_HASH NVARCHAR(256)  NOT NULL,
            GENDER        NVARCHAR(10),
            AGE           INTEGER,
            PHONE         NVARCHAR(30),
            CITY          NVARCHAR(60),
            INTEREST      NVARCHAR(500)
        )
    """)
    print(f"  ✅ Table {CUSTOMERS_TABLE} created")

    rows = []
    with open(CUSTOMERS_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            cid  = r["CUSTOMER_ID"].strip()
            name = r["CUSTOMER_NAME"].strip()
            pwd  = r.get("PASSWORD", "Meijer@2025").strip() or "Meijer@2025"
            if not cid or not name:
                continue
            rows.append((
                cid,
                name,
                generate_password_hash(pwd),
                r.get("GENDER", "").strip(),
                int(r["AGE"]) if r.get("AGE", "").strip() else None,
                r.get("PHONE", "").strip(),
                r.get("CITY", "").strip(),
                r.get("INTEREST", "").strip(),
            ))

    print(f"  📦 Inserting {len(rows)} customers ...")
    cursor.executemany(
        f"INSERT INTO {CUSTOMERS_TABLE} VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {CUSTOMERS_TABLE}")
    print(f"  ✅ Loaded {cursor.fetchone()[0]} rows into {CUSTOMERS_TABLE}")

    print("\n  📋 Customer summary:")
    cursor.execute(f"SELECT CUSTOMER_ID, CUSTOMER_NAME, CITY, INTEREST FROM {CUSTOMERS_TABLE} ORDER BY CUSTOMER_NAME")
    for row in cursor.fetchall():
        print(f"     {row[1]:<22} | {row[2]:<14} | {row[0]}")

    cursor.close()
    return True


# ── Orders ────────────────────────────────────────────────────────────────────

def load_orders(conn):
    print(f"\n{'='*65}")
    print(f"🛒  ORDERS  →  {ORDERS_TABLE}")
    print(f"{'='*65}")

    if not os.path.exists(ORDERS_CSV):
        print(f"❌ {ORDERS_CSV} not found – aborting")
        return False

    cursor = conn.cursor()
    drop_table(cursor, ORDERS_TABLE)

    cursor.execute(f"""
        CREATE TABLE {ORDERS_TABLE} (
            ORDER_ID      NVARCHAR(50)    NOT NULL,
            LINE_ITEM_ID  INTEGER         NOT NULL,
            CUSTOMER_ID   NVARCHAR(100)   NOT NULL,
            PRODUCT_ID    NVARCHAR(50)    NOT NULL,
            PRODUCT_NAME  NVARCHAR(500),
            QUANTITY      INTEGER         DEFAULT 1,
            UNIT_PRICE    DECIMAL(10,2),
            LINE_TOTAL    DECIMAL(10,2),
            ORDER_STATUS  NVARCHAR(30)    DEFAULT 'OPEN',
            ORDER_DATE    DATE,
            IMAGE_URL     NVARCHAR(1000),
            PRIMARY KEY (ORDER_ID, LINE_ITEM_ID)
        )
    """)
    print(f"  ✅ Table {ORDERS_TABLE} created")

    rows = []
    skipped = 0
    with open(ORDERS_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                order_date = datetime.strptime(
                    r["ORDER_DATE"].strip(), "%Y-%m-%d"
                ).date()
                rows.append((
                    r["ORDER_ID"].strip(),
                    int(r["LINE_ITEM_ID"]),
                    r["CUSTOMER_ID"].strip(),
                    r["PRODUCT_ID"].strip(),
                    r["PRODUCT_NAME"].strip(),
                    int(r.get("QUANTITY", 1)),
                    float(r["UNIT_PRICE"]),
                    float(r["LINE_TOTAL"]),
                    r.get("ORDER_STATUS", "OPEN").strip(),
                    order_date,
                    r.get("IMAGE_URL", "").strip(),
                ))
            except (KeyError, ValueError) as e:
                print(f"  ⚠️  Skipping bad row {r.get('ORDER_ID','?')}: {e}")
                skipped += 1

    print(f"  📦 Inserting {len(rows):,} order line items ...")
    cursor.executemany(
        f"""INSERT INTO {ORDERS_TABLE}
            (ORDER_ID, LINE_ITEM_ID, CUSTOMER_ID, PRODUCT_ID, PRODUCT_NAME,
             QUANTITY, UNIT_PRICE, LINE_TOTAL, ORDER_STATUS, ORDER_DATE, IMAGE_URL)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        rows
    )
    conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {ORDERS_TABLE}")
    print(f"  ✅ Loaded {cursor.fetchone()[0]:,} rows into {ORDERS_TABLE}")
    if skipped:
        print(f"  ⚠️  Skipped {skipped} bad rows")

    # Summary by status
    cursor.execute(f"""
        SELECT ORDER_STATUS, COUNT(DISTINCT ORDER_ID) AS ORDERS
        FROM {ORDERS_TABLE}
        GROUP BY ORDER_STATUS ORDER BY ORDERS DESC
    """)
    print("  📊 Orders by status:")
    for status, cnt in cursor.fetchall():
        print(f"     {status:<15} → {cnt} orders")

    # Summary by customer
    cursor.execute(f"""
        SELECT CUSTOMER_ID, COUNT(DISTINCT ORDER_ID) AS ORDERS, SUM(LINE_TOTAL) AS TOTAL
        FROM {ORDERS_TABLE}
        GROUP BY CUSTOMER_ID ORDER BY ORDERS DESC
    """)
    print("  📊 Orders by customer:")
    for cid, cnt, total in cursor.fetchall():
        print(f"     {cid:<40} → {cnt} orders  ${float(total or 0):.2f}")

    cursor.close()
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n🛒  Meijer Customers & Orders Loader")
    print("=" * 65)

    conn = hana_connect()
    if not conn:
        print("❌ Could not connect to HANA – aborting")
        sys.exit(1)

    ok1 = load_customers(conn)
    ok2 = load_orders(conn)

    conn.close()

    print(f"\n{'='*65}")
    if ok1 and ok2:
        print("🎉  Both tables created and loaded successfully!")
        print(f"\n  Credentials (all passwords = Meijer@2025):")
        print(f"  emily.carter@gmail.com")
        print(f"  james.anderson@gmail.com")
        print(f"  sarah.thompson@yahoo.com")
        print(f"  michael.brown@gmail.com")
        print(f"  jessica.wilson@gmail.com")
        print(f"  david.martinez@outlook.com")
        print(f"  ashley.johnson@gmail.com")
        print(f"  ryan.davis@gmail.com")
    else:
        print("⚠️  Some tables may not have loaded – check errors above.")
    print("=" * 65)


if __name__ == "__main__":
    main()
