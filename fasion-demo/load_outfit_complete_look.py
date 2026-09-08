"""
Load outfit_complete_look.csv into SAP HANA as OUTFIT_COMPLETE_LOOK table.

Table schema:
  RULE_ID            INTEGER  (auto-incremented via sequence or plain counter)
  SOURCE_CATEGORY    NVARCHAR(50)   e.g. 'jacket', 'tshirt', 'dress'
  SOURCE_PRODUCT_IDS NCLOB          comma-separated product IDs that belong to this category
  LOOK_LABEL         NVARCHAR(100)  e.g. 'Complete the Look'
  COMPLEMENT_CATEGORY NVARCHAR(50)  e.g. 'pants', 'sunglasses'
  COMPLEMENT_PRODUCT_IDS NCLOB      comma-separated product IDs to recommend
  COMPLEMENT_LABEL   NVARCHAR(100)  e.g. 'Add Trousers / Pants'
  PRIORITY           INTEGER        lower = shown first
"""

import csv
import sys
import os

# Make sure we can import agent.hana_connect
sys.path.insert(0, os.path.dirname(__file__))

from agent import hana_connect

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "outfit_complete_look.csv")
TABLE_NAME = "OUTFIT_COMPLETE_LOOK"


def create_table(cursor):
    drop_sql = f"DROP TABLE {TABLE_NAME}"
    try:
        cursor.execute(drop_sql)
        print(f"🗑  Dropped existing {TABLE_NAME}")
    except Exception:
        pass  # table didn't exist yet

    create_sql = f"""
    CREATE TABLE {TABLE_NAME} (
        RULE_ID              INTEGER,
        SOURCE_CATEGORY      NVARCHAR(50),
        SOURCE_PRODUCT_IDS   NCLOB,
        LOOK_LABEL           NVARCHAR(100),
        COMPLEMENT_CATEGORY  NVARCHAR(50),
        COMPLEMENT_PRODUCT_IDS NCLOB,
        COMPLEMENT_LABEL     NVARCHAR(100),
        PRIORITY             INTEGER
    )
    """
    cursor.execute(create_sql)
    print(f"✅ Created table {TABLE_NAME}")


def load_csv(cursor):
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    insert_sql = f"""
    INSERT INTO {TABLE_NAME}
        (RULE_ID, SOURCE_CATEGORY, SOURCE_PRODUCT_IDS, LOOK_LABEL,
         COMPLEMENT_CATEGORY, COMPLEMENT_PRODUCT_IDS, COMPLEMENT_LABEL, PRIORITY)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    inserted = 0
    for i, row in enumerate(rows, 1):
        params = (
            i,
            row["SOURCE_CATEGORY"].strip(),
            row["SOURCE_PRODUCT_IDS"].strip(),
            row["LOOK_LABEL"].strip(),
            row["COMPLEMENT_CATEGORY"].strip(),
            row["COMPLEMENT_PRODUCT_IDS"].strip(),
            row["COMPLEMENT_LABEL"].strip(),
            int(row["PRIORITY"].strip()),
        )
        cursor.execute(insert_sql, params)
        inserted += 1
        print(f"  Inserted rule {i}: {row['SOURCE_CATEGORY']} → {row['COMPLEMENT_CATEGORY']} (priority {row['PRIORITY']})")

    return inserted


def main():
    print("🔌 Connecting to SAP HANA …")
    conn = hana_connect()
    cursor = conn.cursor()

    print(f"\n📋 Creating table {TABLE_NAME} …")
    create_table(cursor)

    print(f"\n📥 Loading {CSV_PATH} …")
    count = load_csv(cursor)

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n✅ Done — {count} outfit rules loaded into {TABLE_NAME}")


if __name__ == "__main__":
    main()
