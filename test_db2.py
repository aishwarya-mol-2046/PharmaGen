import sqlite3
import sys
from backend.app.services.vcf_parser import VariantAnnotationEngine
conn = sqlite3.connect('backend/data/raw/clinical_kb.db')
c = conn.cursor()

def trace_match(gene, mutation, cursor):
    cursor.execute("PRAGMA table_info(variant_evidence)")
    columns = [col[1].lower() for col in cursor.fetchall()]
    mut_col = "mutation"
    if "variant" in columns: mut_col = "variant"
    elif "alteration" in columns: mut_col = "alteration"
    query = f"SELECT DISTINCT disease, therapy, evidence_tier, source FROM variant_evidence WHERE UPPER(gene) = UPPER(?) AND UPPER({mut_col}) = UPPER(?)"
    cursor.execute(query, (gene, mutation))
    rows = cursor.fetchall()
    print("Exact match rows:", rows)

trace_match('ALK', 'I1171N AND HIP1::ALK FUSION', c)
