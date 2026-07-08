from hdbcli import dbapi

conn = dbapi.connect(
    address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
    port=443,
    user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
    password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
    encrypt=True,
    sslValidateCertificate=False
)
print('Connected OK')
cur = conn.cursor()
cur.execute("SELECT TABLE_NAME FROM TABLES WHERE TABLE_NAME LIKE 'SAP_BUNNINGS%'")
existing = cur.fetchall()
print('Existing SAP_BUNNINGS* tables:', existing)

# Also quick-check embedding works
from ecom_llm import get_google_embedding
emb = get_google_embedding('test bunnings product')
print(f'Embedding dims: {len(emb) if emb else "FAILED"}')
conn.close()
