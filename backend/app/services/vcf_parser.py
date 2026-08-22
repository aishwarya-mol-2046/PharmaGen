import sqlite3
from pathlib import Path

DB_PATH = str(Path(__file__).resolve().parents[2] / "data" / "raw" / "clinical_kb.db")

class VariantAnnotationEngine:
    @staticmethod
    def parse_vcf_stream_detailed(file_bytes: bytes):
        """Parse VCF bytes and return variants plus an input-quality report."""
        variants = []
        validation = {
            "fileformat_header": False,
            "column_header": False,
            "data_rows": 0,
            "parsed_rows": 0,
            "skipped_rows": 0,
            "gene_annotated_rows": 0,
            "mutation_annotated_rows": 0,
            "duplicate_rows": 0,
        }
        seen_variants = set()

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
            parts = stripped_line.split("\t")
            if len(parts) < 8:
                validation["skipped_rows"] += 1
                continue

            chrom, pos, var_id, ref, alt, qual, filter_status, info_raw = parts[:8]
            info_dict = {}
            for item in info_raw.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    info_dict[k.upper()] = v.strip()

            # 1) Custom PharmaGen keys
            gene = info_dict.get("GENE") or info_dict.get("SYMBOL") or "UNKNOWN"
            mutation = info_dict.get("MUT") or info_dict.get("HGVSP")

            # 2) SnpEff ANN= field: ANN=allele|effect|impact|gene|...|hgvs_c|hgvs_p
            if not mutation and "ANN" in info_dict:
                ann_fields = info_dict["ANN"].split("|")
                if len(ann_fields) >= 4 and ann_fields[3]:
                    gene = ann_fields[3]
                if len(ann_fields) >= 11 and ann_fields[10]:
                    mutation = ann_fields[10]

            # 3) VEP CSQ= field
            if not mutation and "CSQ" in info_dict:
                csq_fields = info_dict["CSQ"].split("|")
                if len(csq_fields) >= 4 and csq_fields[3]:
                    gene = csq_fields[3]
                if len(csq_fields) >= 11 and csq_fields[10]:
                    mutation = csq_fields[10]

            # 4) Fallback
            if not mutation:
                mutation = f"{ref}>{alt}"

            # Normalize HGVSp-like prefix so p.V600E matches V600E in KB
            mut_norm = mutation.strip()
            if mut_norm.upper().startswith("P."):
                mut_norm = mut_norm[2:]
            elif mut_norm.upper().startswith("C."):
                mut_norm = mut_norm[2:]
            if ":" in mut_norm:
                mut_norm = mut_norm.split(":", 1)[-1]
            mutation = mut_norm

            variant_key = (chrom, pos, ref, alt, gene.upper(), mutation.upper())
            if variant_key in seen_variants:
                validation["duplicate_rows"] += 1
                continue
            seen_variants.add(variant_key)

            if gene != "UNKNOWN":
                validation["gene_annotated_rows"] += 1
            # Count mutation annotation if it came from an annotation field (not fallback)
            if any(k in info_dict for k in ("MUT", "HGVSP", "ANN", "CSQ")):
                validation["mutation_annotated_rows"] += 1

            variants.append({
                "chrom": chrom,
                "pos": pos,
                "gene": gene.upper(),
                "mutation": mutation.upper()
            })
            validation["parsed_rows"] += 1

        validation["valid_vcf_headers"] = validation["fileformat_header"] and validation["column_header"]
        validation["annotation_coverage_percent"] = round(
            validation["gene_annotated_rows"] / validation["parsed_rows"] * 100, 1
        ) if validation["parsed_rows"] else 0.0
        return variants, validation

    @staticmethod
    # Parses raw VCF bytes into a list of variant dicts with chrom, pos, gene, and mutation
    def parse_vcf_stream(file_bytes: bytes):
        variants, _ = VariantAnnotationEngine.parse_vcf_stream_detailed(file_bytes)
        return variants

    @staticmethod
    # Queries the SQLite clinical knowledge base for matching evidence by gene and mutation
    def match_clinical_evidence(gene: str, mutation: str, cursor=None):
        # Normalize incoming mutation so p.V600E / c.1799T>A etc. hit the KB
        _m = mutation.strip()
        if _m.upper().startswith("P."):
            _m = _m[2:]
        elif _m.upper().startswith("C."):
            _m = _m[2:]
        if ":" in _m:
            _m = _m.split(":", 1)[-1]
        mutation = _m.strip()

        owns_connection = cursor is None
        conn = sqlite3.connect(DB_PATH) if owns_connection else None
        cursor = conn.cursor() if owns_connection else cursor
        
        # 1. Dynamically inspect table columns to find the mutation column name
        cursor.execute("PRAGMA table_info(variant_evidence)")
        columns = [col[1].lower() for col in cursor.fetchall()]
        
        # Determine exact mutation column name used in SQLite table
        mut_col = "mutation"
        if "variant" in columns:
            mut_col = "variant"
        elif "alteration" in columns:
            mut_col = "alteration"
        
        # 2. Query matching BOTH gene and mutation first
        query = f"""
            SELECT DISTINCT disease, therapy, evidence_tier, source 
            FROM variant_evidence 
            WHERE UPPER(gene) = UPPER(?) AND UPPER({mut_col}) = UPPER(?)
        """
        cursor.execute(query, (gene, mutation))
        rows = cursor.fetchall()
        
        match_type = "exact" if rows else "none"

        # Gene-only evidence is contextual and must not be presented as an
        # exact treatment recommendation for a different mutation.
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

        if owns_connection:
            conn.close()
        
        if not rows:
            return [{
                "disease": "No Direct Match",
                "therapy": "No evidence returned",
                "evidence_tier": "Unclassified",
                "source": "N/A",
                "match_type": match_type,
            }]
        
        # 4. Deduplicate matching records
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