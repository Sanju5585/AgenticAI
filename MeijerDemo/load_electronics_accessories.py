# load_electronics_accessories.py - Load accessories for electronics products
# Creates mapping between products and their compatible accessories

import csv
import os
from hdbcli import dbapi
from dotenv import load_dotenv

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

def create_accessories_table(cursor):
    """Create the electronics accessories table"""
    table_name = "SAP_ELECTRONICS_ACCESSORIES_V2"
    
    try:
        # Drop existing table
        cursor.execute(f"DROP TABLE {table_name}")
        print(f"🗑️  Dropped existing table {table_name}")
    except Exception as e:
        print(f"ℹ️  Table {table_name} doesn't exist yet: {e}")
    
    # Create new table
    create_table_sql = f"""
    CREATE TABLE {table_name} (
        ID NVARCHAR(255) PRIMARY KEY,
        PRODUCT_ID NVARCHAR(255) NOT NULL,
        PRODUCT_NAME NVARCHAR(500),
        ACCESSORY_ID NVARCHAR(255) NOT NULL,
        ACCESSORY_NAME NVARCHAR(500),
        ACCESSORY_CATEGORY NVARCHAR(100),
        ACCESSORY_PRICE DECIMAL(10,2),
        ACCESSORY_IMAGE NVARCHAR(500)
    )
    """
    cursor.execute(create_table_sql)
    print(f"✅ Table {table_name} created successfully")

def load_accessories_from_csv(cursor, csv_file_path):
    """Load accessories data from CSV file"""
    table_name = "SAP_ELECTRONICS_ACCESSORIES_V2"
    
    insert_sql = f"""
    INSERT INTO {table_name} 
    (ID, PRODUCT_ID, PRODUCT_NAME, ACCESSORY_ID, ACCESSORY_NAME, ACCESSORY_CATEGORY, ACCESSORY_PRICE, ACCESSORY_IMAGE)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    loaded_count = 0
    skipped_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row in csv_reader:
                try:
                    # Generate unique ID
                    unique_id = f"{row['PRODUCT_ID']}_{row['ACCESSORY_ID']}"
                    
                    # Parse price
                    price = float(row['ACCESSORY_PRICE']) if row['ACCESSORY_PRICE'] else 0.0
                    
                    cursor.execute(insert_sql, (
                        unique_id,
                        row['PRODUCT_ID'],
                        row['PRODUCT_NAME'],
                        row['ACCESSORY_ID'],
                        row['ACCESSORY_NAME'],
                        row['ACCESSORY_CATEGORY'],
                        price,
                        row['ACCESSORY_IMAGE']
                    ))
                    loaded_count += 1
                    
                    if loaded_count % 20 == 0:
                        print(f"   Loaded {loaded_count} accessories...")
                        
                except Exception as e:
                    skipped_count += 1
                    print(f"⚠️  Skipped row: {e}")
                    
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_file_path}")
        return 0, 0
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return 0, 0
    
    print(f"✅ Loaded {loaded_count} accessories, skipped {skipped_count}")
    return loaded_count, skipped_count

def main():
    """Main function to create and populate accessories table"""
    print("🚀 Starting Electronics Accessories Setup")
    print("=" * 60)
    
    conn = connect_to_hana()
    if not conn:
        print("❌ Cannot proceed without database connection")
        return
    
    cursor = conn.cursor()
    
    try:
        # Create table
        print("\n📊 Creating Electronics Accessories Table...")
        create_accessories_table(cursor)
        
        # Load data from CSV
        print("\n💾 Loading Accessories from CSV...")
        csv_path = os.path.join('data', 'electronics_accessories.csv')
        loaded, skipped = load_accessories_from_csv(cursor, csv_path)
        
        # Commit changes
        conn.commit()
        print(f"\n✅ Successfully committed all changes")
        
        # Verify data
        print("\n🔍 Verifying loaded data...")
        cursor.execute("SELECT COUNT(*) FROM SAP_ELECTRONICS_ACCESSORIES_V2")
        count = cursor.fetchone()[0]
        print(f"   Total accessory mappings: {count}")
        
        # Show products with accessories
        print("\n📋 Products with Accessories:")
        cursor.execute("""
            SELECT PRODUCT_ID, PRODUCT_NAME, COUNT(*) as ACC_COUNT 
            FROM SAP_ELECTRONICS_ACCESSORIES_V2 
            GROUP BY PRODUCT_ID, PRODUCT_NAME 
            ORDER BY ACC_COUNT DESC
            LIMIT 10
        """)
        for row in cursor.fetchall():
            print(f"   {row[1]} (ID: {row[0]}): {row[2]} accessories")
        
        # Show accessory categories
        print("\n📦 Accessory Categories:")
        cursor.execute("""
            SELECT ACCESSORY_CATEGORY, COUNT(*) as COUNT 
            FROM SAP_ELECTRONICS_ACCESSORIES_V2 
            GROUP BY ACCESSORY_CATEGORY 
            ORDER BY COUNT DESC
        """)
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]} items")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        print("\n" + "=" * 60)
        print("✅ Electronics Accessories Setup Complete!")

if __name__ == "__main__":
    main()
