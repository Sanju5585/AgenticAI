"""
Quick script to properly load products and accessories into V2 tables
"""
import pandas as pd
import time
from hdbcli import dbapi
from ecom_llm import get_google_embedding

# Database connection
def connect_db():
    return dbapi.connect(
        address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
        port='443',
        user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
        password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
        encrypt=True,
        sslValidateCertificate=False
    )

print("=" * 80)
print("🚀 Loading Products into V2 Table")
print("=" * 80)

conn = connect_db()
cursor = conn.cursor()

# Load Products
products_df = pd.read_csv('data/product.csv', on_bad_lines='skip', encoding='utf-8', quotechar='"')
count = 0

for index, row in products_df.iterrows():
    product_id = "unknown"
    try:
        product_id = str(row['PRODUCT_ID'])
        product_name = str(row['PRODUCT_NAME']) if pd.notna(row['PRODUCT_NAME']) else ""
        summary = str(row['SUMMARY']) if pd.notna(row['SUMMARY']) else ""
        
        # Clean and convert price
        price_str = str(row['PRICE']) if pd.notna(row['PRICE']) else "0"
        price = float(price_str.replace('$', '').replace(',', '').strip())
        
        category_ids = str(row['CATEGORY_IDS']) if pd.notna(row['CATEGORY_IDS']) else ""
        image_url = str(row['IMAGE_URL']) if pd.notna(row['IMAGE_URL']) else ""
        
        # Generate enhanced vectors
        enhanced_name_text = f"{product_name} {category_ids}"
        enhanced_summary_text = f"{product_name}. {summary}. Price: ${price}. Category: {category_ids}"
        
        print(f"  📝 [{count+1}/{len(products_df)}] Processing: {product_name} (${price})")
        
        vector_name = get_google_embedding(enhanced_name_text)
        time.sleep(0.3)
        vector_summary = get_google_embedding(enhanced_summary_text)
        
        if not vector_name or not vector_summary:
            print(f"  ⚠️  Skipping {product_name} - couldn't generate vectors")
            continue
        
        # Convert to string format
        vector_name_str = "[" + ",".join(map(str, vector_name)) + "]"
        vector_summary_str = "[" + ",".join(map(str, vector_summary)) + "]"
        
        # Insert product
        insert_query = """
            INSERT INTO SAP_PRODUCTS_COMMERCE_2211_V2
            (PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDs, IMAGE_URL, VECTOR_NAME, VECTOR_SUMMARY)
            VALUES (?, ?, ?, ?, ?, ?, TO_REAL_VECTOR(?), TO_REAL_VECTOR(?))
        """
        
        cursor.execute(insert_query, (
            product_id,
            product_name,
            summary,
            price,
            category_ids,
            image_url,
            vector_name_str,
            vector_summary_str
        ))
        
        count += 1
        if count % 10 == 0:
            conn.commit()
            print(f"  ✅ Committed {count} products...")
            time.sleep(1)  # Rate limiting
        
    except Exception as e:
        print(f"  ❌ Error loading product {product_id}: {e}")
        continue

conn.commit()
print(f"\n✅ Successfully loaded {count} products into SAP_PRODUCTS_COMMERCE_2211_V2")

# Load Accessories
print("\n" + "=" * 80)
print("🚀 Loading Accessories into V2 Table")
print("=" * 80)

accessories_df = pd.read_csv('data/accessories.csv', on_bad_lines='skip', encoding='utf-8')
acc_count = 0

for index, row in accessories_df.iterrows():
    try:
        product_id = str(row['PRODUCT_ID'])
        product_name = str(row['PRODUCT_NAME']) if pd.notna(row['PRODUCT_NAME']) else ""
        product_ids = str(row['PRODUCT_IDS']) if pd.notna(row['PRODUCT_IDS']) else ""
        
        print(f"  📝 [{acc_count+1}/{len(accessories_df)}] Processing: {product_name}")
        
        # Generate vector
        vector_name = get_google_embedding(product_name)
        
        if not vector_name:
            print(f"  ⚠️  Skipping {product_name} - couldn't generate vector")
            continue
        
        vector_name_str = "[" + ",".join(map(str, vector_name)) + "]"
        accessory_id = f"ACC-{product_id}"
        
        # Insert accessory
        insert_query = """
            INSERT INTO SAP_ACCESSORIES_COMMERCE_2211_V2
            (ACCESSORY_ID, PRODUCT_ID, PRODUCT_NAME, PRODUCT_IDS, VECTOR_PRODUCT_NAME)
            VALUES (?, ?, ?, ?, TO_REAL_VECTOR(?))
        """
        
        cursor.execute(insert_query, (
            accessory_id,
            product_id,
            product_name,
            product_ids,
            vector_name_str
        ))
        
        acc_count += 1
        if acc_count % 10 == 0:
            conn.commit()
            print(f"  ✅ Committed {acc_count} accessories...")
            time.sleep(1)
        
    except Exception as e:
        print(f"  ❌ Error loading accessory {product_id}: {e}")
        continue

conn.commit()
print(f"\n✅ Successfully loaded {acc_count} accessories into SAP_ACCESSORIES_COMMERCE_2211_V2")

# Verify
print("\n" + "=" * 80)
print("📊 FINAL VERIFICATION")
print("=" * 80)

cursor.execute("SELECT COUNT(*) FROM SAP_PRODUCTS_COMMERCE_2211_V2")
products_count = cursor.fetchone()[0]
print(f"✅ Products V2: {products_count} records")

cursor.execute("SELECT COUNT(*) FROM SAP_PROMOTIONS_COMMERCE_2211_V2")
promotions_count = cursor.fetchone()[0]
print(f"✅ Promotions V2: {promotions_count} records")

cursor.execute("SELECT COUNT(*) FROM SAP_ACCESSORIES_COMMERCE_2211_V2")
accessories_count = cursor.fetchone()[0]
print(f"✅ Accessories V2: {accessories_count} records")

# Sample products
print("\n📋 Sample Products with Prices:")
cursor.execute("SELECT TOP 5 PRODUCT_ID, PRODUCT_NAME, PRICE FROM SAP_PRODUCTS_COMMERCE_2211_V2 ORDER BY PRICE DESC")
for row in cursor.fetchall():
    print(f"  - {row[1]}: £{row[2]:.2f}")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("✅ ALL COMPLETE!")
print("=" * 80)
