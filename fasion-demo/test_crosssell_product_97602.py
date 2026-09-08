"""
Test cross-sell products for product 97602
"""

from agent import hana_connect

def test_product_97602_crosssell():
    """Check if product 97602 has cross-sell products"""
    
    print("="*80)
    print("Testing Cross-Sell for Product 97602")
    print("="*80)
    
    conn = hana_connect()
    cursor = conn.cursor()
    
    # Check if product exists
    cursor.execute("""
        SELECT PRODUCT_ID, PRODUCT_NAME, PRICE 
        FROM SAP_PRODUCTS_COMMERCE_2211_V2 
        WHERE TRIM(PRODUCT_ID) = ?
    """, ['97602'])
    
    product = cursor.fetchone()
    if product:
        print(f"\n✅ Product Found:")
        print(f"   ID: {product[0]}")
        print(f"   Name: {product[1]}")
        print(f"   Price: £{product[2]}")
    else:
        print("\n❌ Product 97602 not found!")
        cursor.close()
        conn.close()
        return
    
    # Check cross-sell relationships
    cursor.execute("""
        SELECT 
            cs.SOURCE_PRODUCT_ID,
            cs.CROSS_SELL_PRODUCT_ID,
            cs.RELATIONSHIP_TYPE,
            cs.PRIORITY,
            p.PRODUCT_NAME,
            p.PRICE
        FROM SAP_PRODUCT_CROSS_SELL_V2 cs
        JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p 
            ON TRIM(cs.CROSS_SELL_PRODUCT_ID) = TRIM(p.PRODUCT_ID)
        WHERE TRIM(cs.SOURCE_PRODUCT_ID) = ?
        ORDER BY cs.PRIORITY
    """, ['97602'])
    
    crosssell_products = cursor.fetchall()
    
    print(f"\n📦 Cross-Sell Products Found: {len(crosssell_products)}")
    print("-"*80)
    
    if crosssell_products:
        for idx, row in enumerate(crosssell_products, 1):
            print(f"\n{idx}. Cross-Sell Product:")
            print(f"   Source Product: {row[0]}")
            print(f"   Cross-Sell ID: {row[1]}")
            print(f"   Relationship: {row[2]}")
            print(f"   Priority: {row[3]}")
            print(f"   Name: {row[4]}")
            print(f"   Price: £{row[5]}")
    else:
        print("\n❌ No cross-sell products found for product 97602!")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*80)
    print(f"Total Cross-Sell Products: {len(crosssell_products)}")
    print("="*80)

if __name__ == "__main__":
    test_product_97602_crosssell()
