# PharmaGen — Skills & Architecture Guide

## Interface-First Architecture

All service contracts are locked in AGENTS.md. Before implementing any feature:

1. Read the interface contracts in AGENTS.md
2. Verify your implementation matches the exact return types and key names
3. Run existing tests to confirm no contract violations

## Symbol Graph Reference

### Call Hierarchy

```
main.py
├── /health
│   └── sqlite3.connect(DB_PATH)
├── /api/v1/analyze
│   ├── VariantAnnotationEngine.parse_vcf_stream_detailed()
│   ├── VariantAnnotationEngine.match_clinical_evidence()
│   └── returns annotated_results
└── /api/v1/ai-review
    └── review_evidence()
        ├── _llm_review() [optional, degrades gracefully]
        └── _local_review() [fallback, always available]

vcf_parser.py
├── parse_vcf_stream_detailed(file_bytes) → (variants, validation)
│   ├── Parses VCF headers (##fileformat, #CHROM)
│   ├── Extracts INFO fields (GENE, MUT, HGVSP)
│   ├── Deduplicates by (chrom, pos, ref, alt, gene, mutation)
│   └── Returns validation metrics
├── parse_vcf_stream(file_bytes) → variants [deprecated wrapper]
└── match_clinical_evidence(gene, mutation, cursor) → matches
    ├── PRAGMA table_info introspection
    ├── Exact match: gene + mutation
    └── Fallback: gene_context match

graph_engine.py
└── generate_interactive_html(annotated_results, output_html_path) → path
    └── PyVis Network with COLOR_MAP schema

report_generator.py
└── generate_html_report(filename, analysis, rows) → html_string

ai_layer.py
├── review_evidence(evidence, context) → result [public entry]
├── _llm_review(evidence, context) → result | None [optional]
└── _local_review(evidence, context) → result [deterministic fallback]

bootstrap.py
└── init_real_civic_db()
    ├── Fetches CIViC nightly TSV
    ├── Handles modern & legacy column schemas
    └── Falls back to curated panel on network failure
```

### Data Flow

```
VCF Upload → parse_vcf_stream_detailed() → variants[]
                                    ↓
                         match_clinical_evidence() per variant
                                    ↓
                         annotated_results[] → JSON response
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
              Frontend      generate_interactive_html()   review_evidence()
              Matrix        (PyVis graph)                 (AI summary)
```

## Dual-Agent Workflows

### Architect Agent (RFC Mode)

For features touching >2 files or adding new match types:

1. **Produce an RFC** covering:
   - Files to create/modify with line estimates
   - New interface contracts (if any)
   - Edge cases to test (e.g., empty VCF, duplicate rows, missing INFO)
   - Failure modes and rollback strategy
2. **Verify contracts** don't break existing tests
3. **Limit scope** — single feature per RFC

### Worker Agent (Implementation Mode)

For atomic tasks under 150 lines:

1. **Single function** or **single test suite** per execution
2. **Read the relevant interface contract** before coding
3. **Verify with tests** immediately after implementation

### RFC Template

```markdown
## RFC: [Feature Name]

### Scope
- Files to modify: [list with estimated line changes]
- New files: [list]

### Interface Changes
- [ ] New contract needed
- [ ] Existing contract modified (requires version bump)

### Edge Cases
1. [describe]
2. [describe]

### Test Plan
- [ ] test_clinical_workflow.py: [new case]
- [ ] test_ai_layer.py: [new case]

### Rollback
- [how to revert if issues arise]
```

## Type Definitions (Reference)

### Variant Dict
```python
{
    "chrom": str,      # "1", "X", etc.
    "pos": str,        # genomic position
    "gene": str,       # uppercase, e.g., "BRAF"
    "mutation": str    # uppercase, e.g., "V600E"
}
```

### Validation Report Dict
```python
{
    "fileformat_header": bool,
    "column_header": bool,
    "data_rows": int,
    "parsed_rows": int,
    "skipped_rows": int,
    "gene_annotated_rows": int,
    "mutation_annotated_rows": int,
    "duplicate_rows": int,
    "valid_vcf_headers": bool,
    "annotation_coverage_percent": float
}
```

### Clinical Match Dict
```python
{
    "disease": str,
    "therapy": str,
    "evidence_tier": str,
    "source": str,
    "match_type": "exact" | "gene_context" | "none"
}
```

### AI Review Result Dict
```python
{
    "provider": str,           # "local-review" | "groq-llm"
    "summary": str,
    "key_points": list[str],
    "safety_flags": list[str],
    "disclaimer": str          # always from DISCLAIMER constant
}
```

## Common Patterns

### Adding a New Match Type
1. Add to `match_clinical_evidence()` in `vcf_parser.py`
2. Update match policy table in AGENTS.md
3. Add frontend filter in `frontend/app.py`
4. Add test case in `test_clinical_workflow.py`
5. Update `frontend/app.py` matrix display logic

### Adding a New API Endpoint
1. Define in `main.py` with `/api/v1/` prefix
2. Document in AGENTS.md interface contracts
3. Add health check if it touches the database

### Modifying the Knowledge Graph
1. Edit `KnowledgeGraphService.generate_interactive_html()`
2. Maintain COLOR_MAP schema
3. Frontend has separate graph logic — update both if schema changes

## Test Patterns

### VCF Parser Test
```python
def test_vcf_quality_report(self):
    content = Path("fixture.vcf").read_bytes()
    variants, report = VariantAnnotationEngine.parse_vcf_stream_detailed(content)
    self.assertTrue(report["valid_vcf_headers"])
    self.assertEqual(report["parsed_rows"], expected_count)
```

### AI Layer Test
```python
def test_local_review_safety_flags(self):
    result = _local_review(evidence, "reduced kidney function")
    self.assertTrue(any("renal" in f.lower() for f in result["safety_flags"]))
    self.assertIn("not a diagnosis", result["disclaimer"])
```

### Clinical Workflow Test
```python
def test_match_type_behavior(self):
    matches = VariantAnnotationEngine.match_clinical_evidence("GENE", "MUT")
    self.assertTrue(any(m["match_type"] == "expected_type" for m in matches))
```

## File Size Guidelines

| File | Target Lines | Hard Limit |
|---|---|---|
| `backend/app/services/*.py` | <150 | 200 |
| `backend/app/main.py` | <100 | 150 |
| `frontend/app.py` | <400 | 500 |
| `convert_patient_vcf.py` | <300 | 400 |
| Test files | <50 | 100 |

When approaching limits, refactor into helper functions or split modules.
