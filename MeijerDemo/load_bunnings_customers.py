"""
Create SAP_BUNNINGS_CUSTOMERS_V1 in HANA and load bunnings_customers.csv.
Passwords are stored as Werkzeug pbkdf2:sha256 hashes (same as Flask standard).
Run: .\\venv\\Scripts\\python.exe load_bunnings_customers.py
"""
import csv, os, sys

def main():
    from agent import hana_connect
    from werkzeug.security import generate_password_hash

    CSV_PATH = os.path.join("data", "bunnings_customers.csv")
    if not os.path.exists(CSV_PATH):
        print("ERROR: data/bunnings_customers.csv not found")
        sys.exit(1)

    conn = hana_connect()
    cursor = conn.cursor()

    # ── drop & recreate ───────────────────────────────────────────────────────
    print("Creating SAP_BUNNINGS_CUSTOMERS_V1 ...")
    try:
        cursor.execute("DROP TABLE SAP_BUNNINGS_CUSTOMERS_V1 CASCADE")
        print("  Dropped existing table")
    except Exception:
        print("  No existing table to drop")

    cursor.execute("""
        CREATE TABLE SAP_BUNNINGS_CUSTOMERS_V1 (
            CUSTOMER_ID   NVARCHAR(100) NOT NULL PRIMARY KEY,
            CUSTOMER_NAME NVARCHAR(100) NOT NULL,
            PASSWORD_HASH NVARCHAR(256) NOT NULL,
            GENDER        NVARCHAR(10),
            AGE           INTEGER,
            PHONE         NVARCHAR(30),
            CITY          NVARCHAR(60),
            INTEREST      NVARCHAR(200)
        )
    """)
    print("  Table created")

    # ── load CSV ──────────────────────────────────────────────────────────────
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            pw_hash = generate_password_hash(r["PASSWORD"])
            rows.append((
                r["CUSTOMER_ID"].strip(),
                r["CUSTOMER_NAME"].strip(),
                pw_hash,
                r.get("GENDER", ""),
                int(r["AGE"]) if r.get("AGE") else None,
                r.get("PHONE", ""),
                r.get("CITY", ""),
                r.get("INTEREST", ""),
            ))

    print(f"  Inserting {len(rows)} customers ...")
    cursor.executemany(
        "INSERT INTO SAP_BUNNINGS_CUSTOMERS_V1 VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM SAP_BUNNINGS_CUSTOMERS_V1")
    print(f"  Loaded {cursor.fetchone()[0]} rows")

    cursor.close()
    conn.close()
    print("Done!")

if __name__ == "__main__":
    main()
