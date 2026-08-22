import unittest
from pathlib import Path

from backend.app.services.vcf_parser import VariantAnnotationEngine


class ClinicalWorkflowTests(unittest.TestCase):
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
        content = Path("unmatched_test.vcf").read_bytes()
        variants, report = VariantAnnotationEngine.parse_vcf_stream_detailed(content)
        self.assertEqual(len(variants), 2)
        self.assertTrue(report["valid_vcf_headers"])
        self.assertEqual(report["skipped_rows"], 0)
        self.assertEqual(report["annotation_coverage_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
