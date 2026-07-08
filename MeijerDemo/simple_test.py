#!/usr/bin/env python3
"""
Simple test to check if accessories table exists and has data
"""

from hdbcli import dbapi

def test_accessories():
    try:
        # Use the same connection as agent.py
        conn = dbapi.connect(
            address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
            port='443',
            user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
            password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
            encrypt=True,
            autocommit=True,
            sslValidateCertificate=False,
        )
        
        cursor = conn.cursor()
        
        # Check if accessories table exists
        print("🔍 Checking if accessories table exists...")
        try:
            cursor.execute("SELECT COUNT(*) FROM SAP_ACCESSORIES_COMMERCE_2211")
            count = cursor.fetchone()[0]
            print(f"✅ SAP_ACCESSORIES_COMMERCE_2211 exists with {count} records")
            
            # Show some sample data
            cursor.execute("SELECT PRODUCT_ID, PRODUCT_NAME, PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 LIMIT 5")
            samples = cursor.fetchall()
            
            print("\n📋 Sample accessories data:")
            for i, (pid, pname, accessory_ids) in enumerate(samples, 1):
                print(f"{i}. ID: '{pid}' | Name: '{pname}' | Accessories: '{accessory_ids}'")
                
        except Exception as e:
            print(f"❌ SAP_ACCESSORIES_COMMERCE_2211 table error: {e}")
        
        # Check our specific product IDs
        test_ids = ['0031-1', '0032-1', '100191', '94474', '94462']
        print(f"\n🎯 Testing specific product IDs: {test_ids}")
        
        for test_id in test_ids:
            # Clean the ID (remove extra spaces)
            clean_id = test_id.strip()
            try:
                cursor.execute("SELECT PRODUCT_NAME, PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE TRIM(PRODUCT_ID) = ?", (clean_id,))
                result = cursor.fetchone()
                
                if result:
                    print(f"✅ Found '{clean_id}': Name='{result[0]}', Accessories='{result[1]}'")
                else:
                    print(f"❌ NOT FOUND: '{clean_id}'")
                    
                    # Try with wildcards
                    cursor.execute("SELECT PRODUCT_ID FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE PRODUCT_ID LIKE ? LIMIT 3", (f'%{clean_id}%',))
                    similar = cursor.fetchall()
                    if similar:
                        print(f"   Similar found: {[s[0] for s in similar]}")
                        
            except Exception as e:
                print(f"❌ Error checking '{clean_id}': {e}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")

if __name__ == "__main__":
    test_accessories()