from __future__ import annotations

from html import escape


def generate_html_report(filename: str, analysis: dict, rows: list[dict]) -> str:
    validation = analysis.get("input_validation", {})
    exact_rows = [row for row in rows if row.get("Match Type") == "exact"]
    contextual_rows = [row for row in rows if row.get("Match Type") == "gene_context"]

    def table_body(table_rows):
        return "".join(
            "<tr>" + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in (
                "Gene", "Mutation", "Disease", "Targeted Drug", "Evidence Level", "Source", "Match Type"
            )) + "</tr>"
            for row in table_rows
        ) or '<tr><td colspan="7">No records in this section.</td></tr>'

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>PharmaGen Clinical Review</title>
<style>
body {{ font-family: Arial, sans-serif; color: #142b2e; margin: 40px; }}
h1 {{ color: #0b4f4a; margin-bottom: 4px; }} h2 {{ color: #0f766e; margin-top: 30px; }}
.muted {{ color: #607779; }} .notice {{ padding: 14px; background: #e8f5ef; border-left: 5px solid #0f766e; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 24px 0; }}
.metric {{ border: 1px solid #d8e5e3; padding: 14px; }} .metric strong {{ display: block; font-size: 24px; color: #0b4f4a; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }} th, td {{ border: 1px solid #d8e5e3; padding: 8px; text-align: left; }} th {{ background: #102f31; color: white; }}
</style></head><body>
<h1>PharmaGen Clinical Review</h1><div class="muted">Generated from {escape(filename)}</div>
<p class="notice"><strong>Synthetic/research review:</strong> This output supports demonstration and evidence review only. It is not a diagnosis or treatment recommendation.</p>
<div class="grid">
<div class="metric">Variants reviewed<strong>{analysis.get('variants_count', 0):,}</strong></div>
<div class="metric">Exact matches<strong>{analysis.get('exact_matches', 0):,}</strong></div>
<div class="metric">Contextual variants<strong>{analysis.get('contextual_matches', 0):,}</strong></div>
<div class="metric">Unmatched variants<strong>{analysis.get('no_matches', 0):,}</strong></div>
</div>
<h2>Input validation</h2><p>Valid VCF headers: {validation.get('valid_vcf_headers', False)} · Parsed rows: {validation.get('parsed_rows', 0):,} · Skipped rows: {validation.get('skipped_rows', 0):,} · Duplicate rows: {validation.get('duplicate_rows', 0):,} · Annotation coverage: {validation.get('annotation_coverage_percent', 0)}%</p>
<h2>Exact clinical evidence</h2><table><thead><tr><th>Gene</th><th>Mutation</th><th>Disease</th><th>Targeted Drug</th><th>Evidence</th><th>Source</th><th>Match</th></tr></thead><tbody>{table_body(exact_rows)}</tbody></table>
<h2>Contextual evidence only</h2><p class="muted">These records match the gene but not the uploaded mutation and must not be interpreted as treatment recommendations.</p><table><thead><tr><th>Gene</th><th>Mutation</th><th>Disease</th><th>Targeted Drug</th><th>Evidence</th><th>Source</th><th>Match</th></tr></thead><tbody>{table_body(contextual_rows)}</tbody></table>
<p class="muted">Evidence base: local CIViC-derived clinical knowledge base.</p></body></html>"""