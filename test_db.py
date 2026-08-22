import sqlite3
from backend.app.services.vcf_parser import VariantAnnotationEngine
conn = sqlite3.connect('backend/data/raw/clinical_kb.db')
c = conn.cursor()
m = VariantAnnotationEngine.match_clinical_evidence('ALK', 'I1171N AND HIP1::ALK FUSION', cursor=c)
print(m)
