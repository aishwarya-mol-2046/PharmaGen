# Contributing to PharmaGen

## Development Setup

### Quick Start (Recommended)

```bash
# Clone and setup
git clone <repo-url>
cd pharmagen
python3 -m venv .venv && source .venv/bin/activate
make install-dev

# Initialize knowledge base
make bootstrap

# Run tests
make test

# Start development servers
make run
```

### Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
python -m backend.app.db.bootstrap
```

## Development Workflow

### 1. Before Starting Work

- Read `AGENTS.md` for project rules and constraints
- Read `SKILLS.md` for architecture overview and patterns
- Check existing tests to understand expected behavior

### 2. Making Changes

We follow **atomic task boundaries** — keep diffs under 150 lines:

- Single function implementation, OR
- Single test suite addition, OR
- Single endpoint modification

For multi-file changes, produce an RFC first (see SKILLS.md RFC template).

### 3. Code Quality

Automated checks run via pre-commit hooks:

```bash
make lint      # ruff linter
make format    # ruff formatter
make typecheck # mypy type checker
make test      # pytest with coverage
```

### 4. Testing

Every change must have corresponding tests:

- New match type → `tests/test_clinical_workflow.py` case
- AI layer changes → `tests/test_ai_layer.py` with `safety_flags` verification
- VCF parser changes → validate full `validation` dict structure

```bash
make test              # run all tests
make test-coverage     # run with coverage report
```

### 5. Interface Contracts

All service contracts are locked in AGENTS.md. Before modifying any public method:

1. Verify the change doesn't break existing contracts
2. Update type signatures in SKILLS.md if needed
3. Run full test suite to confirm compatibility

## Project Structure

```
pharmagen/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI endpoints
│       └── services/            # Business logic
├── frontend/
│   └── app.py                   # Streamlit UI
├── tests/                       # Test suites
├── AGENTS.md                    # Project rules
├── SKILLS.md                    # Architecture guide
├── Makefile                     # Development commands
├── pyproject.toml               # Tool configuration
└── requirements*.txt            # Dependencies
```

## Common Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install` | Install production dependencies |
| `make install-dev` | Install dev dependencies + pre-commit |
| `make bootstrap` | Initialize clinical knowledge base |
| `make test` | Run all tests |
| `make test-coverage` | Run tests with coverage |
| `make lint` | Run linter |
| `make format` | Format code |
| `make typecheck` | Run type checker |
| `make clean` | Clean generated files |
| `make run` | Start backend + frontend |
| `make backend` | Start backend only |
| `make frontend` | Start frontend only |
| `make demo` | Generate demo VCF |

## Pull Request Checklist

- [ ] Tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Type checking passes (`make typecheck`)
- [ ] No secrets committed
- [ ] New tests added for new functionality
- [ ] Diffs under 150 lines (or RFC attached)
- [ ] Interface contracts respected
