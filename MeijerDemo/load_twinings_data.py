"""
load_twinings_data.py
Creates and loads all Twinings tables in SAP HANA:
  - SAP_TWININGS_PRODUCTS_V1   (with REAL_VECTOR embeddings)
  - SAP_TWININGS_CUSTOMERS_V1  (passwords hashed with pbkdf2:sha256)
  - SAP_TWININGS_CROSSSELL_V1  (product relationships)
  - SAP_TWININGS_CATEGORY_V1   (category hierarchy)

Run: .\\venv\\Scripts\\python.exe load_twinings_data.py
"""

import csv
import os
import sys

from werkzeug.security import generate_password_hash

from agent import hana_connect
from ecom_llm import get_google_embedding

# ── Table names ────────────────────────────────────────────────────────────────
PRODUCTS_TABLE  = "SAP_TWININGS_PRODUCTS_V1"
CUSTOMERS_TABLE = "SAP_TWININGS_CUSTOMERS_V1"
CROSSSELL_TABLE = "SAP_TWININGS_CROSSSELL_V1"
CATEGORY_TABLE  = "SAP_TWININGS_CATEGORY_V1"

# ── CSV paths ──────────────────────────────────────────────────────────────────
PRODUCTS_CSV  = os.path.join("data", "twinings_products.csv")
CUSTOMERS_CSV = os.path.join("data", "twinings_customers.csv")
CROSSSELL_CSV = os.path.join("data", "twinings_crosssell.csv")
CATEGORY_CSV  = os.path.join("data", "twinings_category.csv")


def drop_table(cursor, table_name):
    try:
        cursor.execute(f"DROP TABLE {table_name} CASCADE")
        print(f"  🗑️  Dropped existing table {table_name}")
    except Exception:
        print(f"  ℹ️  Table {table_name} does not exist yet – will create fresh")


# ── Products ───────────────────────────────────────────────────────────────────

def load_products(conn):
    print(f"\n{'='*65}")
    print(f"📦  PRODUCTS  →  {PRODUCTS_TABLE}")
    print(f"{'='*65}")

    if not os.path.exists(PRODUCTS_CSV):
        print(f"❌ {PRODUCTS_CSV} not found – skipping")
        return

    cursor = conn.cursor()
    drop_table(cursor, PRODUCTS_TABLE)

    cursor.execute(f"""
        CREATE TABLE {PRODUCTS_TABLE} (
            PRODUCT_ID      NVARCHAR(50)   PRIMARY KEY,
            PRODUCT_NAME    NVARCHAR(500)  NOT NULL,
            SUMMARY         NVARCHAR(5000),
            PRICE           DECIMAL(10,2),
            CATEGORY_IDS    NVARCHAR(1000),
            IMAGE_URL       NVARCHAR(1000),
            BRAND           NVARCHAR(255),
            VECTOR_NAME     REAL_VECTOR(3072),
            VECTOR_SUMMARY  REAL_VECTOR(3072),
            VECTOR_CATEGORY REAL_VECTOR(3072)
        )
    """)
    print(f"  ✅ Table {PRODUCTS_TABLE} created")

    insert_sql = f"""
        INSERT INTO {PRODUCTS_TABLE}
            (PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDS, IMAGE_URL, BRAND,
             VECTOR_NAME, VECTOR_SUMMARY, VECTOR_CATEGORY)
        VALUES (?, ?, ?, ?, ?, ?, ?, TO_REAL_VECTOR(?), TO_REAL_VECTOR(?), TO_REAL_VECTOR(?))
    """

    loaded = skipped = 0
    with open(PRODUCTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id   = row.get("PRODUCT_ID", "").strip()
            product_name = row.get("PRODUCT_NAME", "").strip()
            summary      = row.get("SUMMARY", "").strip()
            price_str    = row.get("PRICE", "0").strip()
            category_ids = row.get("CATEGORY_IDS", "").strip()
            image_url    = row.get("IMAGE_URL", "").strip()
            brand        = row.get("BRAND", "").strip()

            if not product_id or not product_name:
                skipped += 1
                continue

            try:
                price = float(price_str.replace("£", "").replace(",", ""))
            except ValueError:
                price = 0.0

            print(f"\n  📦 [{product_id}] {product_name[:60]}")

            vec_name     = get_google_embedding(product_name)
            vec_summary  = get_google_embedding(summary if summary else product_name)
            vec_category = get_google_embedding(category_ids if category_ids else product_name)

            if not vec_name or not vec_summary or not vec_category:
                print(f"  ⚠️  Embedding failed for {product_id} – skipping")
                skipped += 1
                continue

            try:
                cursor.execute(insert_sql, (
                    product_id, product_name, summary, price,
                    category_ids, image_url, brand,
                    str(vec_name), str(vec_summary), str(vec_category),
                ))
                loaded += 1
                print(f"  ✅ Inserted")
            except Exception as e:
                print(f"  ❌ Insert failed: {e}")
                skipped += 1

    conn.commit()
    cursor.close()
    print(f"\n  📊 Products: loaded={loaded}, skipped={skipped}")


# ── Customers ──────────────────────────────────────────────────────────────────

def load_customers(conn):
    print(f"\n{'='*65}")
    print(f"👤  CUSTOMERS  →  {CUSTOMERS_TABLE}")
    print(f"{'='*65}")

    if not os.path.exists(CUSTOMERS_CSV):
        print(f"❌ {CUSTOMERS_CSV} not found – skipping")
        return

    cursor = conn.cursor()
    drop_table(cursor, CUSTOMERS_TABLE)

    cursor.execute(f"""
        CREATE TABLE {CUSTOMERS_TABLE} (
            CUSTOMER_ID   NVARCHAR(100) NOT NULL PRIMARY KEY,
            CUSTOMER_NAME NVARCHAR(100) NOT NULL,
            PASSWORD_HASH NVARCHAR(256) NOT NULL,
            GENDER        NVARCHAR(10),
            AGE           INTEGER,
            PHONE         NVARCHAR(30),
            CITY          NVARCHAR(60),
            INTEREST      NVARCHAR(200)
        )
    """)
    print(f"  ✅ Table {CUSTOMERS_TABLE} created")

    rows = []
    with open(CUSTOMERS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((
                r["CUSTOMER_ID"].strip(),
                r["CUSTOMER_NAME"].strip(),
                generate_password_hash(r["PASSWORD"]),
                r.get("GENDER", ""),
                int(r["AGE"]) if r.get("AGE") else None,
                r.get("PHONE", ""),
                r.get("CITY", ""),
                r.get("INTEREST", ""),
            ))

    print(f"  📦 Inserting {len(rows)} customers ...")
    cursor.executemany(
        f"INSERT INTO {CUSTOMERS_TABLE} VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {CUSTOMERS_TABLE}")
    print(f"  ✅ Loaded {cursor.fetchone()[0]} rows into {CUSTOMERS_TABLE}")
    cursor.close()


# ── Crosssell ──────────────────────────────────────────────────────────────────

def load_crosssell(conn):
    print(f"\n{'='*65}")
    print(f"🔗  CROSSSELL  →  {CROSSSELL_TABLE}")
    print(f"{'='*65}")

    if not os.path.exists(CROSSSELL_CSV):
        print(f"❌ {CROSSSELL_CSV} not found – skipping")
        return

    cursor = conn.cursor()
    drop_table(cursor, CROSSSELL_TABLE)

    cursor.execute(f"""
        CREATE TABLE {CROSSSELL_TABLE} (
            PRODUCT_ID         NVARCHAR(50)  NOT NULL,
            RELATED_PRODUCT_ID NVARCHAR(50)  NOT NULL,
            RELATION_TYPE      NVARCHAR(20)  NOT NULL,
            DISPLAY_ORDER      INTEGER       NOT NULL,
            PRIMARY KEY (PRODUCT_ID, RELATED_PRODUCT_ID, RELATION_TYPE)
        )
    """)
    print(f"  ✅ Table {CROSSSELL_TABLE} created")

    rows = []
    with open(CROSSSELL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((
                r["PRODUCT_ID"].strip(),
                r["RELATED_PRODUCT_ID"].strip(),
                r["RELATION_TYPE"].strip(),
                int(r["DISPLAY_ORDER"]),
            ))

    print(f"  📦 Inserting {len(rows):,} rows ...")
    cursor.executemany(
        f"INSERT INTO {CROSSSELL_TABLE} VALUES (?,?,?,?)",
        rows
    )
    conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {CROSSSELL_TABLE}")
    print(f"  ✅ Loaded {cursor.fetchone()[0]:,} rows into {CROSSSELL_TABLE}")

    cursor.execute(f"""
        SELECT RELATION_TYPE, COUNT(*) AS CNT
        FROM {CROSSSELL_TABLE}
        GROUP BY RELATION_TYPE
        ORDER BY CNT DESC
    """)
    print("  📊 Breakdown by relation type:")
    for relation_type, cnt in cursor.fetchall():
        print(f"     {relation_type:<12} → {cnt:>4} rows")

    cursor.close()


# ── Category ───────────────────────────────────────────────────────────────────

def load_category(conn):
    print(f"\n{'='*65}")
    print(f"🗂️   CATEGORY  →  {CATEGORY_TABLE}")
    print(f"{'='*65}")

    if not os.path.exists(CATEGORY_CSV):
        print(f"❌ {CATEGORY_CSV} not found – skipping")
        return

    cursor = conn.cursor()
    drop_table(cursor, CATEGORY_TABLE)

    cursor.execute(f"""
        CREATE TABLE {CATEGORY_TABLE} (
            CATEGORY_NAME NVARCHAR(200) NOT NULL,
            CATEGORY_ID   INTEGER       NOT NULL PRIMARY KEY
        )
    """)
    print(f"  ✅ Table {CATEGORY_TABLE} created")

    rows = []
    with open(CATEGORY_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((
                r["CATEGORY_NAME"].strip(),
                int(r["CATEGORY_ID"]),
            ))

    print(f"  📦 Inserting {len(rows)} categories ...")
    cursor.executemany(
        f"INSERT INTO {CATEGORY_TABLE} VALUES (?,?)",
        rows
    )
    conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {CATEGORY_TABLE}")
    print(f"  ✅ Loaded {cursor.fetchone()[0]} rows into {CATEGORY_TABLE}")
    cursor.close()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n🍵  Twinings HANA Data Loader")
    print("=" * 65)

    conn = hana_connect()
    if not conn:
        print("❌ Could not connect to HANA – aborting")
        sys.exit(1)

    load_category(conn)
    load_customers(conn)
    load_crosssell(conn)
    load_products(conn)   # last – most time-consuming (embeddings)

    conn.close()
    print(f"\n{'='*65}")
    print("🎉  All Twinings tables created and loaded successfully!")
    print("=" * 65)


if __name__ == "__main__":
    main()
