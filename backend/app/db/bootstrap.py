import os
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = str(Path(__file__).resolve().parents[2] / "data" / "raw" / "clinical_kb.db")
CIVIC_URL = "https://civicdb.org/downloads/nightly/nightly-ClinicalEvidenceSummaries.tsv"
GENIE_ONCOKB_FILENAME = "genie_mskcc_samples_with_2017_oncokb_annotation.txt"

# OncoKB levels crosswalked to CIViC A-E scale so the frontend's
# high-confidence metric (Level A|B) treats both sources consistently.
ONCOKB_TIER_CROSSWALK = {
    "LEVEL_1": "Level A",
    "LEVEL_2": "Level B",
    "LEVEL_3A": "Level C",
    "LEVEL_3B": "Level C",
    "LEVEL_4": "Level D",
}


def _load_oncokb(cursor):
    """Load OncoKB evidence independently of CIViC network success.

    Priority: full GENIE annotation TSV (repo root or PHARMAGEN_ONCOKB_FILE)
    -> committed curated seed panel. Seed rows use INSERT OR IGNORE so an
    existing CIViC row for the same evidence key keeps its source.
    """
    import re

    pattern = r"([^\(]+)\(([^ ]+) ([^\)]+)\)"
    genie_candidates = [
        Path(p)
        for p in (
            os.environ.get("PHARMAGEN_ONCOKB_FILE", "").strip(),
            str(Path(__file__).resolve().parents[3] / GENIE_ONCOKB_FILENAME),
            str(Path(__file__).resolve().parents[3] / "tests" / GENIE_ONCOKB_FILENAME),
        )
        if p.strip()
    ]
    genie_path = next((p for p in genie_candidates if p.exists()), None)
    records = []

    if genie_path:
        print(f"Loading full OncoKB data from {genie_path}...")
        df_onco = pd.read_csv(genie_path, sep="\t", low_memory=False)
        for _, row in df_onco.dropna(subset=["CANCER_TYPE_DETAILED"]).iterrows():
            disease = str(row["CANCER_TYPE_DETAILED"]).strip()
            for level_col, tier in ONCOKB_TIER_CROSSWALK.items():
                if level_col in df_onco.columns and pd.notna(row[level_col]):
                    for item in str(row[level_col]).strip().split(";"):
                        match = re.search(pattern, item)
                        if match:
                            gene = match.group(2).strip().upper()
                            mutation = match.group(3).strip().upper()
                            if mutation.startswith(("P.", "C.")):
                                mutation = mutation[2:]
                            for drug in match.group(1).strip().split(","):
                                records.append(
                                    (gene, mutation, disease, drug.strip(), tier, "OncoKB")
                                )
        cursor.executemany(
            "INSERT OR IGNORE INTO variant_evidence (gene, mutation, disease, therapy, evidence_tier, source) VALUES (?,?,?,?,?,?)",
            records,
        )
        print(f"Successfully loaded {len(records)} clinical records from OncoKB into SQLite!")
        return

    seed_path = Path(__file__).resolve().parents[2] / "data" / "seed" / "oncokb_seed.csv"
    if not seed_path.exists():
        print("OncoKB: no GENIE file or seed panel found; skipping.")
        return
    print("Loading OncoKB curated seed panel...")
    df_seed = pd.read_csv(seed_path)
    records = [
        (
            str(row.gene).upper(),
            str(row.mutation).upper(),
            str(row.disease),
            str(row.therapy),
            str(row.evidence_tier),
            "OncoKB",
        )
        for row in df_seed.itertuples()
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO variant_evidence (gene, mutation, disease, therapy, evidence_tier, source) VALUES (?,?,?,?,?,?)",
        records,
    )
    print(f"Successfully loaded {len(records)} OncoKB seed-panel records into SQLite!")


# Downloads live CIViC evidence into SQLite, falling back to a curated panel if the network fails
def init_real_civic_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS variant_evidence (
            gene TEXT,
            mutation TEXT,
            disease TEXT,
            therapy TEXT,
            evidence_tier TEXT,
            source TEXT,
            PRIMARY KEY (gene, mutation, therapy, disease)
        )
    """
    )

    cursor.execute("PRAGMA table_info(variant_evidence)")
    columns = [col[1] for col in cursor.fetchall()]
    if "adverse_effects" not in columns:
        cursor.execute("ALTER TABLE variant_evidence ADD COLUMN adverse_effects TEXT")

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
        cursor.executemany(
            "INSERT OR REPLACE INTO variant_evidence (gene, mutation, disease, therapy, evidence_tier, source) VALUES (?,?,?,?,?,?)",
            fallback,
        )

    # OncoKB loads independently: a CIViC network failure no longer blocks it
    try:
        _load_oncokb(cursor)
    except Exception as e:
        print(f"OncoKB load warning ({e}); continuing with CIViC-only knowledge base.")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_real_civic_db()
