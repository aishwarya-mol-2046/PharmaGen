import { useState } from "react";
import { requestHtmlReport, requestPdfReport } from "../api";
import type { AnalysisResponse, CohortRow, InputValidation, MatrixRow } from "../types";
import { buildAnalysisPayload, toReportRow } from "../types";
import { downloadBlob } from "../utils";

export default function Downloads({ fileName, analysis, validation, exactRows, contextualRows }: {
  fileName: string;
  analysis: AnalysisResponse;
  validation: InputValidation;
  exactRows: MatrixRow[];
  contextualRows: MatrixRow[];
}) {
  const [busy, setBusy] = useState<"pdf" | "html" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reportBody = () => ({
    filename: fileName,
    analysis: buildAnalysisPayload(analysis, validation),
    rows: [...exactRows, ...contextualRows].map(toReportRow),
  });

  const runPdf = async () => {
    setBusy("pdf"); setError(null);
    try {
      downloadBlob(await requestPdfReport(reportBody()), "pharmagen_clinical_review.pdf", "application/pdf");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  };

  const runHtml = async () => {
    setBusy("html"); setError(null);
    try {
      downloadBlob(await requestHtmlReport(reportBody()), "pharmagen_clinical_review.html", "text/html");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  };

  return (
    <div>
      <div className="btn-row">
        <CsvButton label="Download filtered matrix" rows={exactRows} />
        <button className="btn" onClick={() =>
          downloadBlob(new Blob([JSON.stringify(analysis, null, 2)], { type: "application/json" }),
            "pharmagen_analysis.json", "application/json")}>
          Download full analysis JSON
        </button>
        <button className="btn" onClick={runPdf} disabled={busy !== null}>
          {busy === "pdf" ? "Building PDF…" : "Generate PDF report"}
        </button>
        <button className="btn" onClick={runHtml} disabled={busy !== null}>
          {busy === "html" ? "Building HTML…" : "Generate clinical review (HTML)"}
        </button>
      </div>
      {error && <div className="banner banner--error">{error}</div>}
    </div>
  );
}

function CsvButton({ label, rows }: { label: string; rows: MatrixRow[] }) {
  const cohort: CohortRow[] = rows.map((r) => ({ ...r, patients: 1 }));
  // collapse duplicates for the CSV the way the matrix does
  const map = new Map<string, CohortRow>();
  for (const r of cohort) {
    const key = `${r.gene}|${r.mutation}|${r.disease}|${r.targetedDrug}|${r.evidenceLevel}|${r.source}`;
    if (map.has(key)) map.get(key)!.patients += 1;
    else map.set(key, r);
  }
  const collapsed = [...map.values()];
  const header = "Gene,Mutation,Chromosome,Disease,Targeted Drug,Evidence Level,Source,Match Type,Patients";
  const csv = [
    header,
    ...collapsed.map((r) =>
      [r.gene, r.mutation, r.chromosome, r.disease, r.targetedDrug, r.evidenceLevel, r.source, r.matchType, r.patients]
        .map((v) => (/[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v)))
        .join(","),
    ),
  ].join("\n");

  return (
    <button className="btn" onClick={() => downloadBlob(csv, "pharmagen_evidence_matrix.csv", "text/csv")}>
      {label}
    </button>
  );
}
