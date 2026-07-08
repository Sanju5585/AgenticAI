#!/usr/bin/env python3
"""
Debug script to check the accessories database and product matching
"""

import os
import configparser
from hdbcli import dbapi

# Configuration
config_properties = configparser.ConfigParser()
config_properties.read('config.ini')

def hana_connect():
    connection = dbapi.connect(
        address=config_properties['database']['ADDRESS'],
        port=config_properties['database']['PORT'],
        user=config_properties['database']['USER'],
        password=config_properties['database']['PASSWORD'],
        encrypt='true',
        sslValidateCertificate='false'
    )
    return connection

def check_accessories_data():
    print("🔍 Checking accessories database...")
    
    conn = hana_connect()
    cursor = conn.cursor()
    
    # Check what's in the accessories table
    cursor.execute("SELECT COUNT(*) FROM SAP_ACCESSORIES_COMMERCE_2211")
    count = cursor.fetchone()[0]
    print(f"📊 Total accessories entries: {count}")
    
    # Check some sample data
    cursor.execute("SELECT PRODUCT_ID, PRODUCT_NAME, PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 LIMIT 10")
    samples = cursor.fetchall()
    
    print("\n📋 Sample accessories data:")
    for i, (pid, pname, accessory_ids) in enumerate(samples, 1):
        print(f"{i}. Product ID: {pid} | Name: {pname[:50]}{'...' if len(pname) > 50 else ''}")
        print(f"   Accessories: {accessory_ids[:100]}{'...' if len(accessory_ids) > 100 else ''}")
    
    # Check if our test products exist
    test_product_ids = ['0031-1', '0032-1', '100191', '94474', '94462']
    
    print(f"\n🎯 Checking for our test product IDs: {test_product_ids}")
    
    for test_id in test_product_ids:
        test_id = test_id.strip()
        cursor.execute("SELECT PRODUCT_NAME, PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE PRODUCT_ID = ?", (test_id,))
        result = cursor.fetchone()
        
        if result:
            print(f"✅ Found {test_id}: {result[0][:50]}...")
            print(f"   Accessories: {result[1][:100]}{'...' if len(result[1]) > 100 else ''}")
        else:
            print(f"❌ NOT FOUND: {test_id}")
            
            # Try variations
            cursor.execute("SELECT PRODUCT_ID, PRODUCT_NAME FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE PRODUCT_ID LIKE ?", (f'%{test_id}%',))
            similar = cursor.fetchall()
            if similar:
                print(f"   Similar IDs found: {[s[0] for s in similar[:3]]}")
    
    # Check product names
    test_product_names = ['Trench Coat', 'Leather Jacket', 'Beacon Jacket', 'Trenchtown Jacket', 'Bender Jacket']
    
    print(f"\n🎯 Checking for our test product names...")
    
    for test_name in test_product_names:
        test_name = test_name.strip()
        cursor.execute("SELECT PRODUCT_ID, PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE UPPER(PRODUCT_NAME) LIKE UPPER(?)", (f'%{test_name}%',))
        results = cursor.fetchall()
        
        if results:
            print(f"✅ Found matches for '{test_name}': {len(results)} entries")
            for r in results[:2]:
                print(f"   ID: {r[0]} | Accessories: {r[1][:50]}...")
        else:
            print(f"❌ NOT FOUND: '{test_name}'")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_accessories_data()