"""Pytest configuration for PharmaGen tests."""

import sqlite3
from pathlib import Path

import pytest

from backend.app.services.vcf_parser import DB_PATH


@pytest.fixture(scope="session", autouse=True)
def ensure_database():
    """Ensure the database exists before running tests that need it."""
    db_path = Path(DB_PATH)
    if not db_path.exists():
        # Create minimal test database with fallback data
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
                PRIMARY KEY (gene, mutation, therapy, disease)
            )
        """)
        # Insert minimal test data
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
    yield


@pytest.fixture
def fixtures_dir():
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent
