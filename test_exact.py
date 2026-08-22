import sqlite3
conn = sqlite3.connect('backend/data/raw/clinical_kb.db')
c = conn.cursor()
c.execute("SELECT DISTINCT disease, therapy, evidence_tier, source FROM variant_evidence WHERE UPPER(gene) = UPPER(?) AND UPPER(mutation) = UPPER(?)", ('ALK', 'I1171N AND HIP1::ALK FUSION'))
print(c.fetchall())
