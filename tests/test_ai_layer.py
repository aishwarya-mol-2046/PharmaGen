import unittest

from backend.app.services.ai_layer import _local_review


class AiLayerTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {
            "gene": "EGFR",
            "mutation": "L858R",
            "disease": "Non-Small Cell Lung Cancer",
            "therapy": "Osimertinib",
            "evidence_tier": "Level A",
        }

    def test_local_summary_is_grounded(self):
        result = _local_review(self.evidence, "Stage IV NSCLC; reduced kidney function")
        self.assertEqual(result["provider"], "local-review")
        self.assertIn("EGFR L858R", result["summary"])
        self.assertTrue(any("renal" in flag.lower() for flag in result["safety_flags"]))
        self.assertIn("not a diagnosis", result["disclaimer"])


if __name__ == "__main__":
    unittest.main()
