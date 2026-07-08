# load_bunnings_products.py
# Loads bunnings_products.csv -> SAP_BUNNINGS_PRODUCTS_V1  (with embeddings)
# Loads bunnings_accessories.csv -> SAP_BUNNINGS_ACCESSORIES_V1 (no embeddings – mapping table)
#
# Follows the same conventions as load_electronic_products_v2.py:
#   - Google gemini-embedding-001 via v1beta API
#   - REAL_VECTOR(3072) columns
#   - hdbcli connection

import csv
import os
from hdbcli import dbapi
from dotenv import load_dotenv
from ecom_llm import get_google_embedding

load_dotenv()

# ── HANA connection ────────────────────────────────────────────────────────────
HANA_ADDRESS  = '794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com'
HANA_PORT     = 443
HANA_USER     = '00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT'
HANA_PASSWORD = 'Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.'

PRODUCTS_TABLE    = 'SAP_BUNNINGS_PRODUCTS_V1'
ACCESSORIES_TABLE = 'SAP_BUNNINGS_ACCESSORIES_V1'


def connect_to_hana():
    try:
        conn = dbapi.connect(
            address=HANA_ADDRESS,
            port=HANA_PORT,
            user=HANA_USER,
            password=HANA_PASSWORD,
            encrypt=True,
            sslValidateCertificate=False,
        )
        print('✅ Connected to HANA database')
        return conn
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        return None


def drop_table(cursor, table_name):
    try:
        cursor.execute(f'DROP TABLE {table_name}')
        print(f'🗑️  Dropped existing table {table_name}')
    except Exception:
        print(f'ℹ️  Table {table_name} does not exist yet – will create fresh')


# ── Products ───────────────────────────────────────────────────────────────────

def create_products_table(cursor):
    """
    SAP_BUNNINGS_PRODUCTS_V1
    Mirrors bunnings_products.csv columns plus three REAL_VECTOR(3072) columns:
      VECTOR_NAME     – embedding of PRODUCT_NAME
      VECTOR_SUMMARY  – embedding of SUMMARY
      VECTOR_CATEGORY – embedding of CATEGORY_IDS  (enables category-level similarity search)
    """
    drop_table(cursor, PRODUCTS_TABLE)

    ddl = f"""
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
    """
    cursor.execute(ddl)
    print(f'✅ Table {PRODUCTS_TABLE} created (REAL_VECTOR 3072 dimensions)')


def load_products(cursor, csv_path):
    create_products_table(cursor)

    insert_sql = f"""
    INSERT INTO {PRODUCTS_TABLE}
        (PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDS, IMAGE_URL, BRAND,
         VECTOR_NAME, VECTOR_SUMMARY, VECTOR_CATEGORY)
    VALUES (?, ?, ?, ?, ?, ?, ?, TO_REAL_VECTOR(?), TO_REAL_VECTOR(?), TO_REAL_VECTOR(?))
    """

    loaded = skipped = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id   = row.get('PRODUCT_ID', '').strip()
            product_name = row.get('PRODUCT_NAME', '').strip()
            summary      = row.get('SUMMARY', '').strip()
            price_str    = row.get('PRICE', '0').strip()
            category_ids = row.get('CATEGORY_IDS', '').strip()
            image_url    = row.get('IMAGE_URL', '').strip()
            brand        = row.get('BRAND', '').strip()

            if not product_id or not product_name:
                skipped += 1
                continue

            try:
                price = float(price_str.replace('$', '').replace(',', ''))
            except ValueError:
                price = 0.0

            print(f'\n📦 Processing [{product_id}]: {product_name[:55]}...')

            # Text used for each vector
            name_text     = product_name
            summary_text  = summary if summary else product_name
            category_text = category_ids if category_ids else product_name

            vec_name     = get_google_embedding(name_text)
            vec_summary  = get_google_embedding(summary_text)
            vec_category = get_google_embedding(category_text)

            if not vec_name or not vec_summary or not vec_category:
                print(f'⚠️  Embedding failed for {product_id} – skipping')
                skipped += 1
                continue

            try:
                cursor.execute(insert_sql, (
                    product_id,
                    product_name,
                    summary,
                    price,
                    category_ids,
                    image_url,
                    brand,
                    str(vec_name),
                    str(vec_summary),
                    str(vec_category),
                ))
                loaded += 1
                print(f'✅ Inserted {product_name[:50]}')
            except Exception as e:
                print(f'❌ Insert failed for {product_id}: {e}')
                skipped += 1

    print(f'\n{"="*70}')
    print(f'📊 Products Load Summary')
    print(f'   ✅ Loaded : {loaded}')
    print(f'   ⚠️  Skipped: {skipped}')
    print(f'{"="*70}')
    return loaded, skipped


# ── Accessories ────────────────────────────────────────────────────────────────

def create_accessories_table(cursor):
    """
    SAP_BUNNINGS_ACCESSORIES_V1
    Mirrors bunnings_accessories.csv – a mapping/join table.
    No embedding columns (accessory names are already covered by the products table).
    """
    drop_table(cursor, ACCESSORIES_TABLE)

    ddl = f"""
    CREATE TABLE {ACCESSORIES_TABLE} (
        ID                  NVARCHAR(255)  PRIMARY KEY,
        PRODUCT_ID          NVARCHAR(50)   NOT NULL,
        PRODUCT_NAME        NVARCHAR(500),
        ACCESSORY_ID        NVARCHAR(50)   NOT NULL,
        ACCESSORY_NAME      NVARCHAR(500),
        ACCESSORY_CATEGORY  NVARCHAR(255),
        ACCESSORY_PRICE     DECIMAL(10,2),
        ACCESSORY_IMAGE     NVARCHAR(1000)
    )
    """
    cursor.execute(ddl)
    print(f'✅ Table {ACCESSORIES_TABLE} created')


def load_accessories(cursor, csv_path):
    create_accessories_table(cursor)

    insert_sql = f"""
    INSERT INTO {ACCESSORIES_TABLE}
        (ID, PRODUCT_ID, PRODUCT_NAME, ACCESSORY_ID, ACCESSORY_NAME,
         ACCESSORY_CATEGORY, ACCESSORY_PRICE, ACCESSORY_IMAGE)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    loaded = skipped = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                product_id      = row['PRODUCT_ID'].strip()
                product_name    = row['PRODUCT_NAME'].strip()
                accessory_id    = row['ACCESSORY_ID'].strip()
                accessory_name  = row['ACCESSORY_NAME'].strip()
                acc_category    = row['ACCESSORY_CATEGORY'].strip()
                acc_image       = row['ACCESSORY_IMAGE'].strip()

                try:
                    acc_price = float(row['ACCESSORY_PRICE'].strip())
                except (ValueError, KeyError):
                    acc_price = 0.0

                # Composite PK avoids duplicate rows
                row_id = f'{product_id}_{accessory_id}'

                cursor.execute(insert_sql, (
                    row_id,
                    product_id,
                    product_name,
                    accessory_id,
                    accessory_name,
                    acc_category,
                    acc_price,
                    acc_image,
                ))
                loaded += 1

                if loaded % 50 == 0:
                    print(f'   ... {loaded} accessory rows loaded')

            except Exception as e:
                skipped += 1
                print(f'⚠️  Skipped accessory row: {e}')

    print(f'\n{"="*70}')
    print(f'📊 Accessories Load Summary')
    print(f'   ✅ Loaded : {loaded}')
    print(f'   ⚠️  Skipped: {skipped}')
    print(f'{"="*70}')
    return loaded, skipped


# ── Verification ───────────────────────────────────────────────────────────────

def verify(cursor):
    print('\n🔍 Verification')
    print('─' * 60)

    cursor.execute(f'SELECT COUNT(*) FROM {PRODUCTS_TABLE}')
    print(f'   {PRODUCTS_TABLE}: {cursor.fetchone()[0]} rows')

    cursor.execute(f'SELECT COUNT(*) FROM {ACCESSORIES_TABLE}')
    print(f'   {ACCESSORIES_TABLE}: {cursor.fetchone()[0]} rows')

    print('\n   Top 5 categories in products table:')
    cursor.execute(f"""
        SELECT CATEGORY_IDS, COUNT(*) AS CNT
        FROM {PRODUCTS_TABLE}
        GROUP BY CATEGORY_IDS
        ORDER BY CNT DESC
        LIMIT 5
    """)
    for r in cursor.fetchall():
        print(f'     {r[1]:3}  {r[0][:70]}')

    print('\n   Accessory category breakdown:')
    cursor.execute(f"""
        SELECT ACCESSORY_CATEGORY, COUNT(*) AS CNT
        FROM {ACCESSORIES_TABLE}
        GROUP BY ACCESSORY_CATEGORY
        ORDER BY CNT DESC
    """)
    for r in cursor.fetchall():
        print(f'     {r[1]:3}  {r[0]}')


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    products_csv    = os.path.join('data', 'bunnings_products.csv')
    accessories_csv = os.path.join('data', 'bunnings_accessories.csv')

    print('=' * 70)
    print('🚀 Bunnings Products & Accessories → SAP HANA Cloud')
    print(f'   Products CSV    : {products_csv}')
    print(f'   Accessories CSV : {accessories_csv}')
    print(f'   Products table  : {PRODUCTS_TABLE}')
    print(f'   Accessories table: {ACCESSORIES_TABLE}')
    print(f'   Embedding model : gemini-embedding-001 (3072 dims)')
    print('=' * 70)

    confirm = input('\n⚠️  This will DROP and RECREATE both tables. Continue? (yes/no): ')
    if confirm.strip().lower() != 'yes':
        print('❌ Cancelled')
        return

    conn = connect_to_hana()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        # ── Load products (with embeddings) ─────────────────────────────────
        print('\n' + '─' * 70)
        print(f'STEP 1/2 – Loading bunnings products into {PRODUCTS_TABLE}')
        print('─' * 70)
        load_products(cursor, products_csv)
        conn.commit()
        print('✅ Products committed')

        # ── Load accessories (no embeddings) ────────────────────────────────
        print('\n' + '─' * 70)
        print(f'STEP 2/2 – Loading bunnings accessories into {ACCESSORIES_TABLE}')
        print('─' * 70)
        load_accessories(cursor, accessories_csv)
        conn.commit()
        print('✅ Accessories committed')

        # ── Verify ──────────────────────────────────────────────────────────
        verify(cursor)

    except Exception as e:
        print(f'\n❌ Unexpected error: {e}')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        print('\n🔒 HANA connection closed')


if __name__ == '__main__':
    main()
