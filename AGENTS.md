# PharmaGen — Agent Rules

## Project Overview

Precision oncology platform: FastAPI backend + React/TypeScript frontend. Ingests VCF files, matches variants against a hybrid CIViC + OncoKB SQLite knowledge base, and surfaces clinical evidence via an interactive knowledge graph.

## Directory Boundaries

```
pharmagen/
├── backend/app/
│   ├── main.py              # FastAPI routes — edit endpoints here
│   ├── services/
│   │   ├── vcf_parser.py    # VCF parsing + evidence matching engine
│   │   ├── graph_engine.py  # PyVis knowledge graph generation
│   │   ├── report_generator.py  # HTML clinical report builder
│   │   └── pdf_generator.py # PDF clinical report builder (ReportLab)
│   └── db/bootstrap.py      # SQLite KB init: CIViC nightly TSV + OncoKB
├── backend/data/seed/oncokb_seed.csv  # Committed offline OncoKB panel
├── frontend/                # React + TypeScript SPA (Vite) — src/App.tsx entry
├── convert_patient_vcf.py   # CLI: CSV↔VCF + synthetic data generator
├── tests/                   # unittest-style suites, run via pytest
├── run.sh / run.ps1         # Launch both services
└── .env.example             # Copy to .env for local overrides
```

**Rule:** Never create files in `backend/data/raw/` — gitignored, populated by `bootstrap.py`. Never add `.env` or `.venv/` to commits.

## CLI Commands

```bash
source .venv/bin/activate  # always work inside the venv
make install-dev           # deps + pre-commit hooks (no CI exists; hooks are the gate)
make bootstrap             # populate SQLite KB — required before analyze/run
make run                   # backend (:8000) + frontend (:5173)
make test                  # all tests (pytest)
make test-coverage         # fails below 70% backend coverage
make lint | format | typecheck | clean
python convert_patient_vcf.py --generate-demo --demo-count 50 demo.vcf  # demo VCF
```

- Order matters: `/api/v1/analyze` returns **503 until `make bootstrap` has run once**.
- Single test: `python -m pytest tests/test_clinical_workflow.py::ClinicalWorkflowTests::test_exact_match -v`
- Import paths differ by context: backend code uses `from app.services...` (uvicorn runs with `--app-dir backend`); tests use `from backend.app.services...`.

## Knowledge Base Behavior

- `bootstrap.py` downloads the live CIViC nightly TSV (~2,500 records); on network failure it inserts a 4-record fallback panel.
- OncoKB loads **independently of CIViC success**: full GENIE TSV if present (`PHARMAGEN_ONCOKB_FILE`, repo root, or `tests/`), else the committed seed panel. Seed rows use `INSERT OR IGNORE` — they never overwrite existing CIViC evidence for the same key.
- OncoKB tiers are crosswalked to CIViC tiers: Level 1→A, 2→B, 3A/3B→C, 4→D.

## Parsing Gotchas (vcf_parser.py)

- Duplicate detection is cohort-aware: the dedup key includes INFO `SAMPLE`. The same hotspot in different patients is kept as distinct instances; only same-patient repeats count as `duplicate_rows`.
- Mutations are normalized before storage and matching: `p.`/`c.` prefixes and transcript names stripped, 3-letter amino acids translated to 1-letter (`p.Val600Glu` → `V600E`). Raw HGVS input therefore hits the KB directly.
- Extraction order: custom INFO keys (`GENE`/`SYMBOL`, `MUT`/`HGVSP`) → SnpEff `ANN=` → VEP `CSQ=` → known rsID map → `REF>ALT` fallback.

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Service classes | PascalCase + `Service`/`Engine` suffix | `VariantAnnotationEngine`, `PDFReportService` |
| API endpoints | `/api/v1/<resource>` | `/api/v1/analyze`, `/api/v1/knowledge-base` |
| Match types | lowercase snake_case strings | `"exact"`, `"gene_context"`, `"none"` |
| VCF INFO keys | UPPERCASE | `GENE`, `MUT`, `HGVSP` |
| DB columns | lowercase snake_case | `evidence_tier`, `variant_evidence` |

## Interface Contracts (Locked)

### VariantAnnotationEngine
```python
@staticmethod
def parse_vcf_stream_detailed(file_bytes: bytes) -> tuple[list[dict], dict]:
    # Returns: (variants, validation_report)
    # variant keys: chrom, pos, gene, mutation (gene/mutation uppercase)
    # validation keys: fileformat_header, column_header, data_rows, parsed_rows,
    #                  skipped_rows, gene_annotated_rows, mutation_annotated_rows,
    #                  duplicate_rows, valid_vcf_headers, annotation_coverage_percent,
    #                  patients_observed, unique_variant_combinations

@staticmethod
def match_clinical_evidence(gene: str, mutation: str, cursor=None) -> list[dict]:
    # Returns list of matches with keys: disease, therapy, evidence_tier, source, match_type
    # match_type ∈ {"exact", "gene_context", "none"}
    # Pass a shared cursor when matching many variants — /api/v1/analyze queries
    # once per unique (gene, mutation).
```

### KnowledgeGraphService
```python
@staticmethod
def generate_interactive_html(annotated_results: list, output_html_path="frontend/graph.html") -> str:
    # Node color schema: Gene=#FF4B4B, Mutation=#FFAA00, Disease=#00C0F2, Drug=#00D47E
```

## Evidence Match Policy

| Match Type | Meaning | Frontend Treatment |
|---|---|---|
| `exact` | Gene + mutation both match | Actionable — shown in matrix |
| `gene_context` | Gene only matches | Contextual — separated with warning |
| `none` | No match | Unmatched — no recommendation |

## Banned Patterns

1. **Never** treat `gene_context` matches as actionable treatment — they lack mutation-level evidence.
2. **Never** hardcode DB column names — use `PRAGMA table_info` introspection (see `match_clinical_evidence` in `vcf_parser.py`).
3. **Never** bypass `parse_vcf_stream_detailed` for validation — the quality report is required by the frontend.
4. **Never** add patient identifiers to logs or session state.
5. **Never** commit secrets — `.env` stays local; API keys via `os.environ` only.
6. **Never** implement a feature without confirming the approach with the user first.

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `PHARMAGEN_API_URL` | Frontend API override | auto-detect `http://127.0.0.1:8000` |
| `PHARMAGEN_ONCOKB_FILE` | Full OncoKB GENIE TSV path | auto-detect repo root / `tests/` |

## Testing Requirements

- Every new match type must have a corresponding case in `tests/test_clinical_workflow.py`.
- VCF parser tests must validate the full `validation` dict structure, including `patients_observed` and `unique_variant_combinations`.
- `tests/conftest.py` auto-creates a minimal KB if `clinical_kb.db` is missing, so tests pass without bootstrapping.

## Atomic Tasks & Commit Discipline

Keep diffs under 150 lines: single function, single test suite, or single endpoint. For multi-file changes, produce an RFC first (template in SKILLS.md).

Commit after every stable stage — passing tests after a feature/fix, a compiling new module, a behavior-preserving refactor, or completed tooling. Before every commit:

1. Run `make test` (plus `make lint` for code changes). Never commit red.
2. One logical change per commit; message describes what changed and why.
3. Never leave the repo uncommitted at end of session — stash or branch intermediate work.
