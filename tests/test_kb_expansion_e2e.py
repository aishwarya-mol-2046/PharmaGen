import unittest
import sqlite3
import os
import sys
from pathlib import Path

# Add project root and backend to sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from app.main import app
from app.services.vcf_parser import DB_PATH, VariantAnnotationEngine
from app.services.graph_engine import KnowledgeGraphService
from app.services.report_generator import generate_html_report


class KnowledgeBaseExpansionE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_database_expansion_counts(self):
        """Verify the database has both CIViC and PharmGKB loaded."""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM variant_evidence;")
        total = c.fetchone()[0]
        self.assertGreaterEqual(total, 10000, f"Expected >10,000 records, got {total}")

        c.execute("SELECT COUNT(*) FROM variant_evidence WHERE source='CIViC Database';")
        civic_count = c.fetchone()[0]
        self.assertGreaterEqual(civic_count, 2000, f"Expected >2,000 CIViC records, got {civic_count}")

        c.execute("SELECT COUNT(*) FROM variant_evidence WHERE source='PharmGKB';")
        pharmgkb_count = c.fetchone()[0]
        self.assertGreaterEqual(pharmgkb_count, 8000, f"Expected >8,000 PharmGKB records, got {pharmgkb_count}")
        conn.close()

    def test_02_health_endpoint(self):
        """Verify the FastAPI /health endpoint reports the expanded KB count."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["knowledge_base"], "loaded")
        self.assertGreaterEqual(data["evidence_records"], 10000)

    def test_03_api_analyze_vcf_with_pharmgkb_and_civic(self):
        """Verify /api/v1/analyze processes a multimodal VCF with oncology and PGx variants."""
        vcf_content = b"""##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr7\t140453136\trs121913333\tA\tT\t100\tPASS\tGENE=BRAF;MUT=V600E
chr10\t96541611\trs4244285\tG\tA\t100\tPASS\tGENE=CYP2C19;MUT=*2
chr16\t31022441\trs9923231\tC\tT\t100\tPASS\tGENE=VKORC1;MUT=RS9923231
chr1\t97915614\trs3918290\tC\tT\t100\tPASS\tGENE=DPYD;MUT=RS3918290
chr7\t55259515\trs121434568\tT\tG\t100\tPASS\tGENE=EGFR;MUT=L858R
chr1\t12345\trs99999\tA\tG\t100\tPASS\tGENE=UNKNOWN_GENE;MUT=VAR_X
"""
        response = self.client.post(
            "/api/v1/analyze",
            files={"file": ("patient_test.vcf", vcf_content, "text/plain")}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["variants_count"], 6)
        self.assertEqual(data["unique_genes"], 6)
        self.assertGreaterEqual(data["exact_matches"], 5)
        self.assertEqual(data["no_matches"], 1)

        # Verify sources in the results
        sources_found = set()
        for item in data["annotated_results"]:
            for match in item["clinical_matches"]:
                sources_found.add(match.get("source"))

        self.assertIn("CIViC Database", sources_found)
        self.assertIn("PharmGKB", sources_found)

    def test_04_knowledge_graph_generation(self):
        """Verify knowledge graph engine renders HTML network for expanded results."""
        vcf_content = b"""##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr7\t140453136\trs121913333\tA\tT\t100\tPASS\tGENE=BRAF;MUT=V600E
chr10\t96541611\trs4244285\tG\tA\t100\tPASS\tGENE=CYP2C19;MUT=*2
"""
        variants, _ = VariantAnnotationEngine.parse_vcf_stream_detailed(vcf_content)
        annotated = []
        for v in variants:
            matches = VariantAnnotationEngine.match_clinical_evidence(v["gene"], v["mutation"])
            annotated.append({"variant_info": v, "clinical_matches": matches})

        output_path = "tests/test_graph.html"
        KnowledgeGraphService.generate_interactive_html(annotated, output_html_path=output_path)
        self.assertTrue(os.path.exists(output_path))
        file_content = Path(output_path).read_text(encoding="utf-8")
        self.assertIn("CYP2C19", file_content)
        self.assertIn("BRAF", file_content)
        if os.path.exists(output_path):
            os.remove(output_path)

    def test_05_html_report_generator(self):
        """Verify HTML clinical report generator builds report without errors."""
        sample_analysis = {
            "variants_count": 2,
            "exact_matches": 2,
            "contextual_matches": 0,
            "no_matches": 0,
            "input_validation": {"valid_vcf_headers": True, "parsed_rows": 2, "skipped_rows": 0, "duplicate_rows": 0, "annotation_coverage_percent": 100}
        }
        sample_rows = [
            {"Gene": "CYP2C19", "Mutation": "*2", "Disease": "Clopidogrel Response", "Targeted Drug": "Clopidogrel", "Evidence Level": "Level 1A", "Source": "PharmGKB", "Match Type": "exact"},
            {"Gene": "BRAF", "Mutation": "V600E", "Disease": "Melanoma", "Targeted Drug": "Vemurafenib", "Evidence Level": "Level A", "Source": "CIViC Database", "Match Type": "exact"}
        ]
        report_html = generate_html_report("patient.vcf", sample_analysis, sample_rows)
        self.assertIn("PharmaGen", report_html)
        self.assertIn("CYP2C19", report_html)
        self.assertIn("BRAF", report_html)

    def test_06_hgvs_3letter_to_1letter_and_prefix_stripping(self):
        """Verify translation of 3-letter amino acids (p.Val600Glu -> V600E) and transcript prefixes."""
        vcf_content = b"""##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr7\t140453136\t.\tA\tT\t100\tPASS\tGENE=BRAF;MUT=p.Val600Glu
chr7\t55259515\t.\tT\tG\t100\tPASS\tGENE=EGFR;MUT=ENSP00000275493:p.Leu858Arg
chr12\t25398284\t.\tC\tA\t100\tPASS\tGENE=KRAS;MUT=p.Gly12Cys
"""
        variants, validation = VariantAnnotationEngine.parse_vcf_stream_detailed(vcf_content)
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0]["mutation"], "V600E")
        self.assertEqual(variants[1]["mutation"], "L858R")
        self.assertEqual(variants[2]["mutation"], "G12C")

        # Test clinical matching on translated variants
        for v in variants:
            matches = VariantAnnotationEngine.match_clinical_evidence(v["gene"], v["mutation"])
            self.assertTrue(any(m["match_type"] == "exact" for m in matches))

    def test_07_rsid_extraction_and_matching(self):
        """Verify rsID extraction from ID column and matching against PharmGKB & CIViC."""
        vcf_content = b"""##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr10\t96541611\trs4244285\tG\tA\t100\tPASS\tGENE=CYP2C19
chr16\t31022441\trs9923231\tC\tT\t100\tPASS\tGENE=VKORC1
chr1\t97915614\trs3918290\tC\tT\t100\tPASS\tGENE=DPYD
"""
        variants, _ = VariantAnnotationEngine.parse_vcf_stream_detailed(vcf_content)
        self.assertEqual(variants[0]["mutation"], "RS4244285")
        self.assertEqual(variants[1]["mutation"], "RS9923231")
        self.assertEqual(variants[2]["mutation"], "RS3918290")

        # Verify all match exactly in the knowledge base
        for v in variants:
            matches = VariantAnnotationEngine.match_clinical_evidence(v["gene"], v["mutation"])
            self.assertTrue(any(m["match_type"] == "exact" and m["source"] == "PharmGKB" for m in matches))

    def test_08_csq_and_ann_bioinformatic_annotations(self):
        """Verify VEP (CSQ) and SnpEff (ANN) fields parse gene and mutation properly."""
        vcf_content = b"""##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr7\t140453136\t.\tA\tT\t100\tPASS\tCSQ=T|missense_variant|MODERATE|BRAF|ENSG00000157764|Transcript|ENST00000288602|protein_coding|15/18||ENST00000288602.6:c.1799T>A|ENSP00000288602.6:p.Val600Glu
chr7\t55259515\t.\tT\tG\t100\tPASS\tANN=T|missense_variant|MODERATE|EGFR|ENSG00000146648|transcript|ENST00000275493|protein_coding|21/28|c.2573T>G|p.Leu858Arg
"""
        variants, _ = VariantAnnotationEngine.parse_vcf_stream_detailed(vcf_content)
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0]["gene"], "BRAF")
        self.assertEqual(variants[0]["mutation"], "V600E")
        self.assertEqual(variants[1]["gene"], "EGFR")
        self.assertEqual(variants[1]["mutation"], "L858R")


if __name__ == "__main__":
    unittest.main()
