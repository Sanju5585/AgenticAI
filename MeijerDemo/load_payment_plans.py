# load_payment_plans.py - Load payment plans for mobile and watch products
# Plans include storage variants and monthly payment options

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

def create_payment_plans_table(cursor):
    """Create the payment plans table"""
    table_name = "SAP_PRODUCT_PAYMENT_PLANS_V2"
    
    try:
        # Drop existing table
        cursor.execute(f"DROP TABLE {table_name}")
        print(f"🗑️  Dropped existing table {table_name}")
    except Exception as e:
        print(f"ℹ️  Table {table_name} doesn't exist: {e}")
    
    # Create new table
    create_table_sql = f"""
    CREATE TABLE {table_name} (
        PLAN_ID NVARCHAR(255) PRIMARY KEY,
        PRODUCT_ID NVARCHAR(255) NOT NULL,
        VARIANT_NAME NVARCHAR(255),
        MONTHLY_PAYMENT DECIMAL(10,2),
        DURATION_MONTHS INTEGER,
        DUE_TODAY DECIMAL(10,2),
        FULL_PRICE DECIMAL(10,2),
        STOCK_STATUS NVARCHAR(50),
        VARIANT_ORDER INTEGER
    )
    """
    cursor.execute(create_table_sql)
    print(f"✅ Table {table_name} created successfully")

def load_sample_payment_plans(cursor):
    """Load sample payment plans for mobile and watch products"""
    table_name = "SAP_PRODUCT_PAYMENT_PLANS_V2"
    
    # Sample data - Plans for popular mobile and watch products
    # Format: PLAN_ID, PRODUCT_ID, VARIANT_NAME, MONTHLY_PAYMENT, DURATION_MONTHS, DUE_TODAY, FULL_PRICE, STOCK_STATUS, VARIANT_ORDER
    sample_plans = [
        # iPhone 15 Plans (Product ID: 200022)
        ('PLAN_200022_256', '200022', '256GB', 4.16, 24, 0.00, 1199.99, 'Out of stock', 1),
        ('PLAN_200022_512', '200022', '512GB', 12.50, 24, 0.00, 1399.99, 'Out of stock', 2),
        ('PLAN_200022_1TB', '200022', '1TB', 20.83, 24, 0.00, 1599.99, 'Out of stock', 3),
        ('PLAN_200022_2TB', '200022', '2TB', 33.33, 24, 99.99, 1999.99, 'Out of stock', 4),
        
        # iPhone 15 Pro (Product ID: 200029)
        ('PLAN_200029_256', '200029', '256GB', 45.83, 24, 0.00, 1199.99, 'In stock', 1),
        ('PLAN_200029_512', '200029', '512GB', 50.00, 24, 0.00, 1299.99, 'In stock', 2),
        ('PLAN_200029_1TB', '200029', '1TB', 58.33, 24, 0.00, 1499.99, 'In stock', 3),
        ('PLAN_200029_2TB', '200029', '2TB', 66.67, 24, 0.00, 1699.99, 'In stock', 4),
        
        # Samsung Galaxy S25 (Product ID: 200050)
        ('PLAN_200050_128', '200050', '128GB', 33.33, 24, 0.00, 799.99, 'In stock', 1),
        ('PLAN_200050_256', '200050', '256GB', 37.50, 24, 0.00, 899.99, 'In stock', 2),
        ('PLAN_200050_512', '200050', '512GB', 41.67, 24, 0.00, 999.99, 'In stock', 3),
        
        # Samsung Galaxy S25 Ultra (Product ID: 200055)
        ('PLAN_200055_256', '200055', '256GB', 52.50, 24, 0.00, 1259.99, 'In stock', 1),
        ('PLAN_200055_512', '200055', '512GB', 58.33, 24, 0.00, 1399.99, 'In stock', 2),
        ('PLAN_200055_1TB', '200055', '1TB', 66.67, 24, 0.00, 1599.99, 'In stock', 3),
        
        # Google Pixel 9a (Product ID: 200058)
        ('PLAN_200058_128', '200058', '128GB', 26.25, 24, 0.00, 629.99, 'In stock', 1),
        ('PLAN_200058_256', '200058', '256GB', 29.17, 24, 0.00, 699.99, 'In stock', 2),
        
        # Apple iPhone 16 Pro Max (Product ID: 200053)
        ('PLAN_200053_256', '200053', '256GB', 54.17, 24, 0.00, 1299.99, 'In stock', 1),
        ('PLAN_200053_512', '200053', '512GB', 58.33, 24, 0.00, 1399.99, 'In stock', 2),
        ('PLAN_200053_1TB', '200053', '1TB', 62.50, 24, 0.00, 1499.99, 'In stock', 3),
        
        # Apple Watch Series 11 42mm (Product ID: 400001)
        ('PLAN_400001_GPS', '400001', 'GPS', 20.83, 24, 0.00, 499.99, 'In stock', 1),
        ('PLAN_400001_GPS_CELL', '400001', 'GPS + Cellular', 25.00, 24, 0.00, 599.99, 'In stock', 2),
        
        # Apple Watch Series 11 46mm (Product ID: 400002)
        ('PLAN_400002_GPS', '400002', 'GPS', 22.08, 24, 0.00, 529.99, 'In stock', 1),
        ('PLAN_400002_GPS_CELL', '400002', 'GPS + Cellular', 27.08, 24, 0.00, 649.99, 'In stock', 2),
        
        # Apple Watch Ultra 3 (Product ID: 400007)
        ('PLAN_400007_TIT', '400007', 'Titanium', 35.42, 24, 0.00, 849.99, 'In stock', 1),
        
        # Samsung Galaxy Watch8 40mm (Product ID: 400011)
        ('PLAN_400011_BT', '400011', 'Bluetooth', 16.67, 24, 0.00, 399.99, 'In stock', 1),
        ('PLAN_400011_LTE', '400011', 'LTE', 20.83, 24, 0.00, 499.99, 'In stock', 2),
        
        # Samsung Galaxy Watch8 44mm (Product ID: 400012)
        ('PLAN_400012_BT', '400012', 'Bluetooth', 17.92, 24, 0.00, 429.99, 'In stock', 1),
        ('PLAN_400012_LTE', '400012', 'LTE', 22.08, 24, 0.00, 529.99, 'In stock', 2),
        
        # Samsung Galaxy Watch Ultra 47mm (Product ID: 400014)
        ('PLAN_400014_LTE', '400014', 'LTE', 27.08, 24, 0.00, 649.99, 'In stock', 1),
        
        # iPhone 17 Pro Max (Product ID: 200036)
        ('PLAN_200036_256', '200036', '256GB', 65.67, 24, 0.00, 1576.13, 'In stock', 1),
        ('PLAN_200036_512', '200036', '512GB', 70.83, 24, 0.00, 1699.99, 'In stock', 2),
        ('PLAN_200036_1TB', '200036', '1TB', 79.17, 24, 0.00, 1899.99, 'In stock', 3),
        
        # Samsung Galaxy Z Flip5 (Product ID: 200037)
        ('PLAN_200037_256', '200037', '256GB', 43.03, 24, 0.00, 1032.62, 'In stock', 1),
        ('PLAN_200037_512', '200037', '512GB', 47.92, 24, 0.00, 1149.99, 'In stock', 2),
        
        # Samsung Galaxy Z Fold5 (Product ID: 200044)
        ('PLAN_200044_256', '200044', '256GB', 56.19, 24, 0.00, 1348.44, 'In stock', 1),
        ('PLAN_200044_512', '200044', '512GB', 62.50, 24, 0.00, 1499.99, 'In stock', 2),
        ('PLAN_200044_1TB', '200044', '1TB', 70.83, 24, 0.00, 1699.99, 'In stock', 3),
    ]
    
    insert_sql = f"""
    INSERT INTO {table_name} 
    (PLAN_ID, PRODUCT_ID, VARIANT_NAME, MONTHLY_PAYMENT, DURATION_MONTHS, DUE_TODAY, FULL_PRICE, STOCK_STATUS, VARIANT_ORDER)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    loaded_count = 0
    for plan in sample_plans:
        try:
            cursor.execute(insert_sql, plan)
            loaded_count += 1
        except Exception as e:
            print(f"❌ Failed to insert plan {plan[0]}: {e}")
    
    print(f"✅ Loaded {loaded_count} payment plans")
    return loaded_count

def main():
    """Main function to create and populate payment plans table"""
    print("🚀 Starting Payment Plans Setup")
    print("=" * 60)
    
    conn = connect_to_hana()
    if not conn:
        print("❌ Cannot proceed without database connection")
        return
    
    cursor = conn.cursor()
    
    try:
        # Create table
        print("\n📊 Creating Payment Plans Table...")
        create_payment_plans_table(cursor)
        
        # Load sample data
        print("\n💾 Loading Sample Payment Plans...")
        loaded_count = load_sample_payment_plans(cursor)
        
        # Commit changes
        conn.commit()
        print(f"\n✅ Successfully committed all changes")
        
        # Verify data
        print("\n🔍 Verifying loaded data...")
        cursor.execute("SELECT COUNT(*) FROM SAP_PRODUCT_PAYMENT_PLANS_V2")
        count = cursor.fetchone()[0]
        print(f"   Total plans in database: {count}")
        
        # Show sample data
        print("\n📋 Sample Plans:")
        cursor.execute("""
            SELECT PRODUCT_ID, COUNT(*) as PLAN_COUNT 
            FROM SAP_PRODUCT_PAYMENT_PLANS_V2 
            GROUP BY PRODUCT_ID 
            ORDER BY PRODUCT_ID
            LIMIT 10
        """)
        for row in cursor.fetchall():
            print(f"   Product {row[0]}: {row[1]} plans")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        print("\n" + "=" * 60)
        print("✅ Payment Plans Setup Complete!")

if __name__ == "__main__":
    main()
