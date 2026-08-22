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

VIP_PGX_MAPPING = {
    ("CYP2C19", "*2"): "RS4244285",
    ("CYP2C19", "*3"): "RS4986893",
    ("CYP2C19", "*17"): "RS12248560",
    ("CYP2D6", "*4"): "RS3892097",
    ("CYP2D6", "*10"): "RS1065852",
    ("CYP2D6", "*6"): "RS5030655",
    ("CYP2C9", "*2"): "RS1799853",
    ("CYP2C9", "*3"): "RS1057910",
    ("DPYD", "*2A"): "RS3918290",
    ("DPYD", "*13"): "RS55886062",
    ("VKORC1", "-1639G>A"): "RS9923231",
    ("TPMT", "*3A"): "RS1800462",
    ("TPMT", "*3C"): "RS1800460",
    ("SLCO1B1", "*5"): "RS4149056",
    ("HLA-B", "*57:01"): "HLA-B*57:01",
    ("HLA-B", "*58:01"): "HLA-B*58:01",
    ("HLA-B", "*15:02"): "HLA-B*15:02",
    ("UGT1A1", "*28"): "RS8175347",
}


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
    # Check and add extra columns on the fly without dropping data
    cursor.execute("PRAGMA table_info(variant_evidence)")
    existing_cols = {col[1].lower() for col in cursor.fetchall()}
    for col_name, col_type in [("adverse_effects", "TEXT"), ("phenotype_category", "TEXT")]:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE variant_evidence ADD COLUMN {col_name} {col_type}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_var_ev_gene_mut ON variant_evidence (gene, mutation)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_var_ev_gene ON variant_evidence (gene)")
    conn.commit()
    return conn


def init_real_civic_db(conn=None):
    """Downloads live CIViC evidence into SQLite, falling back to a curated panel if network fails."""
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
            ("BRAF", "V600E", "Melanoma", "Vemurafenib", "Level A", "CIViC Database"),
            ("EGFR", "L858R", "Non-Small Cell Lung Cancer", "Osimertinib", "Level A", "CIViC Database"),
            ("KRAS", "G12C", "Non-Small Cell Lung Cancer", "Sotorasib", "Level A", "CIViC Database"),
            ("ERBB2", "AMPLIFICATION", "Breast Cancer", "Trastuzumab", "Level A", "CIViC Database"),
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO variant_evidence 
            (gene, mutation, disease, therapy, evidence_tier, source) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, fallback)
        conn.commit()

    if owns_conn:
        conn.close()


def init_oncokb_db(conn=None):
    """Loads OncoKB data from local annotation file if present."""
    owns_conn = conn is None
    conn = _get_connection() if owns_conn else conn
    cursor = conn.cursor()

    oncokb_path = Path(__file__).resolve().parents[3] / "genie_mskcc_samples_with_2017_oncokb_annotation.txt"
    if not oncokb_path.exists():
        print(f"OncoKB annotation file not found at {oncokb_path}, skipping OncoKB ingestion.")
        if owns_conn:
            conn.close()
        return

    print("Loading OncoKB data...")
    try:
        pattern = r"([^\(]+)\(([^ ]+) ([^\)]+)\)"
        df_onco = pd.read_csv(oncokb_path, sep="\t", low_memory=False)
        level_cols = ["LEVEL_1", "LEVEL_2", "LEVEL_3A", "LEVEL_3B", "LEVEL_4"]

        onco_records = []
        for _, row in df_onco.dropna(subset=["CANCER_TYPE_DETAILED"]).iterrows():
            disease = str(row["CANCER_TYPE_DETAILED"]).strip()
            for level_col in level_cols:
                if level_col in df_onco.columns and pd.notna(row[level_col]):
                    cell_val = str(row[level_col]).strip()
                    for item in cell_val.split(";"):
                        match = re.search(pattern, item)
                        if match:
                            drugs_raw = match.group(1).strip()
                            gene = match.group(2).strip().upper()
                            mutation = match.group(3).strip().upper()

                            if mutation.startswith("P.") or mutation.startswith("C."):
                                mutation = mutation[2:]

                            for drug in drugs_raw.split(","):
                                onco_records.append((
                                    gene,
                                    mutation,
                                    disease,
                                    drug.strip(),
                                    level_col.replace("_", " ").title(),
                                    "OncoKB",
                                ))

        if onco_records:
            cursor.executemany("""
                INSERT OR REPLACE INTO variant_evidence 
                (gene, mutation, disease, therapy, evidence_tier, source) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, onco_records)
            conn.commit()
            print(f"Successfully loaded {len(onco_records)} clinical records from OncoKB into SQLite!")
    except Exception as e:
        print(f"OncoKB loading warning ({e}). Skipping OncoKB ingestion.")

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

        if records:
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
        cursor.executemany("""
            INSERT OR REPLACE INTO variant_evidence 
            (gene, mutation, disease, therapy, evidence_tier, source) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, fallback)
        conn.commit()

    if owns_conn:
        conn.close()


def init_cpic_guidelines_db(conn=None):
    """Fetch official CPIC (Clinical Pharmacogenetics Implementation Consortium) Dosing Guidelines."""
    owns_conn = conn is None
    conn = _get_connection() if owns_conn else conn
    cursor = conn.cursor()

    print("Fetching official CPIC Clinical Dosing Guidelines via REST API...")
    try:
        drugs_res = requests.get("https://api.cpicpgx.org/v1/drug", timeout=15)
        drugs_map = {d["drugid"]: d["name"] for d in drugs_res.json()} if drugs_res.status_code == 200 else {}

        recs_res = requests.get("https://api.cpicpgx.org/v1/recommendation", timeout=25)
        if recs_res.status_code != 200:
            raise RuntimeError(f"CPIC API returned status {recs_res.status_code}")

        recs = recs_res.json()
        records = []

        for r in recs:
            drug_name = drugs_map.get(r.get("drugid"), "").strip()
            if not drug_name:
                continue

            lookup_keys = r.get("lookupkey", {})
            implications = r.get("implications", {})
            rec_text = r.get("drugrecommendation", "").strip()
            classification = r.get("classification", "Strong")
            tier = f"CPIC Level A ({classification})" if classification in ("Strong", "Moderate") else f"CPIC Level B ({classification})"

            if not rec_text or rec_text.lower().startswith("no recommendation"):
                continue

            for gene, key_val in lookup_keys.items():
                gene_clean = gene.strip().upper()
                implication_text = implications.get(gene, "")
                disease_desc = f"{implication_text}: {rec_text}" if implication_text else rec_text

                raw_tokens = []
                if "/" in str(key_val):
                    raw_tokens.extend([t.strip().upper() for t in str(key_val).split("/") if t.strip()])
                else:
                    match = re.search(r"(\*[0-9A-Za-z_:]+|-[0-9]+[A-Za-z]?>[A-Za-z]|RS[0-9]+)", str(key_val), re.IGNORECASE)
                    if match:
                        raw_tokens.append(match.group(1).upper())
                    else:
                        raw_tokens.append(str(key_val).strip().upper())

                all_variants = set(raw_tokens)
                for tok in raw_tokens:
                    alias = VIP_PGX_MAPPING.get((gene_clean, tok))
                    if alias:
                        all_variants.add(alias.upper())

                for var in all_variants:
                    if not var or var.lower() == "none" or var == "*1":
                        continue
                    records.append((
                        gene_clean,
                        var,
                        disease_desc,
                        drug_name,
                        tier,
                        "CPIC Guidelines",
                    ))

        if records:
            cursor.executemany("""
                INSERT OR REPLACE INTO variant_evidence 
                (gene, mutation, disease, therapy, evidence_tier, source) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()
            print(f"Successfully loaded {len(records)} official clinical dosing records from CPIC into SQLite!")

    except Exception as e:
        print(f"CPIC fetch warning ({e}). Ingestion skipped or fallback used.")

    if owns_conn:
        conn.close()


def bootstrap_all():
    conn = _get_connection()
    init_real_civic_db(conn=conn)
    init_oncokb_db(conn=conn)
    init_pharmgkb_db(conn=conn)
    init_cpic_guidelines_db(conn=conn)
    conn.close()


if __name__ == "__main__":
    bootstrap_all()
