import io
import os
import re
import sqlite3
import zipfile
from pathlib import Path
import pandas as pd
import requests

DB_PATH = str(Path(__file__).resolve().parents[2] / "data" / "raw" / "clinical_kb.db")
CIVIC_URL = "https://civicdb.org/downloads/nightly/nightly-ClinicalEvidenceSummaries.tsv"
PHARMGKB_URLS = [
    "https://api.clinpgx.org/v1/download/file/data/clinicalAnnotations.zip",
    "https://api.pharmgkb.org/v1/download/file/data/clinicalAnnotations.zip",
]


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS variant_evidence (
            gene TEXT,
            mutation TEXT,
            disease TEXT,
            therapy TEXT,
            evidence_tier TEXT,
            source TEXT,
            PRIMARY KEY (gene, mutation, therapy, disease, source)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_var_ev_gene_mut ON variant_evidence (gene, mutation)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_var_ev_gene ON variant_evidence (gene)")
    conn.commit()
    return conn


def init_real_civic_db(conn=None):
    owns_conn = conn is None
    conn = _get_connection() if owns_conn else conn
    cursor = conn.cursor()

    print("Fetching live CIViC database release...")
    try:
        df = pd.read_csv(CIVIC_URL, sep="\t", low_memory=False)

        cols = {c.lower(): c for c in df.columns}
        disease_col = cols.get("disease", cols.get("disease_name"))
        drug_col = cols.get("therapies", cols.get("drugs", cols.get("therapy")))
        level_col = cols.get("evidence_level", cols.get("evidence_direction"))
        mp_col = cols.get("molecular_profile", cols.get("variant"))
        gene_col = cols.get("gene", cols.get("feature_name"))

        records = []
        if mp_col and disease_col and drug_col:
            clean_df = df.dropna(subset=[mp_col, disease_col, drug_col])
            for _, row in clean_df.iterrows():
                mp_str = str(row[mp_col]).strip().upper()
                parts = mp_str.split(" ", 1)
                gene = parts[0] if len(parts) > 0 else "UNKNOWN"
                mutation = parts[1] if len(parts) > 1 else mp_str
                records.append((
                    gene,
                    mutation,
                    str(row[disease_col]).strip(),
                    str(row[drug_col]).strip(),
                    f"Level {row[level_col]}" if level_col and pd.notna(row[level_col]) else "Level A",
                    "CIViC Database",
                ))
        elif gene_col and disease_col and drug_col:
            clean_df = df.dropna(subset=[gene_col, disease_col, drug_col])
            var_col = cols.get("variant", cols.get("variant_name", gene_col))
            for _, row in clean_df.iterrows():
                records.append((
                    str(row[gene_col]).strip().upper(),
                    str(row[var_col]).strip().upper(),
                    str(row[disease_col]).strip(),
                    str(row[drug_col]).strip(),
                    f"Level {row[level_col]}" if level_col and pd.notna(row[level_col]) else "Level A",
                    "CIViC Database",
                ))
        else:
            raise KeyError(f"Could not map columns. Available: {list(df.columns)}")

        cursor.executemany("""
            INSERT OR REPLACE INTO variant_evidence 
            (gene, mutation, disease, therapy, evidence_tier, source) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, records)
        conn.commit()
        print(f"Successfully loaded {len(records)} live clinical records from CIViC into SQLite!")

    except Exception as e:
        print(f"CIViC fetch warning ({e}). Loading fallback core panel...")
        fallback = [
            ("BRAF", "V600E", "Melanoma", "Vemurafenib", "Level A", "CIViC"),
            ("EGFR", "L858R", "Non-Small Cell Lung Cancer", "Osimertinib", "Level A", "CIViC"),
            ("KRAS", "G12C", "Non-Small Cell Lung Cancer", "Sotorasib", "Level A", "CIViC"),
            ("ERBB2", "AMPLIFICATION", "Breast Cancer", "Trastuzumab", "Level A", "CIViC"),
        ]
        cursor.executemany("INSERT OR REPLACE INTO variant_evidence VALUES (?,?,?,?,?,?)", fallback)
        conn.commit()

    if owns_conn:
        conn.close()


def init_pharmgkb_db(conn=None, zip_path=None):
    """Downloads or extracts PharmGKB/ClinPGx clinical annotations into SQLite."""
    owns_conn = conn is None
    conn = _get_connection() if owns_conn else conn
    cursor = conn.cursor()

    print("Fetching PharmGKB / ClinPGx clinical annotations...")
    records = []
    try:
        content_bytes = None
        if zip_path and os.path.exists(zip_path):
            with open(zip_path, "rb") as f:
                content_bytes = f.read()
        else:
            headers = {"User-Agent": "Mozilla/5.0"}
            for url in PHARMGKB_URLS:
                try:
                    resp = requests.get(url, headers=headers, timeout=30)
                    if resp.status_code == 200 and resp.content:
                        content_bytes = resp.content
                        break
                except Exception:
                    continue

        if not content_bytes:
            raise RuntimeError("Could not download PharmGKB archive from any endpoint.")

        with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
            with z.open("clinical_annotations.tsv") as f:
                df = pd.read_csv(f, sep="\t", dtype=str, low_memory=False)

        for _, row in df.iterrows():
            genes_raw = str(row.get("Gene", "")).strip()
            variants_raw = str(row.get("Variant/Haplotypes", "")).strip()
            drugs_raw = str(row.get("Drug(s)", "")).strip()
            phenos_raw = str(row.get("Phenotype(s)", "")).strip()
            category = str(row.get("Phenotype Category", "Drug Response")).strip()
            level = str(row.get("Level of Evidence", "")).strip()

            if not genes_raw or genes_raw.lower() == "nan":
                continue
            if not drugs_raw or drugs_raw.lower() == "nan":
                continue
            if not variants_raw or variants_raw.lower() == "nan":
                continue

            disease_val = phenos_raw if phenos_raw and phenos_raw.lower() != "nan" else category
            if not disease_val or disease_val.lower() == "nan":
                disease_val = "Drug Response / Toxicity"

            evidence_tier = f"PharmGKB Level {level}" if level and level.lower() != "nan" else "PharmGKB Level 3"

            # Split compound entries cleanly so individual gene-variant matches succeed
            gene_list = [g.strip().upper() for g in re.split(r"[,;]+", genes_raw) if g.strip()]
            drug_list = [d.strip() for d in drugs_raw.split(";") if d.strip()]

            for g in gene_list:
                raw_tokens = [v.strip().upper() for v in re.split(r"[,;]+", variants_raw) if v.strip()]
                var_set = set(raw_tokens)
                for tok in raw_tokens:
                    if tok.startswith(f"{g}*"):
                        var_set.add(tok[len(g):])
                    elif tok.startswith("*"):
                        var_set.add(f"{g}{tok}")

                for v in var_set:
                    for d in drug_list:
                        records.append((
                            g,
                            v,
                            disease_val,
                            d,
                            evidence_tier,
                            "PharmGKB",
                        ))

        cursor.executemany("""
            INSERT OR REPLACE INTO variant_evidence 
            (gene, mutation, disease, therapy, evidence_tier, source) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, records)
        conn.commit()
        print(f"Successfully loaded {len(records)} clinical records from PharmGKB into SQLite!")

    except Exception as e:
        print(f"PharmGKB fetch warning ({e}). Loading curated PGx core panel...")
        fallback = [
            ("CYP2C19", "*2", "Poor Clopidogrel Metabolism / High Thrombosis Risk", "Clopidogrel", "PharmGKB Level 1A", "PharmGKB"),
            ("CYP2C19", "*3", "Poor Clopidogrel Metabolism / High Thrombosis Risk", "Clopidogrel", "PharmGKB Level 1A", "PharmGKB"),
            ("CYP2C19", "RS4244285", "Poor Clopidogrel Metabolism / High Thrombosis Risk", "Clopidogrel", "PharmGKB Level 1A", "PharmGKB"),
            ("CYP2D6", "*4", "Poor Codeine Metabolism / Reduced Analgesia", "Codeine", "PharmGKB Level 1A", "PharmGKB"),
            ("CYP2D6", "*10", "Altered Tamoxifen Metabolism / Reduced Efficacy", "Tamoxifen", "PharmGKB Level 1A", "PharmGKB"),
            ("DPYD", "*2A", "Severe 5-FU Toxicity & Myelosuppression", "Fluorouracil", "PharmGKB Level 1A", "PharmGKB"),
            ("DPYD", "C.1905+1G>A", "Severe 5-FU Toxicity & Myelosuppression", "Capecitabine", "PharmGKB Level 1A", "PharmGKB"),
            ("DPYD", "RS3918290", "Severe 5-FU Toxicity & Myelosuppression", "Fluorouracil", "PharmGKB Level 1A", "PharmGKB"),
            ("VKORC1", "RS9923231", "Increased Warfarin Sensitivity / Bleeding Risk", "Warfarin", "PharmGKB Level 1A", "PharmGKB"),
            ("CYP2C9", "*2", "Decreased Warfarin Clearance / Bleeding Risk", "Warfarin", "PharmGKB Level 1A", "PharmGKB"),
            ("CYP2C9", "*3", "Decreased Warfarin Clearance / Bleeding Risk", "Warfarin", "PharmGKB Level 1A", "PharmGKB"),
            ("TPMT", "*3A", "Severe Myelosuppression / Thiopurine Toxicity", "Azathioprine", "PharmGKB Level 1A", "PharmGKB"),
            ("TPMT", "*3C", "Severe Myelosuppression / Thiopurine Toxicity", "Mercaptopurine", "PharmGKB Level 1A", "PharmGKB"),
            ("SLCO1B1", "*5", "Statin-Induced Myopathy / Rhabdomyolysis", "Simvastatin", "PharmGKB Level 1A", "PharmGKB"),
            ("SLCO1B1", "RS4149056", "Statin-Induced Myopathy / Rhabdomyolysis", "Simvastatin", "PharmGKB Level 1A", "PharmGKB"),
            ("HLA-B", "*57:01", "Severe Abacavir Hypersensitivity Reaction", "Abacavir", "PharmGKB Level 1A", "PharmGKB"),
            ("HLA-B", "*15:02", "Stevens-Johnson Syndrome / Toxic Epidermal Necrolysis", "Carbamazepine", "PharmGKB Level 1A", "PharmGKB"),
        ]
        cursor.executemany("INSERT OR REPLACE INTO variant_evidence VALUES (?,?,?,?,?,?)", fallback)
        conn.commit()

    if owns_conn:
        conn.close()


def bootstrap_all():
    conn = _get_connection()
    init_real_civic_db(conn=conn)
    init_pharmgkb_db(conn=conn)
    conn.close()


if __name__ == "__main__":
    bootstrap_all()