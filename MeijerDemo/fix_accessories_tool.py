"""
Quick script to update find_accessories tool to use SAP_ELECTRONICS_ACCESSORIES_V2 table
"""

# Read the file
with open('agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the old table name with new one in find_accessories function
content = content.replace('SAP_ACCESSORIES_COMMERCE_2211', 'SAP_ELECTRONICS_ACCESSORIES_V2')

# Also need to update the query logic since the table structure is different
# The old code queried for PRODUCT_IDS column, but new table has individual rows

old_query_logic = '''                try:
                    # Try exact match with debug
                    query_sql = "SELECT PRODUCT_IDS FROM SAP_ELECTRONICS_ACCESSORIES_V2 WHERE TRIM(PRODUCT_ID) = ?"'''

new_query_logic = '''                try:
                    # Query accessories directly from the new table structure
                    query_sql = """
                        SELECT PRODUCT_ID, PRODUCT_NAME, ACCESSORY_ID, ACCESSORY_NAME, 
                               ACCESSORY_CATEGORY, ACCESSORY_PRICE, ACCESSORY_IMAGE
                        FROM SAP_ELECTRONICS_ACCESSORIES_V2
                        WHERE TRIM(PRODUCT_ID) = ?
                        ORDER BY ACCESSORY_CATEGORY, ACCESSORY_PRICE
                    "''"""'''

if old_query_logic in content:
    content = content.replace(old_query_logic, new_query_logic)
    print("✅ Updated query logic")
else:
    print("⚠️ Could not find old query logic to replace")

# Write back
with open('agent.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Updated agent.py to use SAP_ELECTRONICS_ACCESSORIES_V2")
print("Note: Manual review recommended for full query logic update")
