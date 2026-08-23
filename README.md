# PharmaGen

Precision oncology platform: FastAPI backend + React/TypeScript frontend. Ingests VCF files, matches variants against a CIViC-derived SQLite knowledge base, and surfaces clinical evidence via an interactive knowledge graph.

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
- Frontend UI: http://localhost:5173

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
```

### Clinical Knowledge Base (hybrid)

`make bootstrap` builds `backend/data/raw/clinical_kb.db` from multiple sources:

| Source | How it loads | Notes |
|--------|--------------|-------|
| **CIViC** | Live nightly TSV download | ~2,500 evidence records; falls back to a 4-record panel offline |
| **OncoKB** | Full GENIE annotation TSV if available, else committed seed panel | Tier crosswalked: Level 1→A, 2→B, 3A/3B→C, 4→D |

To load the full OncoKB dataset, drop the GENIE annotation file at the repo root
(`genie_mskcc_samples_with_2017_oncokb_annotation.txt`) or point
`PHARMAGEN_ONCOKB_FILE` at it. Without it, a curated 27-row seed panel of
standard-of-care Level A/B pairings ships in-repo (`backend/data/seed/oncokb_seed.csv`)
so the hybrid pipeline is demonstrable offline. Seed rows never overwrite
existing CIViC evidence for the same key.

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
├── frontend/                # React + TypeScript SPA (Vite)
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
