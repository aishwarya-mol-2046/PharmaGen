import type { AnalysisResponse, CohortRow, MatrixRow, ReportRow } from "./types";
import { toReportRow } from "./types";

export const MATRIX_COLUMNS = [
  "Gene",
  "Mutation",
  "Chromosome",
  "Disease",
  "Targeted Drug",
  "Evidence Level",
  "Source",
  "Match Type",
] as const;

export function flattenResults(analysis: AnalysisResponse): MatrixRow[] {
  const rows: MatrixRow[] = [];
  for (const item of analysis.annotated_results) {
    for (const m of item.clinical_matches) {
      rows.push({
        gene: item.variant_info.gene,
        mutation: item.variant_info.mutation,
        chromosome: item.variant_info.chrom,
        disease: m.disease,
        targetedDrug: m.therapy,
        evidenceLevel: m.evidence_tier,
        source: m.source,
        matchType: m.match_type ?? "unknown",
      });
    }
  }
  return rows;
}

/** Collapse identical evidence paths across patients into one row + count. */
export function aggregateCohort(rows: MatrixRow[]): CohortRow[] {
  if (rows.length === 0) return [];
  const groups = new Map<string, CohortRow>();
  for (const r of rows) {
    const key = MATRIX_COLUMNS.map((c) => String(r[MATRIX_KEY[c]])).join("\u0001");
    const existing = groups.get(key);
    if (existing) existing.patients += 1;
    else groups.set(key, { ...r, patients: 1 });
  }
  return [...groups.values()].sort(
    (a, b) => b.patients - a.patients || a.gene.localeCompare(b.gene) || a.mutation.localeCompare(b.mutation),
  );
}

const MATRIX_KEY: Record<(typeof MATRIX_COLUMNS)[number], keyof MatrixRow> = {
  Gene: "gene",
  Mutation: "mutation",
  Chromosome: "chromosome",
  Disease: "disease",
  "Targeted Drug": "targetedDrug",
  "Evidence Level": "evidenceLevel",
  Source: "source",
  "Match Type": "matchType",
};

export function splitByMatch(rows: MatrixRow[]): { exact: MatrixRow[]; contextual: MatrixRow[] } {
  return {
    exact: rows.filter((r) => r.matchType === "exact"),
    contextual: rows.filter((r) => r.matchType === "gene_context"),
  };
}

/** Unique Level A/B exact biomarkers — the high-confidence metric. */
export function highConfidenceCount(rows: MatrixRow[]): number {
  const set = new Set<string>();
  for (const r of rows) {
    if (r.matchType === "exact" && /Level A|Level B/.test(r.evidenceLevel)) {
      set.add(`${r.gene}|${r.mutation}`);
    }
  }
  return set.size;
}

export function topAlteredGenes(rows: MatrixRow[], limit = 12): Array<[string, number]> {
  const counts = new Map<string, number>();
  for (const r of new Map(rows.map((r) => [`${r.gene}|${r.mutation}`, r])).values()) {
    counts.set(r.gene, (counts.get(r.gene) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

export function toCsv(rows: CohortRow[]): string {
  const header = [...MATRIX_COLUMNS, "Patients"].join(",");
  const lines = rows.map((r) =>
    [r.gene, r.mutation, r.chromosome, r.disease, r.targetedDrug, r.evidenceLevel, r.source, r.matchType, r.patients]
      .map(csvEscape)
      .join(","),
  );
  return [header, ...lines].join("\n");
}

function csvEscape(v: string | number): string {
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function reportRows(rows: MatrixRow[]): ReportRow[] {
  return rows.map(toReportRow);
}

export function downloadBlob(data: Blob | string, fileName: string, mime: string): void {
  const blob = typeof data === "string" ? new Blob([data], { type: mime }) : data;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}
