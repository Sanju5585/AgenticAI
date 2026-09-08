"""
Clear existing V2 tables to reload with optimized version
"""
from hdbcli import dbapi

def connect_db():
    return dbapi.connect(
        address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
        port='443',
        user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
        password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
        encrypt=True,
        sslValidateCertificate=False
    )

print("🗑️  Clearing existing V2 table data...")

conn = connect_db()
cursor = conn.cursor()

# Clear products and accessories (keep promotions)
cursor.execute("DELETE FROM SAP_PRODUCTS_COMMERCE_2211_V2")
print("✅ Cleared products")

cursor.execute("DELETE FROM SAP_ACCESSORIES_COMMERCE_2211_V2")
print("✅ Cleared accessories")

conn.commit()
cursor.close()
conn.close()

print("\n✅ Ready for optimized reload!")
