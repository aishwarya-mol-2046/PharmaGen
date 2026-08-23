import asyncio
import unittest

from app.main import export_html_report, export_pdf_report
from fastapi import HTTPException

ROWS = [
    {
        "Gene": "BRAF",
        "Mutation": "V600E",
        "Chromosome": "7",
        "Disease": "Melanoma",
        "Targeted Drug": "Vemurafenib",
        "Evidence Level": "Level A",
        "Source": "CIViC Database",
        "Match Type": "exact",
    },
    {
        "Gene": "BRCA1",
        "Mutation": "V1838E",
        "Chromosome": "17",
        "Disease": "Ovarian Cancer",
        "Targeted Drug": "Olaparib",
        "Evidence Level": "Level A",
        "Source": "OncoKB",
        "Match Type": "gene_context",
    },
]

ANALYSIS = {
    "variants_count": 2,
    "exact_matches": 1,
    "contextual_matches": 1,
    "no_matches": 0,
    "synthetic_data": False,
    "input_validation": {
        "valid_vcf_headers": True,
        "parsed_rows": 2,
        "skipped_rows": 0,
        "duplicate_rows": 0,
        "annotation_coverage_percent": 100.0,
        "patients_observed": 1,
    },
}


class ReportExportEndpointTests(unittest.TestCase):
    def test_pdf_export_returns_pdf_bytes(self):
        response = asyncio.run(
            export_pdf_report({"filename": "demo.vcf", "analysis": ANALYSIS, "rows": ROWS})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF"))

    def test_pdf_export_works_without_analysis_payload(self):
        response = asyncio.run(export_pdf_report({"filename": "demo.vcf", "rows": ROWS}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.body.startswith(b"%PDF"))

    def test_pdf_export_paginates_large_result_sets(self):
        many_rows = [dict(ROWS[0], Mutation=f"V600{i}") for i in range(60)]
        small = asyncio.run(
            export_pdf_report({"filename": "d.vcf", "analysis": ANALYSIS, "rows": ROWS})
        )
        large = asyncio.run(
            export_pdf_report({"filename": "d.vcf", "analysis": ANALYSIS, "rows": many_rows})
        )
        small_pages = small.body.count(b"/Type /Page")
        large_pages = large.body.count(b"/Type /Page")
        self.assertGreater(large_pages, small_pages)

    def test_pdf_export_rejects_empty_rows(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(export_pdf_report({"filename": "demo.vcf", "rows": []}))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_html_export_uses_report_service(self):
        payload = {"filename": "demo.vcf", "analysis": ANALYSIS, "rows": ROWS}
        response = asyncio.run(export_html_report(payload))
        body = response.body.decode("utf-8")
        self.assertEqual(response.media_type, "text/html")
        self.assertIn("PharmaGen Clinical Review", body)
        self.assertIn("demo.vcf", body)
        self.assertIn("BRAF", body)
        self.assertIn("not a diagnosis", body)

    def test_html_export_requires_analysis_and_rows(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(export_html_report({"rows": ROWS}))
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
