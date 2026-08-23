# PharmaGen

Precision oncology platform: FastAPI backend + Streamlit frontend. Ingests VCF files, matches variants against a CIViC-derived SQLite knowledge base, and surfaces clinical evidence via an interactive knowledge graph.

## Quick Start

```bash
# Setup (one-time)
python3 -m venv .venv && source .venv/bin/activate
make install-dev

# Initialize knowledge base
make bootstrap

# Run both services
make run
```

Once started:
- Backend API: http://127.0.0.1:8000
- Frontend UI: http://localhost:8501

Press `Ctrl+C` to stop both services.

## Development

### Available Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install` | Install production dependencies |
| `make install-dev` | Install dev dependencies + pre-commit hooks |
| `make bootstrap` | Initialize clinical knowledge base from CIViC |
| `make test` | Run all tests |
| `make test-coverage` | Run tests with coverage report |
| `make lint` | Run ruff linter |
| `make format` | Format code with ruff |
| `make typecheck` | Run mypy type checker |
| `make clean` | Clean generated files |
| `make run` | Start backend + frontend |
| `make backend` | Start backend only |
| `make frontend` | Start frontend only |

### Docker

```bash
docker-compose up
```

### Data Utilities

```bash
# Convert CSV to VCF
python convert_patient_vcf.py patient.csv patient.vcf

# Generate demo VCF with real gene/mutation pairs
python convert_patient_vcf.py --generate-demo --demo-count 100 demo.vcf

# Generate synthetic clinical VCF
python convert_patient_vcf.py --synthetic-clinical --synthetic-count 500 synth.vcf

# Generate combined cohort: 1000 somatic (CIViC/OncoKB) + 120 germline PGx (PharmGKB) rows
python convert_patient_vcf.py --pgx-cohort --somatic-count 1000 --pgx-count 120 --output-file cohort_1000_pgx.vcf
```

### Clinical Knowledge Base (hybrid)

`make bootstrap` builds `backend/data/raw/clinical_kb.db` from multiple sources:

| Source | How it loads | Notes |
|--------|--------------|-------|
| **CIViC** | Live nightly TSV download | ~2,500 evidence records; falls back to a 4-record panel offline |
| **OncoKB** | Full GENIE annotation TSV if available, else committed seed panel | Tier crosswalked: Level 1→A, 2→B, 3A/3B→C, 4→D |
| **PharmGKB** | Full clinical-annotations TSV if available, else committed seed panel | Germline PGx (CYP2C19/clopidogrel, DPYD/5-FU…); levels crosswalked: 1A→A, 1B→B, 2A/2B→C, 3→D, 4→E; CPIC letters A–D map 1:1 |

To load the full OncoKB dataset, drop the GENIE annotation file at the repo root
(`genie_mskcc_samples_with_2017_oncokb_annotation.txt`) or point
`PHARMAGEN_ONCOKB_FILE` at it. For full PharmGKB data, point
`PHARMAGEN_PHARMGKB_FILE` at a clinical-annotations TSV (Gene/Variant/Drug(s)/Level columns).
Without them, curated seed panels ship in-repo (`backend/data/seed/oncokb_seed.csv`,
`backend/data/seed/pharmgkb_seed.csv`) so the hybrid pipeline is demonstrable offline.
Seed rows never overwrite existing evidence for the same key (`INSERT OR IGNORE`),
and every tier from every source is normalized to one `Level A–E` scale before insert.

## Project Structure

```
pharmagen/
├── backend/app/
│   ├── main.py              # FastAPI endpoints
│   └── services/
│       ├── vcf_parser.py    # VCF parsing + evidence matching
│       ├── graph_engine.py  # PyVis knowledge graph
│       ├── report_generator.py  # HTML report builder
│       └── ai_layer.py      # AI review (local + LLM fallback)
├── frontend/app.py          # Streamlit UI
├── tests/                   # Test suites
├── AGENTS.md                # Project rules & constraints
├── SKILLS.md                # Architecture & workflow guide
├── CONTRIBUTING.md          # Contribution guidelines
├── Makefile                 # Development commands
├── pyproject.toml           # Tool configuration
├── requirements.txt         # Production dependencies
└── requirements-dev.txt     # Development dependencies
```

## Documentation

- **[AGENTS.md](AGENTS.md)** — Project rules, naming conventions, interface contracts, banned patterns
- **[SKILLS.md](SKILLS.md)** — Architecture overview, call hierarchy, type definitions, RFC workflow
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Setup instructions, development workflow, PR checklist

## Requirements

- Python 3.9+
- Linux/macOS (or Windows with PowerShell/WSL)

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Add your GROQ_API_KEY for LLM features
```

| Variable | Purpose | Default |
|---|---|---|
| `PHARMAGEN_LLM_PROVIDER` | LLM backend selector | `groq` |
| `GROQ_API_KEY` | Groq API key | (required for LLM) |
| `GROQ_MODEL` | Model identifier | `llama-3.3-70b-versatile` |
| `PHARMAGEN_API_URL` | Frontend API override | auto-detect |
| `PHARMAGEN_ONCOKB_FILE` | Full OncoKB GENIE TSV path (optional) | repo-root auto-detect |
| `PHARMAGEN_PHARMGKB_FILE` | PharmGKB clinical-annotations TSV path (optional) | seed panel |
