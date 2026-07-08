"""
load_meijer_data.py
Creates and loads all Meijer tables in SAP HANA:
  - SAP_MEIJER_PRODUCTS_V1   (with REAL_VECTOR embeddings)
  - SAP_MEIJER_CUSTOMERS_V1  (passwords hashed with pbkdf2:sha256)
  - SAP_MEIJER_CATEGORY_V1   (category hierarchy with PARENT_CATEGORY_ID)

Run: .\\venv\\Scripts\\python.exe load_meijer_data.py
"""

import csv
import os
import sys

from werkzeug.security import generate_password_hash

from agent import hana_connect
from ecom_llm import get_google_embedding

# ── Table names ────────────────────────────────────────────────────────────────
PRODUCTS_TABLE  = "SAP_MEIJER_PRODUCTS_V1"
CUSTOMERS_TABLE = "SAP_MEIJER_CUSTOMERS_V1"
CATEGORY_TABLE  = "SAP_MEIJER_CATEGORY_V1"

# ── CSV paths ──────────────────────────────────────────────────────────────────
PRODUCTS_CSV  = os.path.join("data", "Meijer_product.csv")
CUSTOMERS_CSV = os.path.join("data", "customer.csv")
CATEGORY_CSV  = os.path.join("data", "Meijer_category.csv")

# Default password assigned to all Meijer customers (no password column in CSV)
DEFAULT_PASSWORD = "Meijer@2025"


def drop_table(cursor, table_name):
    try:
        cursor.execute(f"DROP TABLE {table_name} CASCADE")
        print(f"  🗑️  Dropped existing table {table_name}")
    except Exception:
        print(f"  ℹ️  Table {table_name} does not exist yet – will create fresh")


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
            CATEGORY_ID        INTEGER        NOT NULL PRIMARY KEY,
            CATEGORY_NAME      NVARCHAR(200)  NOT NULL,
            PARENT_CATEGORY_ID INTEGER
        )
    """)
    print(f"  ✅ Table {CATEGORY_TABLE} created")

    rows = []
    with open(CATEGORY_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            cat_id  = r["CATEGORY_ID"].strip()
            name    = r["CATEGORY_NAME"].strip()
            parent  = r.get("PARENT_CATEGORY_ID", "").strip()

            if not cat_id or not name:
                continue

            rows.append((
                int(cat_id),
                name,
                int(parent) if parent else None,
            ))

    print(f"  📦 Inserting {len(rows)} categories ...")
    cursor.executemany(
        f"INSERT INTO {CATEGORY_TABLE} (CATEGORY_ID, CATEGORY_NAME, PARENT_CATEGORY_ID) VALUES (?,?,?)",
        rows
    )
    conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {CATEGORY_TABLE}")
    print(f"  ✅ Loaded {cursor.fetchone()[0]} rows into {CATEGORY_TABLE}")
    cursor.close()


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
            CUSTOMER_ID   NVARCHAR(100)  NOT NULL PRIMARY KEY,
            CUSTOMER_NAME NVARCHAR(100)  NOT NULL,
            PASSWORD_HASH NVARCHAR(256)  NOT NULL,
            GENDER        NVARCHAR(10),
            AGE           INTEGER,
            PHONE         NVARCHAR(30),
            CITY          NVARCHAR(60),
            INTEREST      NVARCHAR(200)
        )
    """)
    print(f"  ✅ Table {CUSTOMERS_TABLE} created")

    hashed_default = generate_password_hash(DEFAULT_PASSWORD)
    rows = []
    with open(CUSTOMERS_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            customer_id   = r.get("CUSTOMER_ID", "").strip()
            customer_name = r.get("CUSTOMER_NAME", "").strip()
            gender        = r.get("GENDER", "").strip()
            age_str       = r.get("AGE", "").strip()
            # PASSWORD column is optional – fall back to default
            password      = r.get("PASSWORD", "").strip()
            phone         = r.get("PHONE", "").strip()
            city          = r.get("CITY", "").strip()
            interest      = r.get("INTEREST", "").strip()

            if not customer_id or not customer_name:
                continue

            password_hash = generate_password_hash(password) if password else hashed_default

            try:
                age = int(age_str) if age_str else None
            except ValueError:
                age = None

            rows.append((
                customer_id,
                customer_name,
                password_hash,
                gender,
                age,
                phone,
                city,
                interest,
            ))

    print(f"  📦 Inserting {len(rows)} customers (default password: {DEFAULT_PASSWORD}) ...")
    cursor.executemany(
        f"INSERT INTO {CUSTOMERS_TABLE} VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {CUSTOMERS_TABLE}")
    print(f"  ✅ Loaded {cursor.fetchone()[0]} rows into {CUSTOMERS_TABLE}")
    cursor.close()


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
            BRAND           NVARCHAR(255),
            SUMMARY         NVARCHAR(5000),
            PRICE           DECIMAL(10,2),
            CATEGORY_IDS    NVARCHAR(1000),
            IMAGE_URL       NVARCHAR(1000),
            VECTOR_NAME     REAL_VECTOR(3072),
            VECTOR_SUMMARY  REAL_VECTOR(3072),
            VECTOR_CATEGORY REAL_VECTOR(3072)
        )
    """)
    print(f"  ✅ Table {PRODUCTS_TABLE} created")

    insert_sql = f"""
        INSERT INTO {PRODUCTS_TABLE}
            (PRODUCT_ID, PRODUCT_NAME, BRAND, SUMMARY, PRICE, CATEGORY_IDS, IMAGE_URL,
             VECTOR_NAME, VECTOR_SUMMARY, VECTOR_CATEGORY)
        VALUES (?, ?, ?, ?, ?, ?, ?, TO_REAL_VECTOR(?), TO_REAL_VECTOR(?), TO_REAL_VECTOR(?))
    """

    loaded = skipped = 0
    with open(PRODUCTS_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id   = row.get("PRODUCT_ID", "").strip()
            product_name = row.get("PRODUCT_NAME", "").strip()
            brand        = row.get("BRAND", "").strip()
            summary      = row.get("SUMMARY", "").strip()
            price_str    = row.get("PRICE", "0").strip()
            category_ids = row.get("CATEGORY_IDS", "").strip()
            image_url    = row.get("IMAGE_URL", "").strip()

            if not product_id or not product_name:
                skipped += 1
                continue

            try:
                price = float(price_str.replace("$", "").replace(",", ""))
            except ValueError:
                price = 0.0

            print(f"\n  📦 [{product_id}] {product_name[:60]}")

            # Build embedding inputs
            embed_name     = product_name
            embed_summary  = summary if summary else product_name
            embed_category = f"{category_ids} {brand}".strip() if category_ids else product_name

            vec_name     = get_google_embedding(embed_name)
            vec_summary  = get_google_embedding(embed_summary)
            vec_category = get_google_embedding(embed_category)

            if not vec_name or not vec_summary or not vec_category:
                print(f"  ⚠️  Embedding failed for {product_id} – skipping")
                skipped += 1
                continue

            try:
                cursor.execute(insert_sql, (
                    product_id, product_name, brand, summary, price,
                    category_ids, image_url,
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


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n🛒  Meijer HANA Data Loader")
    print("=" * 65)

    conn = hana_connect()
    if not conn:
        print("❌ Could not connect to HANA – aborting")
        sys.exit(1)

    load_category(conn)     # fast – no embeddings
    load_customers(conn)    # fast – no embeddings
    load_products(conn)     # last – most time-consuming (embeddings per product)

    conn.close()
    print(f"\n{'='*65}")
    print("🎉  All Meijer tables created and loaded successfully!")
    print("=" * 65)


if __name__ == "__main__":
    main()
