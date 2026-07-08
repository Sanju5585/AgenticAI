"""
Create SAP_BUNNINGS_CROSSSELL_V1 table in HANA and load crosssell_products.csv.
Run once: .\venv\Scripts\python.exe load_crosssell.py
"""
import csv, os, sys

def main():
    from agent import hana_connect

    CSV_PATH = os.path.join("data", "crosssell_products.csv")
    if not os.path.exists(CSV_PATH):
        print("❌ crosssell_products.csv not found — run generate_crosssell_csv.py first")
        sys.exit(1)

    conn = hana_connect()
    cursor = conn.cursor()

    # ── create table ──────────────────────────────────────────────────────────
    print("📋 Creating SAP_BUNNINGS_CROSSSELL_V1 table (DROP IF EXISTS)...")
    try:
        cursor.execute("DROP TABLE SAP_BUNNINGS_CROSSSELL_V1 CASCADE")
        print("   Dropped existing table")
    except Exception:
        print("   No existing table to drop")

    cursor.execute("""
        CREATE TABLE SAP_BUNNINGS_CROSSSELL_V1 (
            PRODUCT_ID         NVARCHAR(50)  NOT NULL,
            RELATED_PRODUCT_ID NVARCHAR(50)  NOT NULL,
            RELATION_TYPE      NVARCHAR(20)  NOT NULL,
            DISPLAY_ORDER      INTEGER       NOT NULL,
            PRIMARY KEY (PRODUCT_ID, RELATED_PRODUCT_ID, RELATION_TYPE)
        )
    """)
    print("   Table created ✅")

    # ── load CSV ──────────────────────────────────────────────────────────────
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [
            (r["PRODUCT_ID"], r["RELATED_PRODUCT_ID"],
             r["RELATION_TYPE"], int(r["DISPLAY_ORDER"]))
            for r in reader
        ]

    print(f"📦 Inserting {len(rows):,} rows...")
    cursor.executemany(
        "INSERT INTO SAP_BUNNINGS_CROSSSELL_V1 VALUES (?,?,?,?)",
        rows
    )
    conn.commit()

    # ── verify ────────────────────────────────────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM SAP_BUNNINGS_CROSSSELL_V1")
    count = cursor.fetchone()[0]
    print(f"✅ Loaded {count:,} rows into SAP_BUNNINGS_CROSSSELL_V1")

    cursor.execute("""
        SELECT RELATION_TYPE, COUNT(*) AS CNT
        FROM SAP_BUNNINGS_CROSSSELL_V1
        GROUP BY RELATION_TYPE
        ORDER BY CNT DESC
    """)
    for rel, cnt in cursor.fetchall():
        print(f"   {rel}: {cnt:,}")

    cursor.close()
    conn.close()
    print("🎉 Done!")

if __name__ == "__main__":
    main()
