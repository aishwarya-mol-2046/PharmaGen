import unittest
import sqlite3
from pathlib import Path

from backend.app.services.vcf_parser import DB_PATH, VariantAnnotationEngine

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent


def _ensure_test_database():
    """Create a minimal test database if one doesn't exist."""
    db_path = Path(DB_PATH)
    if db_path.exists():
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
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
    test_data = [
        ("BRAF", "V600E", "Melanoma", "Vemurafenib", "Level A", "CIViC"),
        ("EGFR", "L858R", "Non-Small Cell Lung Cancer", "Osimertinib", "Level A", "CIViC"),
        ("KRAS", "G12C", "Non-Small Cell Lung Cancer", "Sotorasib", "Level A", "CIViC"),
        ("ERBB2", "AMPLIFICATION", "Breast Cancer", "Trastuzumab", "Level A", "CIViC"),
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO variant_evidence VALUES (?,?,?,?,?,?)",
        test_data,
    )
    conn.commit()
    conn.close()


class ClinicalWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_test_database()

    def test_exact_match(self):
        matches = VariantAnnotationEngine.match_clinical_evidence("EGFR", "L858R")
        self.assertTrue(matches)
        self.assertTrue(any(match["match_type"] == "exact" for match in matches))

    def test_gene_context_is_not_exact(self):
        matches = VariantAnnotationEngine.match_clinical_evidence("EGFR", "NOT_A_REAL_VARIANT")
        self.assertTrue(matches)
        self.assertTrue(all(match["match_type"] == "gene_context" for match in matches))

    def test_unknown_variant_has_no_match(self):
        matches = VariantAnnotationEngine.match_clinical_evidence("NOT_A_REAL_GENE", "Q999Z")
        self.assertEqual(matches[0]["match_type"], "none")
        self.assertEqual(matches[0]["disease"], "No Direct Match")

    def test_vcf_quality_report(self):
        content = (FIXTURES_DIR / "unmatched_test.vcf").read_bytes()
        variants, report = VariantAnnotationEngine.parse_vcf_stream_detailed(content)
        self.assertEqual(len(variants), 2)
        self.assertTrue(report["valid_vcf_headers"])
        self.assertEqual(report["skipped_rows"], 0)
        self.assertEqual(report["annotation_coverage_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
