"""
Creates SAP_TWININGS_ORDERS_V1 in HANA.
One row per line item — multiple rows share the same ORDER_ID for multi-product orders.
Run: .\\venv\\Scripts\\python.exe create_twinings_orders_table.py
"""

def main():
    from agent import hana_connect
    conn = hana_connect()
    cursor = conn.cursor()

    print("Creating SAP_TWININGS_ORDERS_V1 ...")
    try:
        cursor.execute("DROP TABLE SAP_TWININGS_ORDERS_V1 CASCADE")
        print("  Dropped existing table")
    except Exception:
        print("  No existing table to drop")

    cursor.execute("""
        CREATE TABLE SAP_TWININGS_ORDERS_V1 (
            ORDER_ID        NVARCHAR(20)    NOT NULL,
            LINE_ITEM_ID    INTEGER         NOT NULL,
            CUSTOMER_ID     NVARCHAR(100)   NOT NULL,
            PRODUCT_ID      NVARCHAR(50),
            PRODUCT_NAME    NVARCHAR(500),
            QUANTITY        INTEGER         DEFAULT 1,
            UNIT_PRICE      DECIMAL(10,2),
            LINE_TOTAL      DECIMAL(10,2),
            ORDER_STATUS    NVARCHAR(50)    DEFAULT 'Open',
            ORDER_DATE      NVARCHAR(30),
            IMAGE_URL       NVARCHAR(1000),
            PRIMARY KEY (ORDER_ID, LINE_ITEM_ID)
        )
    """)
    conn.commit()
    print("  Table SAP_TWININGS_ORDERS_V1 created successfully")

    cursor.close()
    conn.close()
    print("Done!")

if __name__ == "__main__":
    main()
