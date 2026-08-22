import sqlite3
conn = sqlite3.connect('backend/data/raw/clinical_kb.db')
c = conn.cursor()
m = 'I1171N AND HIP1::ALK FUSION'
c.execute("SELECT mutation FROM variant_evidence WHERE UPPER(mutation)=UPPER(?)", (m,))
print("Query result:", c.fetchall())
