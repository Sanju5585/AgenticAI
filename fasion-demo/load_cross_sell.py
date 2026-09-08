"""
Load Cross-Sell Product Associations into HANA Database
Creates SAP_PRODUCT_CROSS_SELL_V2 table for product recommendations
"""
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

def drop_table_if_exists(cursor, table_name):
    """Drop table if it exists"""
    try:
        cursor.execute(f"DROP TABLE {table_name}")
        print(f"✅ Table {table_name} dropped")
    except Exception as e:
        print(f"ℹ️  Table {table_name} doesn't exist or couldn't be dropped")

def load_cross_sell_csv(cursor, csv_file_path):
    """Load cross-sell data from CSV into SAP_PRODUCT_CROSS_SELL_V2 table"""
    
    table_name = "SAP_PRODUCT_CROSS_SELL_V2"
    
    # Drop and recreate table
    drop_table_if_exists(cursor, table_name)
    
    # Create table
    create_table_sql = f"""
    CREATE TABLE {table_name} (
        ID INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        SOURCE_PRODUCT_ID NVARCHAR(255),
        CROSS_SELL_PRODUCT_ID NVARCHAR(255),
        RELATIONSHIP_TYPE NVARCHAR(50),
        PRIORITY INTEGER,
        CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    try:
        cursor.execute(create_table_sql)
        print(f"✅ Table {table_name} created successfully")
    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return
    
    # Read and load CSV data
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            
            insert_sql = f"""
            INSERT INTO {table_name} 
            (SOURCE_PRODUCT_ID, CROSS_SELL_PRODUCT_ID, RELATIONSHIP_TYPE, PRIORITY)
            VALUES (?, ?, ?, ?)
            """
            
            loaded_count = 0
            skipped_count = 0
            
            for row in csv_reader:
                source_product_id = row.get('SOURCE_PRODUCT_ID', '').strip()
                cross_sell_product_id = row.get('CROSS_SELL_PRODUCT_ID', '').strip()
                relationship_type = row.get('RELATIONSHIP_TYPE', 'cross-sell').strip()
                priority_str = row.get('PRIORITY', '1').strip()
                
                # Skip if missing required fields
                if not source_product_id or not cross_sell_product_id:
                    skipped_count += 1
                    continue
                
                # Parse priority
                try:
                    priority = int(priority_str)
                except:
                    priority = 1
                
                try:
                    cursor.execute(insert_sql, (
                        source_product_id,
                        cross_sell_product_id,
                        relationship_type,
                        priority
                    ))
                    loaded_count += 1
                    print(f"✅ Loaded: {source_product_id} → {cross_sell_product_id} ({relationship_type})")
                    
                except Exception as e:
                    print(f"❌ Failed to load {source_product_id} → {cross_sell_product_id}: {e}")
                    skipped_count += 1
            
            print(f"\n📊 Summary:")
            print(f"   ✅ Loaded: {loaded_count} cross-sell associations")
            print(f"   ❌ Skipped: {skipped_count} rows")
            
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_file_path}")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")

def verify_data(cursor):
    """Verify loaded data"""
    try:
        cursor.execute("SELECT COUNT(*) FROM SAP_PRODUCT_CROSS_SELL_V2")
        count = cursor.fetchone()[0]
        print(f"\n✅ Total cross-sell associations in database: {count}")
        
        # Show sample data
        cursor.execute("""
            SELECT SOURCE_PRODUCT_ID, CROSS_SELL_PRODUCT_ID, RELATIONSHIP_TYPE, PRIORITY 
            FROM SAP_PRODUCT_CROSS_SELL_V2 
            ORDER BY PRIORITY 
            LIMIT 5
        """)
        
        print(f"\n📋 Sample cross-sell associations:")
        for row in cursor.fetchall():
            print(f"   {row[0]} → {row[1]} ({row[2]}, priority: {row[3]})")
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")

def main():
    print("=" * 80)
    print("🔄 Loading Cross-Sell Product Associations into HANA")
    print("=" * 80)
    
    # Connect to database
    connection = connect_to_hana()
    if not connection:
        return
    
    cursor = connection.cursor()
    
    # Load cross-sell data
    csv_file = os.path.join('data', 'product_cross_sell.csv')
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return
    
    load_cross_sell_csv(cursor, csv_file)
    
    # Commit changes
    connection.commit()
    print("\n✅ All changes committed to database")
    
    # Verify data
    verify_data(cursor)
    
    # Close connection
    cursor.close()
    connection.close()
    print("\n✅ Database connection closed")
    print("=" * 80)

if __name__ == "__main__":
    main()
