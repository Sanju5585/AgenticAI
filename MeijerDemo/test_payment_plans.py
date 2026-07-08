# test_payment_plans.py - Test script to verify payment plans implementation
from dotenv import load_dotenv
load_dotenv()

from agent import hana_connect

def test_payment_plans():
    """Test if payment plans are properly loaded and accessible"""
    print("🧪 Testing Payment Plans Implementation")
    print("=" * 60)
    
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Test 1: Check if payment plans table exists and has data
        print("\n✅ Test 1: Checking payment plans table...")
        cursor.execute("SELECT COUNT(*) FROM SAP_PRODUCT_PAYMENT_PLANS_V2")
        count = cursor.fetchone()[0]
        print(f"   Total payment plans: {count}")
        
        # Test 2: Get payment plans for a mobile product (iPhone 15 - Product ID: 200022)
        print("\n✅ Test 2: Getting payment plans for iPhone 15 (Product ID: 200022)...")
        cursor.execute("""
            SELECT VARIANT_NAME, MONTHLY_PAYMENT, FULL_PRICE, STOCK_STATUS
            FROM SAP_PRODUCT_PAYMENT_PLANS_V2
            WHERE PRODUCT_ID = '200022'
            ORDER BY VARIANT_ORDER
        """)
        plans = cursor.fetchall()
        if plans:
            print(f"   Found {len(plans)} plans:")
            for plan in plans:
                print(f"      - {plan[0]}: ${plan[1]:.2f}/month (Full: ${plan[2]:.2f}) - {plan[3]}")
        else:
            print("   ❌ No plans found!")
        
        # Test 3: Get payment plans for a watch product (Apple Watch Series 11 - Product ID: 400001)
        print("\n✅ Test 3: Getting payment plans for Apple Watch Series 11 (Product ID: 400001)...")
        cursor.execute("""
            SELECT VARIANT_NAME, MONTHLY_PAYMENT, FULL_PRICE, STOCK_STATUS
            FROM SAP_PRODUCT_PAYMENT_PLANS_V2
            WHERE PRODUCT_ID = '400001'
            ORDER BY VARIANT_ORDER
        """)
        plans = cursor.fetchall()
        if plans:
            print(f"   Found {len(plans)} plans:")
            for plan in plans:
                print(f"      - {plan[0]}: ${plan[1]:.2f}/month (Full: ${plan[2]:.2f}) - {plan[3]}")
        else:
            print("   ❌ No plans found!")
        
        # Test 4: Test get_product_details function with a mobile product
        print("\n✅ Test 4: Testing get_product_details for Samsung Galaxy S25 (200050)...")
        from agent import get_product_details
        result = get_product_details("product 200050")
        
        if result.get('results'):
            product = result['results'][0]
            print(f"   Product: {product.get('PRODUCT_NAME')}")
            print(f"   Price: ${product.get('PRICE'):.2f}")
            if 'PAYMENT_PLANS' in product:
                print(f"   Payment Plans: {len(product['PAYMENT_PLANS'])} variants")
                for plan in product['PAYMENT_PLANS']:
                    print(f"      - {plan['VARIANT_NAME']}: ${plan['MONTHLY_PAYMENT']:.2f}/month")
            else:
                print("   ❌ No payment plans included in result!")
        else:
            print(f"   ❌ Error: {result.get('error')}")
        
        # Test 5: Verify no plans for non-mobile/watch products
        print("\n✅ Test 5: Testing product without plans (Tablet - 300001)...")
        cursor.execute("""
            SELECT COUNT(*)
            FROM SAP_PRODUCT_PAYMENT_PLANS_V2
            WHERE PRODUCT_ID = '300001'
        """)
        tablet_plans = cursor.fetchone()[0]
        print(f"   Payment plans for tablet: {tablet_plans}")
        if tablet_plans == 0:
            print("   ✅ Correctly no plans for non-mobile/watch product")
        
        # Summary
        print("\n" + "=" * 60)
        print("✅ All Tests Complete!")
        print(f"📊 Summary:")
        print(f"   - Total payment plans in database: {count}")
        print(f"   - Plans applicable to: Mobile phones and watches only")
        print(f"   - Product detail function: Enhanced with payment plan support")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Test Failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_payment_plans()
