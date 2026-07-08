"""
load_meijer_crosssell.py
Creates SAP_MEIJER_CROSSSELL_V1 in SAP HANA and loads data/Meijer_crosssell.csv into it.

Run: .\\venv\\Scripts\\python.exe load_meijer_crosssell.py
"""

import csv
import os
import sys

from agent import hana_connect

CROSSSELL_TABLE = "SAP_MEIJER_CROSSSELL_V1"
CROSSSELL_CSV   = os.path.join("data", "Meijer_crosssell.csv")


def drop_table(cursor, table_name):
    try:
        cursor.execute(f"DROP TABLE {table_name} CASCADE")
        print(f"  🗑️  Dropped existing table {table_name}")
    except Exception:
        print(f"  ℹ️  Table {table_name} does not exist yet – will create fresh")


def load_crosssell(conn):
    print(f"\n{'='*65}")
    print(f"🔗  CROSSSELL  →  {CROSSSELL_TABLE}")
    print(f"{'='*65}")

    if not os.path.exists(CROSSSELL_CSV):
        print(f"❌ {CROSSSELL_CSV} not found – aborting")
        return

    cursor = conn.cursor()
    drop_table(cursor, CROSSSELL_TABLE)

    cursor.execute(f"""
        CREATE TABLE {CROSSSELL_TABLE} (
            PRODUCT_ID         NVARCHAR(50)  NOT NULL,
            RELATED_PRODUCT_ID NVARCHAR(50)  NOT NULL,
            RELATION_TYPE      NVARCHAR(20)  NOT NULL,
            DISPLAY_ORDER      INTEGER       NOT NULL,
            PRIMARY KEY (PRODUCT_ID, RELATED_PRODUCT_ID, RELATION_TYPE)
        )
    """)
    print(f"  ✅ Table {CROSSSELL_TABLE} created")

    rows = []
    skipped = 0
    with open(CROSSSELL_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append((
                    r["PRODUCT_ID"].strip(),
                    r["RELATED_PRODUCT_ID"].strip(),
                    r["RELATION_TYPE"].strip(),
                    int(r["DISPLAY_ORDER"]),
                ))
            except (KeyError, ValueError) as e:
                print(f"  ⚠️  Skipping bad row: {r}  ({e})")
                skipped += 1

    print(f"  📦 Inserting {len(rows):,} rows ...")
    cursor.executemany(
        f"INSERT INTO {CROSSSELL_TABLE} VALUES (?,?,?,?)",
        rows
    )
    conn.commit()

    cursor.execute(f"SELECT COUNT(*) FROM {CROSSSELL_TABLE}")
    print(f"  ✅ Loaded {cursor.fetchone()[0]:,} rows into {CROSSSELL_TABLE}")
    if skipped:
        print(f"  ⚠️  Skipped {skipped} malformed rows")

    # Breakdown by relation type
    cursor.execute(f"""
        SELECT RELATION_TYPE, COUNT(*) AS CNT
        FROM {CROSSSELL_TABLE}
        GROUP BY RELATION_TYPE
        ORDER BY CNT DESC
    """)
    print("  📊 Breakdown by relation type:")
    for relation_type, cnt in cursor.fetchall():
        print(f"     {relation_type:<12} → {cnt:>4} rows")

    cursor.close()


def main():
    print("\n🛒  Meijer Crosssell Loader")
    print("=" * 65)

    conn = hana_connect()
    if not conn:
        print("❌ Could not connect to HANA – aborting")
        sys.exit(1)

    load_crosssell(conn)

    conn.close()
    print(f"\n{'='*65}")
    print("🎉  SAP_MEIJER_CROSSSELL_V1 created and loaded successfully!")
    print("=" * 65)


if __name__ == "__main__":
    main()
