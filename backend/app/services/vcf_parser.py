import os
import re
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = str(Path(__file__).resolve().parents[2] / "data" / "raw" / "clinical_kb.db")

# 3-letter to 1-letter amino acid dictionary
AA3_TO_AA1 = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
    "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
    "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
    "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
    "TER": "*", "STOP": "*",
}

HGVS_MAP = {
    "VAL600GLU": "V600E",
    "LEU858ARG": "L858R",
    "GLY12CYS": "G12C",
    "GLY12VAL": "G12V",
    "GLY12ASP": "G12D",
    "GLU545LYS": "E545K",
    "HIS1047ARG": "H1047R",
    "ARG248GLN": "R248Q",
    "ARG273HIS": "R273H",
    "THR790MET": "T790M",
}

RSID_MAP = {
    "rs121913333": ("BRAF", "V600E"),
    "rs121434568": ("EGFR", "L858R"),
    "rs121913529": ("KRAS", "G12C"),
    "rs11555212": ("PIK3CA", "E545K"),
    "rs28934578": ("TP53", "R248Q"),
}

VIP_PGX_MAPPING = {
    ("CYP2C19", "RS4244285"): "*2",
    ("CYP2C19", "RS4986893"): "*3",
    ("CYP2C19", "RS12248560"): "*17",
    ("CYP2C19", "*2"): "RS4244285",
    ("CYP2C19", "*3"): "RS4986893",
    ("CYP2C19", "*17"): "RS12248560",
    ("CYP2D6", "RS3892097"): "*4",
    ("CYP2D6", "RS1065852"): "*10",
    ("CYP2D6", "RS5030655"): "*6",
    ("CYP2D6", "*4"): "RS3892097",
    ("CYP2D6", "*10"): "RS1065852",
    ("CYP2D6", "*6"): "RS5030655",
    ("CYP2C9", "RS1799853"): "*2",
    ("CYP2C9", "RS1057910"): "*3",
    ("CYP2C9", "*2"): "RS1799853",
    ("CYP2C9", "*3"): "RS1057910",
    ("DPYD", "RS3918290"): "*2A",
    ("DPYD", "RS55886062"): "*13",
    ("DPYD", "RS67376798"): "C.2846A>T",
    ("DPYD", "*2A"): "RS3918290",
    ("DPYD", "C.1905+1G>A"): "RS3918290",
    ("VKORC1", "RS9923231"): "-1639G>A",
    ("VKORC1", "-1639G>A"): "RS9923231",
    ("TPMT", "RS1800462"): "*3A",
    ("TPMT", "RS1800460"): "*3C",
    ("TPMT", "RS1142345"): "*3C",
    ("TPMT", "*3A"): "RS1800462",
    ("TPMT", "*3C"): "RS1800460",
    ("SLCO1B1", "RS4149056"): "*5",
    ("SLCO1B1", "*5"): "RS4149056",
    ("HLA-B", "*57:01"): "HLA-B*57:01",
    ("HLA-B", "*15:02"): "HLA-B*15:02",
    ("UGT1A1", "RS8175347"): "*28",
    ("UGT1A1", "*28"): "RS8175347",
}

VIP_PGX_PHENOTYPE_MAPPING = {
    ("CYP2C19", "*2"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "CYP2C19 POOR METABOLIZER", "CYP2C19 INTERMEDIATE METABOLIZER"],
    ("CYP2C19", "*3"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "CYP2C19 POOR METABOLIZER", "CYP2C19 INTERMEDIATE METABOLIZER"],
    ("CYP2C19", "RS4244285"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "CYP2C19 POOR METABOLIZER"],
    ("CYP2C19", "RS4986893"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "CYP2C19 POOR METABOLIZER"],
    ("CYP2D6", "*4"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "CYP2D6 POOR METABOLIZER"],
    ("CYP2D6", "RS3892097"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "CYP2D6 POOR METABOLIZER"],
    ("CYP2C9", "*2"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "CYP2C9 INTERMEDIATE METABOLIZER"],
    ("CYP2C9", "*3"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "CYP2C9 POOR METABOLIZER"],
    ("DPYD", "*2A"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "DPD DEFICIENT", "DPD DEFICIENCY"],
    ("DPYD", "RS3918290"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "DPD DEFICIENT", "DPD DEFICIENCY"],
    ("TPMT", "*3A"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "TPMT DEFICIENT"],
    ("TPMT", "RS1800462"): ["POOR METABOLIZER", "INTERMEDIATE METABOLIZER", "TPMT DEFICIENT"],
    ("SLCO1B1", "*5"): ["DECREASED FUNCTION", "POOR FUNCTION", "INTERMEDIATE FUNCTION"],
    ("SLCO1B1", "RS4149056"): ["DECREASED FUNCTION", "POOR FUNCTION", "INTERMEDIATE FUNCTION"],
    ("HLA-B", "*57:01"): ["*57:01 POSITIVE", "HLA-B*57:01 POSITIVE", "*57:01", "HLA-B*57:01"],
    ("HLA-B", "*58:01"): ["*58:01 POSITIVE", "HLA-B*58:01 POSITIVE", "*58:01", "HLA-B*58:01"],
    ("HLA-B", "*15:02"): ["*15:02 POSITIVE", "HLA-B*15:02 POSITIVE", "*15:02", "HLA-B*15:02"],
}


def normalize_mutation(mut_str: str | None) -> str:
    """Standardizes mutation strings (strips prefixes, translates 3-letter HGVS to 1-letter)."""
    if not mut_str:
        return ""
    m = str(mut_str).strip()
    if ":" in m and "::" not in m:
        m = m.split(":", 1)[-1].strip()
    if m.upper().startswith("P.") or m.upper().startswith("C."):
        m = m[2:].strip()

    match = re.match(r"^([A-Za-z]{3})(\d+)([A-Za-z]{3}|\*|=|del|ins|fs.*)?$", m, re.IGNORECASE)
    if match:
        a1, pos, a2 = match.groups()
        a1_1 = AA3_TO_AA1.get(a1.upper(), a1.upper())
        a2_1 = AA3_TO_AA1.get((a2 or "").upper(), (a2 or "").upper())
        return f"{a1_1}{pos}{a2_1}"

    for three_let, one_let in HGVS_MAP.items():
        if three_let in m:
            m = m.replace(three_let, one_let)

    return m.upper()


def parse_csq_or_ann(info_dict: dict) -> tuple[str | None, str | None]:
    """Extract gene symbol and protein mutation from VEP (CSQ) or SnpEff (ANN) fields."""
    gene, mut = None, None
    if "CSQ" in info_dict:
        csq_first = info_dict["CSQ"].split(",")[0]
        csq_parts = csq_first.split("|")
        if len(csq_parts) >= 4 and csq_parts[3]:
            gene = csq_parts[3].strip()
        for part in csq_parts:
            if "p." in part.lower():
                mut = part.strip()
                break
    elif "ANN" in info_dict:
        ann_first = info_dict["ANN"].split(",")[0]
        ann_parts = ann_first.split("|")
        if len(ann_parts) >= 4 and ann_parts[3]:
            gene = ann_parts[3].strip()
        for part in ann_parts:
            if "p." in part.lower():
                mut = part.strip()
                break
    return gene, mut


class VariantAnnotationEngine:
    @staticmethod
    def parse_vcf_stream_detailed(file_bytes: bytes):
        """Parse VCF bytes and return variants plus an input-quality report."""
        variants = []
        validation: dict[str, Any] = {
            "fileformat_header": False,
            "column_header": False,
            "data_rows": 0,
            "parsed_rows": 0,
            "skipped_rows": 0,
            "gene_annotated_rows": 0,
            "mutation_annotated_rows": 0,
            "duplicate_rows": 0,
            "valid_vcf_headers": False,
            "annotation_coverage_percent": 0.0,
        }
        seen_variants = set()
        distinct_combinations = set()
        observed_samples = set()

        for line in file_bytes.decode("utf-8", errors="ignore").splitlines():
            stripped_line = line.strip()
            if not stripped_line:
                continue
            if stripped_line.startswith("##fileformat=VCF"):
                validation["fileformat_header"] = True
                continue
            if stripped_line.startswith("#CHROM"):
                validation["column_header"] = True
                continue
            if stripped_line.startswith("#"):
                continue

            validation["data_rows"] += 1
            parts = stripped_line.split("	")
            if len(parts) < 8:
                validation["skipped_rows"] += 1
                continue

            chrom, pos, var_id, ref, alt, qual, filter_status, info_raw = parts[:8]
            info_dict = {}
            for item in info_raw.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    info_dict[k.upper()] = v.strip()

            csq_gene, csq_mut = parse_csq_or_ann(info_dict)
            gene = info_dict.get("GENE") or info_dict.get("SYMBOL") or csq_gene or "UNKNOWN"

            if var_id.lower().startswith("rs") and var_id in RSID_MAP:
                r_gene, r_mut = RSID_MAP[var_id]
                if gene == "UNKNOWN":
                    gene = r_gene
                raw_mut = r_mut
            else:
                raw_mut = (
                    info_dict.get("MUT")
                    or info_dict.get("MUTATION")
                    or info_dict.get("HGVSP")
                    or info_dict.get("HGVS_P")
                    or csq_mut
                    or (var_id.strip() if var_id and var_id.strip() != "." and var_id.strip().lower().startswith("rs") else None)
                    or f"{ref}>{alt}"
                )

            mutation = normalize_mutation(raw_mut)

            if gene != "UNKNOWN":
                validation["gene_annotated_rows"] += 1
            if any(k in info_dict for k in ("MUT", "HGVSP", "MUTATION", "ANN", "CSQ")) or (var_id and var_id.lower().startswith("rs")):
                validation["mutation_annotated_rows"] += 1

            sample_id = info_dict.get("SAMPLE", "")
            if sample_id:
                observed_samples.add(sample_id)

            variant_key = (chrom, pos, ref, alt, gene.upper(), mutation.upper(), sample_id)
            if variant_key in seen_variants:
                validation["duplicate_rows"] += 1
                continue
            seen_variants.add(variant_key)
            distinct_combinations.add((chrom, pos, ref, alt, gene.upper(), mutation.upper()))

            variants.append({
                "chrom": chrom,
                "pos": pos,
                "gene": gene.upper(),
                "mutation": mutation.upper(),
            })
            validation["parsed_rows"] += 1

        validation["valid_vcf_headers"] = (
            validation["fileformat_header"] and validation["column_header"]
        )
        validation["annotation_coverage_percent"] = (
            round(validation["gene_annotated_rows"] / validation["parsed_rows"] * 100, 1)
            if validation["parsed_rows"]
            else 0.0
        )
        validation["patients_observed"] = len(observed_samples)
        validation["unique_variant_combinations"] = len(distinct_combinations)
        return variants, validation

    @staticmethod
    def parse_vcf_stream(file_bytes: bytes):
        """Parses raw VCF bytes into a list of variant dicts with chrom, pos, gene, and mutation."""
        variants, _ = VariantAnnotationEngine.parse_vcf_stream_detailed(file_bytes)
        return variants

    @staticmethod
    def match_clinical_evidence(gene: str, mutation: str, cursor=None):
        """Queries the SQLite clinical knowledge base for matching evidence by gene and mutation."""
        owns_connection = cursor is None
        if owns_connection:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
        else:
            conn = None

        cursor.execute("PRAGMA table_info(variant_evidence)")
        columns = [col[1].lower() for col in cursor.fetchall()]

        mut_col = "mutation"
        if "variant" in columns:
            mut_col = "variant"
        elif "alteration" in columns:
            mut_col = "alteration"

        norm_mut = normalize_mutation(mutation)
        candidates = list(dict.fromkeys([
            str(mutation).strip().upper(),
            norm_mut.upper(),
        ]))
        if norm_mut.startswith(f"{gene.upper()}*"):
            candidates.append(norm_mut[len(gene):])
        elif norm_mut.startswith("*"):
            candidates.append(f"{gene.upper()}{norm_mut}")

        # Check VIP pharmacogene aliases (rsID <-> star-allele)
        for (g, m), alias in VIP_PGX_MAPPING.items():
            if (gene.upper() == g or gene.upper() == "UNKNOWN") and (norm_mut == m or str(mutation).strip().upper() == m):
                candidates.append(alias.upper())

        # Check CPIC phenotype aliases
        for (g, m), phenos in VIP_PGX_PHENOTYPE_MAPPING.items():
            if (gene.upper() == g or gene.upper() == "UNKNOWN") and (norm_mut == m or str(mutation).strip().upper() == m):
                candidates.extend([p.upper() for p in phenos])

        candidates = list(dict.fromkeys(candidates))
        rows = []

        if gene and gene.upper() != "UNKNOWN":
            placeholders = ",".join("?" for _ in candidates)
            query = f"""
                SELECT DISTINCT disease, therapy, evidence_tier, source 
                FROM variant_evidence 
                WHERE UPPER(gene) = UPPER(?) AND UPPER({mut_col}) IN ({placeholders})
            """
            cursor.execute(query, [gene] + candidates)
            rows = cursor.fetchall()

            # Fallback variant search
            if not rows and any(c.startswith("RS") or c.startswith("*") for c in candidates):
                placeholders = ",".join("?" for _ in candidates)
                cursor.execute(
                    f"SELECT DISTINCT disease, therapy, evidence_tier, source FROM variant_evidence WHERE UPPER({mut_col}) IN ({placeholders})",
                    candidates
                )
                rows = cursor.fetchall()
        else:
            placeholders = ",".join("?" for _ in candidates)
            cursor.execute(
                f"SELECT DISTINCT disease, therapy, evidence_tier, source FROM variant_evidence WHERE UPPER({mut_col}) IN ({placeholders})",
                candidates
            )
            rows = cursor.fetchall()

        match_type = "exact" if rows else "none"

        if not rows:
            cursor.execute(
                """
                SELECT DISTINCT disease, therapy, evidence_tier, source 
                FROM variant_evidence 
                WHERE UPPER(gene) = UPPER(?)
                LIMIT 10
                """,
                (gene,)
            )
            rows = cursor.fetchall()
            match_type = "gene_context" if rows else "none"

        if owns_connection and conn is not None:
            conn.close()

        if not rows:
            return [{
                "disease": "No Direct Match",
                "therapy": "No evidence returned",
                "evidence_tier": "Unclassified",
                "source": "N/A",
                "match_type": match_type,
            }]

        unique_matches = []
        seen = set()

        for r in rows:
            record_tuple = (r[0], r[1], r[2], r[3])
            if record_tuple not in seen:
                seen.add(record_tuple)
                unique_matches.append({
                    "disease": r[0],
                    "therapy": r[1],
                    "evidence_tier": r[2],
                    "source": r[3],
                    "match_type": match_type,
                })

        return unique_matches
