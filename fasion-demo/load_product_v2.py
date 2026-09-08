# load_product_v2.py - Load products into SAP_PRODUCTS_COMMERCE_2211_V2 table
# Uses Google gemini-embedding-001 (3072 dimensions via v1beta API)
import csv
import os
from hdbcli import dbapi
from dotenv import load_dotenv
from ecom_llm import get_google_embedding

load_dotenv()

def connect_to_hana():
    """Connect to SAP HANA database"""
    try:
        connection = dbapi.connect(
            address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
            port=443,
            user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
            password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
            encrypt=True,
            sslValidateCertificate=False
        )
        print("✅ Connected to HANA database")
        return connection
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def drop_table_if_exists(cursor, table_name):
    """Drop table if it exists"""
    try:
        cursor.execute(f"DROP TABLE {table_name}")
        print(f"✅ Table {table_name} dropped")
    except Exception as e:
        print(f"ℹ️  Table {table_name} doesn't exist or couldn't be dropped")

def load_product_csv_data(cursor, csv_file_path):
    """Load product data from CSV into SAP_PRODUCTS_COMMERCE_2211_V2 table"""
    
    table_name = "SAP_PRODUCTS_COMMERCE_2211_V2"
    
    # Drop and recreate table
    drop_table_if_exists(cursor, table_name)
    
    # Create table with REAL_VECTOR columns (3072 dimensions for Google gemini-embedding-001)
    create_table_sql = f"""
    CREATE TABLE {table_name} (
        PRODUCT_ID NVARCHAR(255) PRIMARY KEY,
        PRODUCT_NAME NVARCHAR(500),
        SUMMARY NVARCHAR(5000),
        PRICE DECIMAL(10,2),
        CATEGORY_IDs NVARCHAR(1000),
        IMAGE_URL NVARCHAR(1000),
        VECTOR_NAME REAL_VECTOR(3072),
        VECTOR_SUMMARY REAL_VECTOR(3072)
    )
    """
    
    try:
        cursor.execute(create_table_sql)
        print(f"✅ Table {table_name} created with REAL_VECTOR columns (3072 dimensions)")
    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return
    
    # Read and load CSV data
    try:
        with open(csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            
            insert_sql = f"""
            INSERT INTO {table_name} 
            (PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDs, IMAGE_URL, VECTOR_NAME, VECTOR_SUMMARY)
            VALUES (?, ?, ?, ?, ?, ?, TO_REAL_VECTOR(?), TO_REAL_VECTOR(?))
            """
            
            loaded_count = 0
            skipped_count = 0
            
            for row in csv_reader:
                product_id = row.get('PRODUCT_ID', '').strip()
                product_name = row.get('PRODUCT_NAME', '').strip()
                summary = row.get('SUMMARY', '').strip()
                price_str = row.get('PRICE', '0').strip()
                category_ids = row.get('CATEGORY_IDS', '').strip()
                image_url = row.get('IMAGE_URL', '').strip()
                
                # Skip if no product ID or name
                if not product_id or not product_name:
                    skipped_count += 1
                    continue
                
                # Parse price
                try:
                    price = float(price_str.replace('$', '').replace(',', ''))
                except:
                    price = 0.0
                
                # Generate embeddings using Google gemini-embedding-001
                print(f"\n📦 Processing: {product_name[:50]}...")
                
                vector_name = get_google_embedding(product_name)
                vector_summary = get_google_embedding(summary if summary else product_name)
                
                # Skip if embedding generation failed
                if not vector_name or not vector_summary:
                    print(f"⚠️  Embedding generation failed for {product_id}, skipping...")
                    skipped_count += 1
                    continue
                
                # Convert embeddings to string format for HANA
                vector_name_str = str(vector_name)
                vector_summary_str = str(vector_summary)
                
                try:
                    cursor.execute(insert_sql, (
                        product_id,
                        product_name,
                        summary,
                        price,
                        category_ids,
                        image_url,
                        vector_name_str,
                        vector_summary_str
                    ))
                    loaded_count += 1
                    print(f"✅ Loaded: {product_name[:50]}...")
                    
                except Exception as e:
                    print(f"❌ Failed to insert {product_id}: {e}")
                    skipped_count += 1
            
            print(f"\n{'='*80}")
            print(f"📊 Loading Summary:")
            print(f"   ✅ Successfully loaded: {loaded_count} products")
            print(f"   ⚠️  Skipped: {skipped_count} products")
            print(f"{'='*80}")
            
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_file_path}")
    except Exception as e:
        print(f"❌ Error loading CSV data: {e}")

def main():
    """Main execution function"""
    csv_file = "data/product.csv"
    
    print("="*80)
    print("🚀 Loading Products into SAP_PRODUCTS_COMMERCE_2211_V2")
    print("   Using Google gemini-embedding-001 (3072 dimensions)")
    print("="*80)
    
    # Confirm with user
    confirm = input("\n⚠️  This will DROP and RECREATE the table. Continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Operation cancelled")
        return
    
    # Connect to database
    connection = connect_to_hana()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        
        # Load products
        load_product_csv_data(cursor, csv_file)
        
        # Commit changes
        connection.commit()
        print("\n✅ All changes committed to database")
        
        # Verify data
        cursor.execute("SELECT COUNT(*) FROM SAP_PRODUCTS_COMMERCE_2211_V2")
        count = cursor.fetchone()[0]
        print(f"✅ Total products in table: {count}")
        
        cursor.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        connection.rollback()
    finally:
        connection.close()
        print("✅ Database connection closed")

if __name__ == "__main__":
    main()
