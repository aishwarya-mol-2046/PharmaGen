#!/usr/bin/env python3
"""Convert patient data between CSV and the VCF format expected by the PharmaGen app.

Supported flows:
- CSV -> VCF for patient files with columns CHROM,POS,REF,ALT,GENE,MUT
- VCF -> CSV for patient or variant files, preserving GENE/MUT when available
- generate-demo-vcf: creates a valid patient VCF with N rows using real gene/mutation pairs from the clinical database

The backend parser expects INFO strings like:
    GENE=BRAF;MUT=V600E
"""

from __future__ import annotations

import argparse
import csv
import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "backend" / "data" / "raw" / "clinical_kb.db"


def parse_info_field(info_value: str) -> dict:
    info = {}
    for item in str(info_value).split(";"):
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        info[key.upper()] = value.strip()
    return info


def csv_to_patient_vcf(input_csv: str, output_vcf: str) -> None:
    in_path = Path(input_csv)
    out_path = Path(output_vcf)

    with in_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"CHROM", "POS", "REF", "ALT", "GENE", "MUT"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        rows = list(reader)

    with out_path.open("w", encoding="utf-8", newline="") as out:
        out.write("##fileformat=VCFv4.2\n")
        out.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")

        for row in rows:
            chrom = (row.get("CHROM") or ".").strip()
            pos = (row.get("POS") or ".").strip()
            ref = (row.get("REF") or ".").strip()
            alt = (row.get("ALT") or ".").strip()
            gene = (row.get("GENE") or "UNKNOWN").strip()
            mut = (row.get("MUT") or row.get("MUTATION") or f"{ref}>{alt}").strip()
            vid = f"{chrom}:{pos}:{ref}>{alt}"
            info = f"GENE={gene};MUT={mut}"
            out.write(f"{chrom}\t{pos}\t{vid}\t{ref}\t{alt}\t.\tPASS\t{info}\n")

    print(f"Converted {len(rows)} CSV rows to {out_path}")


def vcf_to_patient_csv(input_vcf: str, output_csv: str) -> None:
    in_path = Path(input_vcf)
    out_path = Path(output_csv)
    rows = []

    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 8:
                continue

            chrom, pos, _id, ref, alt, qual, filt, info_raw = parts[:8]
            info = parse_info_field(info_raw)

            gene = (info.get("GENE") or info.get("SYMBOL") or "UNKNOWN").strip()
            mutation = (
                info.get("MUT") or info.get("HGVSP") or info.get("HGVS_P") or f"{ref}>{alt}"
            ).strip()

            rows.append(
                {
                    "CHROM": chrom,
                    "POS": pos,
                    "REF": ref,
                    "ALT": alt,
                    "GENE": gene,
                    "MUT": mutation,
                }
            )

    with out_path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["CHROM", "POS", "REF", "ALT", "GENE", "MUT"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Extracted {len(rows)} VCF rows to {out_path}")


def generate_demo_patient_vcf(output_vcf: str, row_count: int = 100) -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Clinical database not found at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT gene, mutation FROM variant_evidence WHERE gene IS NOT NULL AND mutation IS NOT NULL ORDER BY gene, mutation"
    )
    rows = cur.fetchall()
    conn.close()

    if len(rows) < row_count:
        raise ValueError(
            f"Database has only {len(rows)} distinct gene/mutation pairs; requested {row_count} rows."
        )

    out_path = Path(output_vcf)
    with out_path.open("w", encoding="utf-8", newline="") as out:
        out.write("##fileformat=VCFv4.2\n")
        out.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")

        for idx, (gene, mutation) in enumerate(rows[:row_count], start=1):
            chrom = (idx % 22) + 1
            if chrom == 23:
                chrom = 1
            pos = 1000000 + idx * 17
            ref = "A"
            alt = "T"
            if idx % 3 == 0:
                ref, alt = "C", "G"
            elif idx % 2 == 0:
                ref, alt = "G", "A"

            vid = f"chr{chrom}:{pos}:{ref}>{alt}"
            info = f"GENE={gene};MUT={mutation}"
            out.write(f"{chrom}\t{pos}\t{vid}\t{ref}\t{alt}\t.\tPASS\t{info}\n")

    print(f"Generated {row_count} valid patient VCF rows at {out_path}")


def _fetch_evidence_pairs(conn, source: str | None = None):
    """Return distinct (gene, mutation) evidence pairs, optionally filtered by source."""
    if source:
        return conn.execute(
            """
            SELECT gene, mutation
            FROM variant_evidence
            WHERE gene IS NOT NULL AND mutation IS NOT NULL AND source = ?
            GROUP BY gene, mutation
            ORDER BY gene, mutation
            """,
            (source,),
        ).fetchall()
    return conn.execute(
        """
        SELECT gene, mutation
        FROM variant_evidence
        WHERE gene IS NOT NULL AND mutation IS NOT NULL
        GROUP BY gene, mutation
        ORDER BY gene, mutation
        """
    ).fetchall()


def generate_pgx_enriched_cohort_vcf(
    output_vcf: str,
    somatic_count: int = 1000,
    pgx_count: int = 120,
    seed: int = 42,
) -> None:
    """Build a combined cohort: synthetic somatic rows + germline PharmGKB PGx rows.

    Somatic pairs come from CIViC/OncoKB evidence; germline rows come from the
    PharmGKB source so the three-source hybrid pipeline is demonstrable on a
    single uploaded file. All coordinates are synthetic and flagged as such.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Clinical database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    somatic_pairs = [
        (gene, mutation, tier, source)
        for gene, mutation, tier, source in conn.execute(
            """
            SELECT gene, mutation, evidence_tier, source
            FROM variant_evidence
            WHERE gene IS NOT NULL AND mutation IS NOT NULL
            GROUP BY gene, mutation
            ORDER BY gene, mutation
            """
        ).fetchall()
    ]
    pgx_pairs = [pair for pair in _fetch_evidence_pairs(conn, "PharmGKB") if pair[0] and pair[1]]
    conn.close()

    if not somatic_pairs:
        raise ValueError("Clinical database contains no usable gene/mutation pairs")
    if not pgx_pairs:
        raise ValueError("No PharmGKB rows in the knowledge base; run bootstrap first")

    generator = random.Random(seed)
    shuffled = list(somatic_pairs)
    generator.shuffle(shuffled)
    somatic_rows = [shuffled[index % len(shuffled)] for index in range(somatic_count)]

    out_path = Path(output_vcf)
    with out_path.open("w", encoding="utf-8", newline="") as out:
        out.write("##fileformat=VCFv4.2\n")
        out.write("##synthetic_data=true\n")
        out.write("##synthetic_coordinates=true\n")
        out.write("##source=civic_oncokb_pharmgkb_hybrid_cohort\n")
        out.write("##germline_pgx=true\n")
        out.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")

        # Tumor (somatic) rows — patient tumor sample IDs
        for index, (gene, mutation, tier, source) in enumerate(somatic_rows, start=1):
            chrom = ((index - 1) % 22) + 1
            pos = 1000000 + index * 17
            ref, alt = ("A", "T") if index % 2 else ("G", "C")
            variant_id = f"SYNTH-{index:06d}"
            sample = f"P-{(index - 1) % 174 + 1:07d}-T01-IM3"
            info = (
                f"GENE={gene};MUT={mutation};"
                f"EVIDENCE_TIER={tier};SOURCE={source};SYNTHETIC=1;SAMPLE={sample}"
            )
            out.write(f"{chrom}\t{pos}\t{variant_id}\t{ref}\t{alt}\t.\tPASS\t{info}\n")

        # Germline pharmacogenomics rows — matched germline sample IDs (P-n-G01-GL)
        for offset in range(pgx_count):
            gene, mutation = pgx_pairs[offset % len(pgx_pairs)]
            chrom = ((offset + 7) % 22) + 1  # deliberately different spread than somatic block
            pos = 20000000 + offset * 29
            ref, alt = ("C", "T") if offset % 2 else ("A", "G")
            variant_id = f"PGX-{offset + 1:06d}"
            patient = f"P-{(offset % 174) + 1:07d}-G01-GL"
            info = (
                f"GENE={gene};MUT={mutation};"
                f"SOURCE=PharmGKB;GERMLINE=1;SYNTHETIC=1;SAMPLE={patient}"
            )
            out.write(f"{chrom}\t{pos}\t{variant_id}\t{ref}\t{alt}\t.\tPASS\t{info}\n")

    print(
        f"Generated {somatic_count} somatic + {pgx_count} germline PGx rows at {out_path} "
        f"(seed={seed}, {len(pgx_pairs)} distinct PharmGKB pairs)"
    )


def generate_synthetic_clinical_vcf(output_vcf: str, row_count: int = 1000, seed: int = 42) -> None:
    """Generate labelled synthetic variants from the local clinical evidence pairs.

    Gene/mutation pairs and evidence metadata come from the database. Coordinates
    are synthetic and must not be interpreted as a real patient's genome.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Clinical database not found at {DB_PATH}")
    if row_count < 1:
        raise ValueError("row_count must be greater than zero")

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT gene, mutation, evidence_tier, source
        FROM variant_evidence
        WHERE gene IS NOT NULL AND mutation IS NOT NULL
        GROUP BY gene, mutation
        ORDER BY gene, mutation
        """
    ).fetchall()
    conn.close()

    if not rows:
        raise ValueError("Clinical database contains no usable gene/mutation pairs")

    generator = random.Random(seed)
    selected = list(rows)
    generator.shuffle(selected)
    selected = [selected[index % len(selected)] for index in range(row_count)]

    out_path = Path(output_vcf)
    with out_path.open("w", encoding="utf-8", newline="") as out:
        out.write("##fileformat=VCFv4.2\n")
        out.write("##synthetic_data=true\n")
        out.write("##synthetic_coordinates=true\n")
        out.write("##source=local_CIViC_derived_clinical_evidence\n")
        out.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")

        for index, (gene, mutation, evidence_tier, source) in enumerate(selected, start=1):
            chrom = ((index - 1) % 22) + 1
            pos = 1000000 + index * 17
            ref, alt = ("A", "T") if index % 2 else ("G", "C")
            variant_id = f"SYNTH-{index:06d}"
            info = (
                f"GENE={gene};MUT={mutation};"
                f"EVIDENCE_TIER={evidence_tier};SOURCE={source};SYNTHETIC=1"
            )
            out.write(f"{chrom}\t{pos}\t{variant_id}\t{ref}\t{alt}\t.\tPASS\t{info}\n")

    print(f"Generated {row_count} clinically grounded synthetic rows at {out_path} (seed={seed})")


def convert_indigen_to_patient_vcf(
    input_vcf: str, output_vcf: str, max_rows: int | None = None
) -> None:
    """Convert the raw IndiGen non-annotated VCF into the app-readable format.

    Since the raw file has no GENE/MUT annotation, this keeps every variant row but
    assigns a fallback GENE and MUT based on the REF/ALT pair. This ensures the app
    can ingest all rows, though most variants will not match the clinical database.
    """
    in_path = Path(input_vcf)
    out_path = Path(output_vcf)

    rows_written = 0
    with (
        in_path.open("r", encoding="utf-8", errors="ignore") as src,
        out_path.open("w", encoding="utf-8", newline="") as dst,
    ):
        dst.write("##fileformat=VCFv4.2\n")
        dst.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")

        for line in src:
            if not line.strip() or line.startswith("#"):
                continue

            parts = line.strip().split("\t")
            if len(parts) < 8:
                continue

            chrom, pos, vid, ref, alt, qual, filt, info_raw = parts[:8]
            if max_rows is not None and rows_written >= max_rows:
                break

            mutation = f"{ref}>{alt}"
            gene = "UNKNOWN"
            info = f"GENE={gene};MUT={mutation}"
            dst.write(f"{chrom}\t{pos}\t{vid}\t{ref}\t{alt}\t{qual}\t{filt}\t{info}\n")
            rows_written += 1

    print(f"Converted {rows_written} IndiGen rows to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert patient data between CSV and the VCF format used by PharmaGen."
    )
    parser.add_argument("input_file", nargs="?", help="Input CSV or VCF file")
    parser.add_argument("output_file", nargs="?", help="Output CSV or VCF file")
    parser.add_argument(
        "--output-file", dest="output_file_flag", help="Output path when using --generate-demo"
    )
    parser.add_argument(
        "--generate-demo",
        action="store_true",
        help="Create a valid patient VCF with N rows using real gene/mutation pairs from the clinical database",
    )
    parser.add_argument(
        "--demo-count",
        type=int,
        default=100,
        help="Number of rows to generate when --generate-demo is used",
    )
    parser.add_argument(
        "--synthetic-clinical",
        action="store_true",
        help="Create labelled synthetic rows from local clinical evidence pairs",
    )
    parser.add_argument(
        "--synthetic-count",
        type=int,
        default=1000,
        help="Number of clinically grounded synthetic rows to generate",
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed for reproducible synthetic data")
    parser.add_argument(
        "--indigen",
        action="store_true",
        help="Convert every row of a raw IndiGen VCF into app-readable GENE/MUT format using fallback values",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap for raw IndiGen conversion; useful for testing before full conversion",
    )
    parser.add_argument(
        "--pgx-cohort",
        action="store_true",
        help="Create a cohort VCF combining synthetic somatic rows with germline PharmGKB PGx rows",
    )
    parser.add_argument(
        "--somatic-count",
        type=int,
        default=1000,
        help="Number of somatic rows when --pgx-cohort is used",
    )
    parser.add_argument(
        "--pgx-count",
        type=int,
        default=120,
        help="Number of germline PharmGKB rows to append when --pgx-cohort is used",
    )
    args = parser.parse_args()

    out_path = args.output_file or args.output_file_flag

    if args.pgx_cohort:
        if not out_path:
            raise ValueError("Output file path is required when using --pgx-cohort")
        generate_pgx_enriched_cohort_vcf(
            out_path,
            somatic_count=args.somatic_count,
            pgx_count=args.pgx_count,
            seed=args.seed,
        )
        raise SystemExit(0)

    if args.generate_demo:
        if not out_path:
            raise ValueError("Output file path is required when using --generate-demo")
        generate_demo_patient_vcf(out_path, row_count=args.demo_count)
        raise SystemExit(0)

    if args.synthetic_clinical:
        if not out_path:
            raise ValueError("Output file path is required when using --synthetic-clinical")
        generate_synthetic_clinical_vcf(out_path, row_count=args.synthetic_count, seed=args.seed)
        raise SystemExit(0)

    if args.indigen:
        if not args.input_file or not out_path:
            raise ValueError("Input and output files are required when using --indigen")
        convert_indigen_to_patient_vcf(args.input_file, out_path, max_rows=args.max_rows)
        raise SystemExit(0)

    if not args.input_file or not out_path:
        raise ValueError(
            "Input and output files are required unless --generate-demo or --indigen is used."
        )

    in_suffix = Path(args.input_file).suffix.lower()
    out_suffix = Path(out_path).suffix.lower()

    if in_suffix == ".csv" and out_suffix == ".vcf":
        csv_to_patient_vcf(args.input_file, out_path)
    elif in_suffix == ".vcf" and out_suffix == ".csv":
        vcf_to_patient_csv(args.input_file, out_path)
    else:
        raise ValueError(
            "Unsupported conversion. Use CSV -> VCF or VCF -> CSV. "
            "Example: convert_patient_vcf.py patient.csv patient.vcf"
        )
