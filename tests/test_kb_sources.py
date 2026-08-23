import sqlite3
import unittest
from pathlib import Path

from backend.app.db.bootstrap import _normalize_pharmgkb_tier
from backend.app.services.vcf_parser import DB_PATH


class PharmGKBTierCrosswalkTests(unittest.TestCase):
    """PharmGKB/CPIC levels MUST be normalized to the KB Level A-E scale.

    Regression guard for the proven failure mode where raw levels ('1A',
    'CPIC A') were stored verbatim and silently dropped out of the
    frontend's high-confidence filter ('Level A|Level B').
    """

    def test_numeric_levels_map_to_civic_scale(self):
        self.assertEqual(_normalize_pharmgkb_tier("1A"), "Level A")
        self.assertEqual(_normalize_pharmgkb_tier("1B"), "Level B")
        self.assertEqual(_normalize_pharmgkb_tier("2A"), "Level C")
        self.assertEqual(_normalize_pharmgkb_tier("2B"), "Level C")
        self.assertEqual(_normalize_pharmgkb_tier("3"), "Level D")
        self.assertEqual(_normalize_pharmgkb_tier("4"), "Level E")

    def test_prefixed_variants_of_levels_normalize(self):
        self.assertEqual(_normalize_pharmgkb_tier("Level 1A"), "Level A")
        self.assertEqual(_normalize_pharmgkb_tier("pharmgkb 1B"), "Level B")
        self.assertEqual(_normalize_pharmgkb_tier("CPIC A"), "Level A")
        self.assertEqual(_normalize_pharmgkb_tier("cpic d"), "Level D")

    def test_unknown_level_is_unclassified(self):
        self.assertEqual(_normalize_pharmgkb_tier("garbage"), "Unclassified")
        self.assertEqual(_normalize_pharmgkb_tier(""), "Unclassified")


class KnowledgeBaseTierHygieneTests(unittest.TestCase):
    """Every stored tier must conform to 'Level X' or 'Unclassified'.

    Only enforced when a bootstrapped DB exists locally; CI's minimal
    fixture DB also satisfies this trivially.
    """

    def test_all_stored_tiers_are_standardized(self):
        if not Path(DB_PATH).exists():
            self.skipTest("knowledge base not bootstrapped on this machine")
        conn = sqlite3.connect(DB_PATH)
        try:
            rows = conn.execute(
                "SELECT DISTINCT evidence_tier FROM variant_evidence"
            ).fetchall()
        finally:
            conn.close()
        for (tier,) in rows:
            self.assertTrue(
                tier.startswith("Level ") or tier == "Unclassified",
                f"non-standard tier leaked into KB: {tier!r}",
            )


if __name__ == "__main__":
    unittest.main()
