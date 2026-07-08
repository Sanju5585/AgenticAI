"""
Reload only SAP_TWININGS_PRODUCTS_V1 and SAP_TWININGS_CROSSSELL_V1
without touching customers or categories.
Run: .\\venv\\Scripts\\python.exe reload_products_crosssell.py
"""
import sys
from load_twinings_data import load_products, load_crosssell
from agent import hana_connect

def main():
    print("\n🍵  Reloading Products + Crosssell")
    print("=" * 65)
    conn = hana_connect()
    if not conn:
        print("❌ Could not connect to HANA – aborting")
        sys.exit(1)
    load_crosssell(conn)
    load_products(conn)   # last – most time-consuming (embeddings)
    conn.close()
    print("\n🎉  Done!")

if __name__ == "__main__":
    main()
