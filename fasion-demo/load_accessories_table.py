"""
Load accessories.csv into SAP_ACCESSORIES_COMMERCE_2211 table.
This creates/recreates the table and loads all 305 accessory mappings.
"""
import pandas as pd
from hdbcli import dbapi

def connect_db():
    return dbapi.connect(
        address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
        port='443',
        user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
        password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
        encrypt=True,
        sslValidateCertificate=False
    )

print("=" * 70)
print("🚀 Loading accessories.csv → SAP_ACCESSORIES_COMMERCE_2211")
print("=" * 70)

conn = connect_db()
cursor = conn.cursor()

# Drop and recreate the table
print("\n📋 Creating SAP_ACCESSORIES_COMMERCE_2211 table...")
try:
    cursor.execute("DROP TABLE SAP_ACCESSORIES_COMMERCE_2211")
    conn.commit()
    print("   ✅ Dropped existing table")
except Exception:
    print("   ℹ️  Table did not exist, creating fresh")

create_sql = """
CREATE TABLE SAP_ACCESSORIES_COMMERCE_2211 (
    PRODUCT_ID   NVARCHAR(50)   NOT NULL,
    PRODUCT_NAME NVARCHAR(200),
    PRODUCT_IDS  NVARCHAR(2000),
    PRIMARY KEY (PRODUCT_ID)
)
"""
cursor.execute(create_sql)
conn.commit()
print("   ✅ Table created")

# Load CSV
print("\n📂 Reading accessories.csv...")
df = pd.read_csv('data/accessories.csv', on_bad_lines='skip', encoding='utf-8')
print(f"   Found {len(df)} rows")

# Insert rows
print("\n⬆️  Inserting rows...")
count = 0
skipped = 0

for _, row in df.iterrows():
    try:
        product_id   = str(row['PRODUCT_ID']).strip()
        product_name = str(row['PRODUCT_NAME']).strip() if pd.notna(row['PRODUCT_NAME']) else ""
        product_ids  = str(row['PRODUCT_IDS']).strip() if pd.notna(row['PRODUCT_IDS']) else ""

        if not product_id:
            skipped += 1
            continue

        cursor.execute(
            "INSERT INTO SAP_ACCESSORIES_COMMERCE_2211 (PRODUCT_ID, PRODUCT_NAME, PRODUCT_IDS) VALUES (?, ?, ?)",
            (product_id, product_name, product_ids)
        )
        count += 1

        if count % 50 == 0:
            conn.commit()
            print(f"   ✅ Inserted {count} rows...")

    except Exception as e:
        print(f"   ⚠️  Skipped {row.get('PRODUCT_ID', '?')}: {e}")
        skipped += 1

conn.commit()
cursor.close()
conn.close()

print(f"\n{'=' * 70}")
print(f"✅ Done! Inserted {count} rows | Skipped {skipped}")

# Verify
print("\n🔍 Verifying...")
conn2 = connect_db()
c2 = conn2.cursor()
c2.execute("SELECT COUNT(*) FROM SAP_ACCESSORIES_COMMERCE_2211")
total = c2.fetchone()[0]
print(f"   Table rows: {total}")
c2.execute("SELECT TOP 5 PRODUCT_ID, PRODUCT_NAME, PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211")
print("\n   Sample rows:")
for r in c2.fetchall():
    print(f"   - [{r[0]}] {r[1]} → {r[2][:60]}...")
c2.close()
conn2.close()
print("\n✅ Accessories table is ready!")
