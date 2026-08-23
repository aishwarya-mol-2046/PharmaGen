import { useState } from "react";
import { requestAiReview } from "../api";
import type { AiReviewResult, ClinicalMatch } from "../types";

export default function AiReview({ gene, mutation, match }: {
  gene: string;
  mutation: string;
  match: ClinicalMatch;
}) {
  const [context, setContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AiReviewResult | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await requestAiReview({
        patient_context: context,
        evidence: {
          gene, mutation,
          disease: match.disease,
          therapy: match.therapy,
          evidence_tier: match.evidence_tier,
          source: match.source,
          match_type: match.match_type,
        },
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <details className="panel">
      <summary>AI-assisted clinical review (optional)</summary>
      <div className="panel-body">
        <p style={{ fontSize: "0.92rem", lineHeight: 1.6, marginBottom: "0.7rem" }}>
          Provide <strong>non-identifying</strong> clinical context to generate a cautious summary
          and context flags. The deterministic knowledge-base match remains the source of truth.
        </p>
        <textarea
          className="context-input"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          placeholder="Example: Age 62; Stage IV NSCLC; prior therapy failure; reduced kidney function"
          aria-label="Clinical patient context"
        />
        <p className="disclaimer">
          Do not enter names, identifiers, or confidential patient data. This is review support,
          not a safety clearance.
        </p>
        <div className="btn-row">
          <button className="btn btn--primary" onClick={run} disabled={busy}>
            {busy ? "Reviewing…" : "Generate summary + flags"}
          </button>
        </div>
        {error && <div className="banner banner--error">{error}</div>}
        {result && (
          <div className="ai-block">
            <p><strong>Provider:</strong> {result.provider}</p>
            <h4>Clinical evidence summary</h4>
            <p style={{ fontSize: "0.94rem", lineHeight: 1.65 }}>{result.summary}</p>
            <h4>Key points</h4>
            <ul>{result.key_points.map((p) => <li key={p}>{p}</li>)}</ul>
            <h4>Context flags for professional review</h4>
            {result.safety_flags.map((f) => (
              <div className="ai-flag" key={f}>{f}</div>
            ))}
            <p className="disclaimer">{result.disclaimer}</p>
          </div>
        )}
      </div>
    </details>
  );
}
