import sqlite3
conn = sqlite3.connect('backend/data/raw/clinical_kb.db')
c = conn.cursor()
c.execute("SELECT mutation FROM variant_evidence WHERE gene='ATM' AND mutation LIKE '7089+1DEL%'")
print("In DB:", c.fetchall())

from backend.app.services.vcf_parser import VariantAnnotationEngine
# what does the parser do to 7089+1DEL?
m = "7089+1DEL"
mut_norm = m.strip()
if ":" in mut_norm:
    mut_norm = mut_norm.split(":", 1)[-1]
if mut_norm.upper().startswith("P.") or mut_norm.upper().startswith("C."):
    mut_norm = mut_norm[2:]
for three_let, one_let in {"Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", 
    "Glu": "E", "Gln": "Q", "Gly": "G", "His": "H", "Ile": "I", 
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P", 
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V"}.items():
    if three_let in mut_norm:
        mut_norm = mut_norm.replace(three_let, one_let)
print("Parser output:", mut_norm)

