"""
Safe Script to Preview and Delete Last 4 Orders
This script allows you to preview orders before deletion with safety checks
"""

import configparser
from hdbcli import dbapi
from datetime import datetime
import sys

def hana_connect():
    """Establish connection to SAP HANA database"""
    conn = dbapi.connect(
        address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
        port='443',
        user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
        password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
        encrypt=True,
        autocommit=False,
        sslValidateCertificate=False,
    )
    return conn

def preview_orders(customer_id, limit=4):
    """Preview the last N orders for a customer"""
    conn = hana_connect()
    cursor = conn.cursor()
    
    # Get orders
    query = """
        SELECT ORDER_ID, PRODUCT_ID, PRODUCT_NAME, TOTAL_PRICE, ORDER_DATE, ORDER_STATUS
        FROM SAP_ORDERS_COMMERCE_2211_V2
        WHERE CUSTOMER_ID = ?
        ORDER BY ORDER_DATE DESC, ORDER_ID DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query, (customer_id,))
    orders = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return orders

def count_total_orders(customer_id):
    """Count total orders for a customer"""
    conn = hana_connect()
    cursor = conn.cursor()
    
    query = """
        SELECT COUNT(*) as total_orders, COUNT(DISTINCT ORDER_ID) as unique_orders
        FROM SAP_ORDERS_COMMERCE_2211_V2
        WHERE CUSTOMER_ID = ?
    """
    
    cursor.execute(query, (customer_id,))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return result[0], result[1]

def delete_orders_by_ids(customer_id, order_ids, dry_run=True):
    """Delete orders with specific ORDER_IDs"""
    conn = hana_connect()
    cursor = conn.cursor()
    
    deleted_count = 0
    
    for order_id in order_ids:
        if dry_run:
            # Just count what would be deleted
            count_query = """
                SELECT COUNT(*) FROM SAP_ORDERS_COMMERCE_2211_V2
                WHERE ORDER_ID = ? AND CUSTOMER_ID = ?
            """
            cursor.execute(count_query, (order_id, customer_id))
            count = cursor.fetchone()[0]
            deleted_count += count
            print(f"   [DRY RUN] Would delete {count} record(s) for ORDER_ID: {order_id}")
        else:
            # Actually delete
            delete_query = """
                DELETE FROM SAP_ORDERS_COMMERCE_2211_V2
                WHERE ORDER_ID = ? AND CUSTOMER_ID = ?
            """
            cursor.execute(delete_query, (order_id, customer_id))
            deleted_count += cursor.rowcount
            print(f"   ✓ Deleted {cursor.rowcount} record(s) for ORDER_ID: {order_id}")
    
    if not dry_run:
        conn.commit()
        print("\n   ✓ Transaction committed to database")
    else:
        print("\n   ℹ️  No changes made (dry run mode)")
    
    cursor.close()
    conn.close()
    
    return deleted_count

def display_orders_table(orders):
    """Display orders in a formatted table"""
    print("\n" + "=" * 100)
    print(f"{'ORDER_ID':<12} {'PRODUCT_ID':<15} {'PRODUCT_NAME':<35} {'PRICE':<12} {'DATE':<20}")
    print("=" * 100)
    
    for order in orders:
        order_id, product_id, product_name, price, order_date, status = order
        
        product_name_short = product_name[:32] + "..." if len(product_name) > 35 else product_name
        price_str = f"£{float(price):.2f}"
        date_str = str(order_date)[:19] if order_date else "N/A"
        
        print(f"{order_id:<12} {product_id:<15} {product_name_short:<35} {price_str:<12} {date_str:<20}")
    
    print("=" * 100)

def main():
    """Main interactive function"""
    customer_id = "william.hunter@pronto-hw.com"
    
    print("\n" + "=" * 100)
    print("  ORDER DELETION UTILITY - SAFE MODE")
    print("=" * 100)
    print(f"Customer: {customer_id}")
    print()
    
    # Get total order count
    print("📊 Fetching order statistics...")
    total_records, unique_orders = count_total_orders(customer_id)
    print(f"   Total order records: {total_records}")
    print(f"   Unique ORDER_IDs: {unique_orders}")
    print()
    
    # Preview last 4 orders
    print("📋 Previewing last 4 orders...")
    orders = preview_orders(customer_id, limit=4)
    
    if not orders:
        print("❌ No orders found for this customer.")
        return
    
    print(f"✓ Found {len(orders)} order record(s) to delete")
    display_orders_table(orders)
    
    # Get unique ORDER_IDs
    order_ids = sorted(set(order[0] for order in orders))
    print(f"\n📝 Unique ORDER_IDs to delete: {', '.join(order_ids)}")
    print(f"📝 Total records to delete: {len(orders)}")
    
    # Calculate totals
    total_amount = sum(float(order[3]) for order in orders)
    print(f"💰 Total amount of orders: £{total_amount:.2f}")
    print()
    
    # Menu
    while True:
        print("\n" + "-" * 100)
        print("OPTIONS:")
        print("  1. Dry Run - Preview deletion (no changes)")
        print("  2. Delete Orders - Permanently delete (requires confirmation)")
        print("  3. Show All Orders - View all orders for this customer")
        print("  4. Exit - Cancel and exit")
        print("-" * 100)
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == '1':
            # Dry run
            print("\n🔍 DRY RUN MODE - Simulating deletion...")
            print("=" * 100)
            deleted_count = delete_orders_by_ids(customer_id, order_ids, dry_run=True)
            print("=" * 100)
            print(f"✓ Dry run complete. Would delete {deleted_count} record(s)")
            print("ℹ️  No actual changes were made to the database")
            
        elif choice == '2':
            # Actual deletion
            print("\n⚠️  WARNING: PERMANENT DELETION")
            print("=" * 100)
            print("This will permanently delete the following orders:")
            print(f"  • Customer: {customer_id}")
            print(f"  • ORDER_IDs: {', '.join(order_ids)}")
            print(f"  • Total records: {len(orders)}")
            print("=" * 100)
            print()
            
            confirm1 = input("Type 'YES' to proceed: ").strip()
            if confirm1 != 'YES':
                print("❌ Deletion cancelled.")
                continue
            
            confirm2 = input("Type 'DELETE' to confirm: ").strip()
            if confirm2 != 'DELETE':
                print("❌ Deletion cancelled.")
                continue
            
            print("\n🗑️  Deleting orders...")
            print("=" * 100)
            deleted_count = delete_orders_by_ids(customer_id, order_ids, dry_run=False)
            print("=" * 100)
            
            print("\n✅ DELETION COMPLETE")
            print(f"   Deleted {deleted_count} record(s)")
            print(f"   ORDER_IDs removed: {', '.join(order_ids)}")
            print()
            print("   The orders have been permanently removed from the database.")
            break
            
        elif choice == '3':
            # Show all orders
            print("\n📋 All orders for customer...")
            all_orders = preview_orders(customer_id, limit=None)
            if all_orders:
                display_orders_table(all_orders)
                print(f"\nTotal: {len(all_orders)} order record(s)")
            else:
                print("❌ No orders found.")
                
        elif choice == '4':
            print("\n👋 Exiting without making changes.")
            break
            
        else:
            print("❌ Invalid option. Please select 1-4.")
    
    print("\n" + "=" * 100)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print("\n" + "=" * 100)
        print("❌ ERROR OCCURRED")
        print("=" * 100)
        print(f"Error: {str(e)}")
        print()
        print("Please check:")
        print("  1. Database connection is available")
        print("  2. Customer email is correct")
        print("  3. Database credentials are valid")
        print("=" * 100)
        import traceback
        traceback.print_exc()
        sys.exit(1)
