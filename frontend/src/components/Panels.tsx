import { useMemo, useState } from "react";
import type { AnalysisResponse, CohortRow, InputValidation, MatrixRow } from "../types";
import { highConfidenceCount, topAlteredGenes } from "../utils";
import Pagination from "./Pagination";

export function MetricsRow({ analysis, patientsObserved }: {
  analysis: AnalysisResponse;
  patientsObserved: number;
}) {
  return (
    <>
      <div className="metrics">
        <MetricCard label="Variants reviewed" value={analysis.variants_count}
          delta={patientsObserved > 1 ? `${patientsObserved} patients` : undefined} />
        <MetricCard label="Exact clinical matches" value={analysis.exact_matches} />
        <MetricCard label="High-confidence exact" value={highConfidenceFrom(analysis)} />
        <MetricCard label="Unique genes" value={analysis.unique_genes} />
      </div>
      <p className="coverage">
        <strong>Analysis coverage:</strong>{" "}
        <code>{analysis.exact_matches}</code> exact matches ·{" "}
        <code>{analysis.contextual_matches}</code> gene-context records ·{" "}
        <code>{analysis.no_matches}</code> unmatched variants
      </p>
    </>
  );
}

function highConfidenceFrom(analysis: AnalysisResponse): number {
  const rows: MatrixRow[] = [];
  for (const item of analysis.annotated_results) {
    for (const m of item.clinical_matches) {
      if (m.match_type !== "exact") continue;
      rows.push({
        gene: item.variant_info.gene, mutation: item.variant_info.mutation,
        chromosome: item.variant_info.chrom, disease: m.disease,
        targetedDrug: m.therapy, evidenceLevel: m.evidence_tier,
        source: m.source, matchType: "exact",
      });
    }
  }
  return highConfidenceCount(rows);
}

function MetricCard({ label, value, delta }: { label: string; value: number; delta?: string }) {
  return (
    <div className="metric-card rise">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value.toLocaleString()}</div>
      {delta && <div className="metric-delta">{delta}</div>}
    </div>
  );
}

export function QualityPanel({ validation }: { validation: InputValidation }) {
  const items: Array<[string, string]> = [
    ["Valid headers", validation.valid_vcf_headers ? "Yes" : "No"],
    ["Rows parsed", validation.parsed_rows.toLocaleString()],
    ["Rows skipped", validation.skipped_rows.toLocaleString()],
    ["Duplicates", validation.duplicate_rows.toLocaleString()],
    ["Annotation coverage", `${validation.annotation_coverage_percent}%`],
  ];
  return (
    <details className="panel">
      <summary>Input quality and evidence policy</summary>
      <div className="panel-body">
        <div className="quality-grid">
          {items.map(([label, value]) => (
            <div className="metric-card" key={label}>
              <div className="metric-label">{label}</div>
              <div className="metric-value">{value}</div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: "0.9rem", lineHeight: 1.6 }}>
          <strong>Evidence source:</strong> local CIViC + OncoKB knowledge base.{" "}
          <strong>Match policy:</strong> exact gene plus exact mutation is actionable; gene-only
          evidence is contextual only; unmatched variants do not receive treatment recommendations.
        </p>
      </div>
    </details>
  );
}

export function CohortSnapshot({ rows }: { rows: MatrixRow[] }) {
  const top = topAlteredGenes(rows);
  const max = Math.max(...top.map(([, n]) => n), 1);
  return (
    <details className="panel">
      <summary>Cohort snapshot — most frequently altered genes</summary>
      <div className="panel-body">
        <svg viewBox={`0 0 ${top.length * 52} 190`} width="100%" height="190" role="img"
          aria-label="Bar chart of most frequently altered genes">
          {top.map(([gene, count], i) => {
            const h = (count / max) * 150;
            return (
              <g key={gene}>
                <rect x={i * 52 + 10} y={160 - h} width={34} height={h}
                  fill="var(--viridian)" opacity={0.85} rx={1}>
                  <title>{`${gene}: ${count}`}</title>
                </rect>
                <text x={i * 52 + 27} y={174} textAnchor="middle"
                  style={{ fill: "var(--ink)", fontSize: 9, fontFamily: "var(--mono)" }}>
                  {gene.length > 7 ? gene.slice(0, 6) + "…" : gene}
                </text>
                <text x={i * 52 + 27} y={155 - h} textAnchor="middle"
                  style={{ fill: "var(--ink-soft)", fontSize: 8.5, fontFamily: "var(--mono)" }}>
                  {count}
                </text>
              </g>
            );
          })}
        </svg>
        <p className="disclaimer">Unique variant count per gene across the uploaded cohort.</p>
      </div>
    </details>
  );
}

export function ContextualPanel({ cohort }: { cohort: CohortRow[] }) {
  if (cohort.length === 0) return null;
  return (
    <details className="panel">
      <summary>View {cohort.length.toLocaleString()} gene-context records (not exact matches)</summary>
      <div className="panel-body">
        <div className="banner banner--warning">
          These records come from other mutations in the same gene. They provide context only and
          must not be interpreted as a treatment recommendation for the uploaded mutation.
        </div>
        <PaginatedTable rows={cohort} />
      </div>
    </details>
  );
}

export function EvidenceTable({ rows }: { rows: CohortRow[] }) {
  if (rows.length === 0) return <p className="empty-note">No records in this selection.</p>;
  return <PaginatedTable rows={rows} />;
}

function PaginatedTable({ rows }: { rows: CohortRow[] }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));

  // Reset to page 1 when data changes
  const rowsKey = rows.length;
  useMemo(() => setPage(1), [rowsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Clamp page if out of range
  const safePage = Math.min(page, totalPages);
  const paginatedRows = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return rows.slice(start, start + pageSize);
  }, [rows, safePage, pageSize]);

  if (rows.length === 0) return <p className="empty-note">No records.</p>;

  return (
    <>
      <div className="table-wrap">
        <table className="matrix">
          <thead>
            <tr>
              {["Gene", "Mutation", "Chromosome", "Disease", "Targeted Drug", "Evidence Level", "Source", "Match", "Patients"].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedRows.map((r, i) => (
              <tr key={`${r.gene}-${r.mutation}-${i}-${safePage}`}>
                <td><strong style={{ fontFamily: "var(--mono)", fontSize: "0.82em" }}>{r.gene}</strong></td>
                <td><code style={{ fontFamily: "var(--mono)", fontSize: "0.82em", background: "color-mix(in srgb, var(--panel2) 60%, transparent)", padding: "0.15rem 0.35rem", borderRadius: "2px" }}>{r.mutation}</code></td>
                <td style={{ fontFamily: "var(--mono)", fontSize: "0.82em", color: "var(--ink-soft)" }}>{r.chromosome}</td>
                <td>{r.disease}</td>
                <td>{r.targetedDrug}</td>
                <td><span className={`tier-badge tier-${r.evidenceLevel.replace(/\s/g, "")}`}>{r.evidenceLevel}</span></td>
                <td><span style={{ fontFamily: "var(--mono)", fontSize: "0.74em", opacity: 0.8 }}>{r.source}</span></td>
                <td>
                  <span className={`match-tag match-tag--${r.matchType === "exact" ? "exact" : "contextual"}`}>
                    {r.matchType}
                  </span>
                </td>
                <td style={{ textAlign: "center", fontWeight: 600 }}>{r.patients}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination
        page={safePage}
        totalPages={totalPages}
        total={rows.length}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
      />
    </>
  );
}
