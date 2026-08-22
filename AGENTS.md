# PharmaGen — Agent Rules

## Project Overview

Precision oncology platform: FastAPI backend + Streamlit frontend. Ingests VCF files, matches variants against a CIViC-derived SQLite knowledge base, and surfaces clinical evidence via an interactive knowledge graph.

## Directory Boundaries

```
pharmagen/
├── backend/app/
│   ├── main.py              # FastAPI routes — edit endpoints here
│   ├── services/
│   │   ├── vcf_parser.py    # VCF parsing + evidence matching engine
│   │   ├── graph_engine.py  # PyVis knowledge graph generation
│   │   ├── report_generator.py  # HTML clinical report builder
│   │   └── ai_layer.py      # AI review (local rules + LLM fallback)
│   └── db/
│       └── bootstrap.py     # SQLite init from CIViC TSV
├── frontend/app.py          # Streamlit UI — single-file frontend
├── convert_patient_vcf.py   # CLI: CSV↔VCF + synthetic data generator
├── tests/                   # unittest suites
├── run.sh / run.ps1         # Launch both services
└── .env.example             # Copy to .env, add GROQ_API_KEY
```

**Rule:** Never create files in `backend/data/raw/` — gitignored, populated by `bootstrap.py`. Never add `.env` or `.venv/` to commits.

## CLI Commands

```bash
# Quick start (recommended)
make install-dev   # Install dependencies + pre-commit hooks
make bootstrap     # Populate SQLite KB from CIViC
make run           # Start backend (:8000) + frontend (:8501)

# Manual setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
python -m backend.app.db.bootstrap

# Development
make test          # Run all tests
make test-coverage # Run tests with coverage
make lint          # Run ruff linter
make format        # Format code with ruff
make typecheck     # Run mypy type checker
make clean         # Clean generated files

# Individual services
make backend       # Backend only (uvicorn with reload)
make frontend      # Frontend only (streamlit)

# Data utilities
python convert_patient_vcf.py patient.csv patient.vcf
python convert_patient_vcf.py --generate-demo --demo-count 100 demo.vcf
python convert_patient_vcf.py --synthetic-clinical --synthetic-count 500 synth.vcf

# Docker
docker-compose up  # Run both services in containers
```

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Service classes | PascalCase + `Service`/`Engine` suffix | `VariantAnnotationEngine`, `KnowledgeGraphService` |
| API endpoints | `/api/v1/<resource>` | `/api/v1/analyze`, `/api/v1/ai-review` |
| Match types | lowercase snake_case strings | `"exact"`, `"gene_context"`, `"none"` |
| VCF INFO keys | UPPERCASE | `GENE`, `MUT`, `HGVSP` |
| DB columns | lowercase snake_case | `evidence_tier`, `variant_evidence` |

## Interface Contracts (Locked)

### VariantAnnotationEngine
```python
@staticmethod
def parse_vcf_stream_detailed(file_bytes: bytes) -> tuple[list[dict], dict]:
    # Returns: (variants, validation_report)
    # variant keys: chrom, pos, gene, mutation (all uppercase gene/mutation)
    # validation keys: fileformat_header, column_header, data_rows, parsed_rows,
    #                  skipped_rows, gene_annotated_rows, mutation_annotated_rows,
    #                  duplicate_rows, valid_vcf_headers, annotation_coverage_percent

@staticmethod
def match_clinical_evidence(gene: str, mutation: str, cursor=None) -> list[dict]:
    # Returns list of matches with keys: disease, therapy, evidence_tier, source, match_type
    # match_type ∈ {"exact", "gene_context", "none"}
```

### KnowledgeGraphService
```python
@staticmethod
def generate_interactive_html(annotated_results: list, output_html_path="frontend/graph.html") -> str:
    # Node color schema: Gene=#FF4B4B, Mutation=#FFAA00, Disease=#00C0F2, Drug=#00D47E
```

### AI Layer
```python
def review_evidence(evidence: dict, context: str) -> dict:
    # Required evidence keys: gene, mutation, disease, therapy, evidence_tier
    # Returns: {provider, summary, key_points[], safety_flags[], disclaimer}
```

## Banned Patterns

1. **Never** treat `gene_context` matches as actionable treatment — they lack mutation-level evidence.
2. **Never** call LLM without local fallback — `_llm_review` must degrade to `_local_review` on any failure.
3. **Never** hardcode DB column names — use `PRAGMA table_info` introspection (see `vcf_parser.py:89`).
4. **Never** bypass `parse_vcf_stream_detailed` for validation — the quality report is required by the frontend.
5. **Never** add patient identifiers to logs, AI prompts, or session state.
6. **Never** commit secrets — `.env` stays local; API keys via `os.environ` only.

## Evidence Match Policy

| Match Type | Meaning | Frontend Treatment |
|---|---|---|
| `exact` | Gene + mutation both match | Actionable — shown in matrix |
| `gene_context` | Gene only matches | Contextual — separated with warning |
| `none` | No match | Unmatched — no recommendation |

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `PHARMAGEN_LLM_PROVIDER` | LLM backend selector | `groq` |
| `GROQ_API_KEY` | Groq API key | (required for LLM) |
| `GROQ_MODEL` | Model identifier | `llama-3.3-70b-versatile` |
| `PHARMAGEN_API_URL` | Frontend API override | auto-detect |

## Testing Requirements

- Every new match type must have a corresponding `test_clinical_workflow.py` case.
- AI layer tests must verify `safety_flags` content, not just presence.
- VCF parser tests must validate the full `validation` dict structure.

## Atomic Task Boundaries

Keep diffs under 150 lines. Prefer:
- Single function implementation
- Single test suite addition
- Single endpoint modification

For multi-file changes, produce an RFC first (see SKILLS.md).

## Commit Discipline

**Commit after every stable stage.** A stable stage is defined as:
- A passing test suite after a feature/fix
- A new file/module that compiles and runs without errors
- A refactoring step that preserves existing behavior
- A configuration or tooling change that completes successfully

**Rules:**
1. Run `make test` (or relevant verification) before every commit
2. Commit message must describe what changed and why
3. One logical change per commit — no mixing unrelated fixes
4. If tests fail, do not commit (unless reverting to last known good state)

**Example commit workflow:**
```bash
# After implementing a feature
make test          # verify stable
git add -A
git commit -m "feat: add PDF export endpoint"

# After fixing a bug
make test          # verify fix
make lint          # verify clean
git add -A
git commit -m "fix: handle empty VCF INFO field"
```

**Never leave the repo uncommitted at the end of a session.** Intermediate work should be stashed or committed to a feature branch.
