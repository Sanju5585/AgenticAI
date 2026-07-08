#!/usr/bin/env python3
"""
Debug script to test T-shirt accessory search specifically
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import hana_connect

def debug_tshirt_accessories():
    """Debug T-shirt accessories specifically based on what we see in screenshot"""
    print("🔍 Debugging T-shirt Accessories")
    print("=" * 50)
    
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        
        # The T-shirts visible in the screenshot
        tshirt_products = [
            "Nightlife T-Shirt Women",
            "T-Shirt Men Playboard Flower SS black XL", 
            "T-Shirt Men Playboard Flower SS white XL",
            "Nightlife T-Shirt Women violet M"
        ]
        
        print("1. Looking for T-shirt products in database...")
        for tshirt_name in tshirt_products:
            # Search for exact product
            cursor.execute("SELECT PRODUCT_ID, PRODUCT_NAME FROM SAP_ELECTRONICS_PRODUCTS_2211_V2 WHERE UPPER(PRODUCT_NAME) LIKE UPPER(?)", (f'%{tshirt_name}%',))
            results = cursor.fetchall()
            
            if results:
                for result in results:
                    product_id = result[0]
                    product_name = result[1]
                    print(f"   ✅ Found: {product_name} (ID: {product_id})")
                    
                    # Check if this product has accessories
                    cursor.execute("SELECT PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE TRIM(PRODUCT_ID) = ?", (product_id,))
                    acc_result = cursor.fetchone()
                    
                    if acc_result and acc_result[0]:
                        accessory_ids = [pid.strip() for pid in acc_result[0].split(',') if pid.strip()]
                        print(f"       🎯 HAS ACCESSORIES: {len(accessory_ids)} items")
                        print(f"       📦 Accessory IDs: {', '.join(accessory_ids)}")
                        
                        # Get actual accessory product details
                        for acc_id in accessory_ids[:3]:  # Show first 3
                            cursor.execute("SELECT PRODUCT_NAME, PRICE FROM SAP_ELECTRONICS_PRODUCTS_2211_V2 WHERE PRODUCT_ID = ?", (acc_id,))
                            acc_detail = cursor.fetchone()
                            if acc_detail:
                                print(f"          🛍️  {acc_detail[0]} - £{acc_detail[1]}")
                    else:
                        print(f"       ❌ No accessories found")
            else:
                print(f"   ❌ Not found: {tshirt_name}")
            print()
        
        # Test common T-shirt patterns
        print("2. Searching for T-shirt patterns...")
        patterns = [
            "Nightlife%T-Shirt%",
            "T-Shirt%Playboard%",
            "%T-Shirt%"
        ]
        
        for pattern in patterns:
            cursor.execute("SELECT PRODUCT_ID, PRODUCT_NAME FROM SAP_ELECTRONICS_PRODUCTS_2211_V2 WHERE UPPER(PRODUCT_NAME) LIKE UPPER(?) LIMIT 5", (pattern,))
            results = cursor.fetchall()
            
            print(f"Pattern '{pattern}': {len(results)} results")
            for result in results:
                product_id = result[0]
                product_name = result[1]
                
                # Check accessories
                cursor.execute("SELECT PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE TRIM(PRODUCT_ID) = ?", (product_id,))
                acc_result = cursor.fetchone()
                
                has_accessories = "✅" if (acc_result and acc_result[0]) else "❌"
                print(f"   {has_accessories} {product_name} (ID: {product_id})")
            print()
        
        # Test the exact IDs from our universal test
        print("3. Testing known T-shirt IDs with accessories...")
        known_tshirt_ids = [
            "104176",  # Nightlife T-Shirt Women
            "300464995",  # Nightlife T-Shirt Women violet M
            "300046036",  # T-Shirt Men Playboard Flower SS black L
            "300046037",  # T-Shirt Men Playboard Flower SS black M
        ]
        
        for product_id in known_tshirt_ids:
            cursor.execute("SELECT PRODUCT_NAME FROM SAP_ELECTRONICS_PRODUCTS_2211_V2 WHERE PRODUCT_ID = ?", (product_id,))
            result = cursor.fetchone()
            
            if result:
                product_name = result[0]
                cursor.execute("SELECT PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE TRIM(PRODUCT_ID) = ?", (product_id,))
                acc_result = cursor.fetchone()
                
                if acc_result and acc_result[0]:
                    accessory_ids = [pid.strip() for pid in acc_result[0].split(',') if pid.strip()]
                    print(f"   ✅ {product_name}")
                    print(f"       🎯 {len(accessory_ids)} accessories: {', '.join(accessory_ids)}")
                else:
                    print(f"   ❌ {product_name} - No accessories")
            else:
                print(f"   ❓ Product ID {product_id} not found")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 50)
        print("🎯 T-shirt Accessory Debug Complete!")
        
    except Exception as e:
        print(f"❌ Error during T-shirt debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_tshirt_accessories()