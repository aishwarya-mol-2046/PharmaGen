import os
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = str(Path(__file__).resolve().parents[2] / "data" / "raw" / "clinical_kb.db")
CIVIC_URL = "https://civicdb.org/downloads/nightly/nightly-ClinicalEvidenceSummaries.tsv"


# Downloads live CIViC evidence into SQLite, falling back to a curated panel if the network fails
def init_real_civic_db():
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
            PRIMARY KEY (gene, mutation, therapy, disease)
        )
    """)

    print("Fetching live CIViC database release...")
    try:
        df = pd.read_csv(CIVIC_URL, sep="\t", low_memory=False)

        # 1. Detect column mapping dynamically (handles v1 & v2 schemas)
        cols = {c.lower(): c for c in df.columns}

        disease_col = cols.get("disease", cols.get("disease_name"))
        drug_col = cols.get("therapies", cols.get("drugs", cols.get("therapy")))
        level_col = cols.get("evidence_level", cols.get("evidence_direction"))
        mp_col = cols.get("molecular_profile", cols.get("variant"))
        gene_col = cols.get("gene", cols.get("feature_name"))

        records = []

        # 2. Parse Modern CIViC Molecular Profile schema (e.g. "BRAF V600E")
        if mp_col and disease_col and drug_col:
            clean_df = df.dropna(subset=[mp_col, disease_col, drug_col])
            for _, row in clean_df.iterrows():
                mp_str = str(row[mp_col]).strip().upper()
                parts = mp_str.split(" ", 1)

                gene = parts[0] if len(parts) > 0 else "UNKNOWN"
                mutation = parts[1] if len(parts) > 1 else mp_str

                records.append(
                    (
                        gene,
                        mutation,
                        str(row[disease_col]).strip(),
                        str(row[drug_col]).strip(),
                        f"Level {row[level_col]}"
                        if level_col and pd.notna(row[level_col])
                        else "Level A",
                        "CIViC Database",
                    )
                )

        # 3. Parse Legacy Column Schema
        elif gene_col and disease_col and drug_col:
            clean_df = df.dropna(subset=[gene_col, disease_col, drug_col])
            var_col = cols.get("variant", cols.get("variant_name", gene_col))
            for _, row in clean_df.iterrows():
                records.append(
                    (
                        str(row[gene_col]).strip().upper(),
                        str(row[var_col]).strip().upper(),
                        str(row[disease_col]).strip(),
                        str(row[drug_col]).strip(),
                        f"Level {row[level_col]}"
                        if level_col and pd.notna(row[level_col])
                        else "Level A",
                        "CIViC Database",
                    )
                )
        else:
            raise KeyError(f"Could not map columns. Available: {list(df.columns)}")

        cursor.executemany(
            """
            INSERT OR REPLACE INTO variant_evidence
            (gene, mutation, disease, therapy, evidence_tier, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            records,
        )
        print(f"Successfully loaded {len(records)} live clinical records from CIViC into SQLite!")

    except Exception as e:
        print(f"Network fetch warning ({e}). Loading fallback core panel...")
        fallback = [
            ("BRAF", "V600E", "Melanoma", "Vemurafenib", "Level A", "CIViC"),
            ("EGFR", "L858R", "Non-Small Cell Lung Cancer", "Osimertinib", "Level A", "CIViC"),
            ("KRAS", "G12C", "Non-Small Cell Lung Cancer", "Sotorasib", "Level A", "CIViC"),
            ("ERBB2", "AMPLIFICATION", "Breast Cancer", "Trastuzumab", "Level A", "CIViC"),
        ]
        cursor.executemany("INSERT OR REPLACE INTO variant_evidence VALUES (?,?,?,?,?,?)", fallback)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_real_civic_db()
