import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Hero from "./components/Hero";
import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import KnowledgeBase from "./components/KnowledgeBase";
import AiReview from "./components/AiReview";
import Downloads from "./components/Downloads";
import GraphView from "./components/GraphView";
import {
  CohortSnapshot, ContextualPanel, EvidenceTable, MetricsRow, QualityPanel,
} from "./components/Panels";
import { analyzeVcf, resolveApiBase, sha256Hex } from "./api";
import { useTheme } from "./theme";
import type { AnalysisResponse, HealthResponse } from "./types";
import { aggregateCohort, flattenResults, splitByMatch } from "./utils";

interface CacheEntry { hash: string; response: AnalysisResponse; raw: string }

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const [currentPage, setCurrentPage] = useState<"console" | "knowledge">("console");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [file, setFile] = useState<{ name: string; content: ArrayBuffer; hash: string } | null>(null);
  const [cache, setCache] = useState<CacheEntry | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestedHash = useRef<string | null>(null);

  useEffect(() => {
    void resolveApiBase().then(({ base, health: h }) => {
      setApiBase(base);
      setHealth(h);
    });
  }, []);

  const handleFile = useCallback(async (name: string, content: ArrayBuffer) => {
    const hash = await sha256Hex(content);
    setError(null);
    setFile({ name, content, hash });
  }, []);

  useEffect(() => {
    if (!file || analyzing) return;
    if (apiBase === null) {
      setError("Backend not connected — is the API running on :8000? Retrying…");
      void resolveApiBase().then(({ base, health: h }) => {
        setApiBase(base);
        setHealth(h);
        if (!base) setError("Backend still not reachable. Start it with: make run  (or uvicorn app.main:app --app-dir backend)");
      });
      return;
    }
    if (cache?.hash === file.hash) return;
    if (requestedHash.current === file.hash) return;
    requestedHash.current = file.hash;
    setAnalyzing(true);
    setError(null);
    analyzeVcf(file.name, file.content)
      .then((response) => setCache({ hash: file.hash, response, raw: JSON.stringify(response) }))
      .catch((e) => {
        requestedHash.current = null;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setAnalyzing(false));
  }, [apiBase, file, cache, analyzing]);

  const analysis = cache && file && cache.hash === file.hash ? cache.response : null;

  const rows = useMemo(() => (analysis ? flattenResults(analysis) : []), [analysis]);
  const { exact, contextual } = useMemo(() => splitByMatch(rows), [rows]);

  const allLevels = useMemo(() => [...new Set(rows.map((r) => r.evidenceLevel))], [rows]);
  const allSources = useMemo(() => [...new Set(rows.map((r) => r.source))].sort(), [rows]);
  const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);

  useEffect(() => { setSelectedLevels(allLevels); }, [allLevels.join("|")]);
  useEffect(() => { setSelectedSources(allSources); }, [allSources.join("|")]);

  const filteredExact = exact.filter(
    (r) => selectedLevels.includes(r.evidenceLevel) && selectedSources.includes(r.source),
  );
  const filteredContextual = contextual.filter(
    (r) => selectedLevels.includes(r.evidenceLevel) && selectedSources.includes(r.source),
  );
  const filteredExactCohort = useMemo(() => aggregateCohort(filteredExact), [filteredExact]);
  const filteredContextualCohort = useMemo(() => aggregateCohort(filteredContextual), [filteredContextual]);

  const biomarkers = useMemo(() => {
    const set = new Set<string>();
    for (const r of filteredExact) set.add(`${r.gene} · ${r.mutation}`);
    return [...set].sort();
  }, [filteredExact]);
  const [biomarker, setBiomarker] = useState<string>("");
  useEffect(() => { setBiomarker(biomarkers[0] ?? ""); }, [biomarkers.join("|")]);
  const graphMatch = useMemo(() => {
    if (!biomarker || !analysis) return null;
    const [g, m] = biomarker.split(" · ");
    const item = analysis.annotated_results.find(
      (a) => a.variant_info.gene === g && a.variant_info.mutation === m,
    );
    return (
      item?.clinical_matches
        .filter((c) => c.match_type === "exact" && selectedLevels.includes(c.evidence_tier))
        .sort((a, b) =>
          a.evidence_tier.localeCompare(b.evidence_tier) ||
          a.disease.localeCompare(b.disease) ||
          a.therapy.localeCompare(b.therapy))[0] ?? null
    );
  }, [biomarker, analysis, selectedLevels]);

  const patientsObserved = analysis?.input_validation.patients_observed ?? 0;

  return (
    <>
      <Navbar
        current={currentPage}
        onNavigate={setCurrentPage}
        theme={theme}
        onToggleTheme={toggleTheme}
        health={health}
        apiBase={apiBase}
      />
      <div className="shell">
        <Sidebar
          health={health} apiBase={apiBase}
          theme={theme} onToggleTheme={toggleTheme}
          onFile={handleFile} activeFileName={file?.name ?? null}
          allLevels={currentPage === "console" ? allLevels : []}
          allSources={currentPage === "console" ? allSources : []}
          selectedLevels={selectedLevels} selectedSources={selectedSources}
          onToggleLevel={(l) => setSelectedLevels((s) => s.includes(l) ? s.filter((x) => x !== l) : [...s, l])}
          onToggleSource={(s) => setSelectedSources((p) => p.includes(s) ? p.filter((x) => x !== s) : [...p, s])}
        />

        <main className="main">
          {currentPage === "knowledge" ? (
            <KnowledgeBase />
          ) : (
            <>
              <Hero />

              {error && (
                <div className="banner banner--error" role="alert">
                  <strong>API error.</strong> {error}
                </div>
              )}

              {!analysis && !error && !analyzing && (
                <>
                  <div className="status-strip status-strip--calm">
                    <strong>Awaiting genomic input</strong> — upload a VCF from the workspace to open the evidence console.
                  </div>
                  <div className="section-label">What the console surfaces</div>
                  <div className="folio-grid">
                    <Folio num="I" title="Variant scan" copy="Gene and mutation signals are extracted from the uploaded VCF — annotated fields, transcript normalization, cohort-aware duplicates." />
                    <Folio num="II" title="Evidence match" copy="Each finding is traced to disease context, targeted therapy, evidence tier, and source across the CIViC + OncoKB knowledge base." />
                    <Folio num="III" title="Explainable graph" copy="Follow one clinical reasoning path — biomarker to mechanism to medicine — rendered as a focused evidence graph." />
                  </div>
                </>
              )}

              {analyzing && (
                <div className="status-strip" role="status">Executing deterministic evidence lookup…</div>
              )}

              {analysis && (
                <>
                  {analysis.synthetic_data ? (
                    <div className="banner banner--info">
                      Synthetic demonstration dataset: genomic coordinates are simulated; clinical
                      relationships come from the local knowledge base.
                    </div>
                  ) : analysis.exact_matches > 0 ? (
                    <div className="banner banner--success">
                      Annotated genomic input detected · {analysis.exact_matches.toLocaleString()} exact clinical matches.
                    </div>
                  ) : (
                    <div className="banner banner--warning">
                      Input parsed, but no exact gene-plus-mutation matches were found. Contextual gene
                      evidence is shown separately.
                    </div>
                  )}

                  <MetricsRow analysis={analysis} patientsObserved={patientsObserved} />

                  {patientsObserved > 1 && <CohortSnapshot rows={rows} />}
                  <QualityPanel validation={analysis.input_validation} />

                  <div className="section-label">Clinical interpretation</div>

                  <h3 style={{ fontFamily: "var(--mono)", fontSize: "0.7rem", letterSpacing: "0.18em", textTransform: "uppercase", margin: "1rem 0 0.6rem", color: "var(--accent)" }}>
                    Actionable treatment matrix
                  </h3>
                  <EvidenceTable rows={filteredExactCohort} />
                  <ContextualPanel cohort={filteredContextualCohort} />

                  <Downloads
                    fileName={file?.name ?? "pharmagen_analysis"}
                    analysis={analysis}
                    validation={analysis.input_validation}
                    exactRows={filteredExact}
                    contextualRows={filteredContextual}
                  />

                  <div className="section-label">Interactive knowledge graph</div>
                  {biomarkers.length === 0 ? (
                    <div className="banner banner--warning">
                      No exact matches available in the selected evidence tiers.
                    </div>
                  ) : (
                    <>
                      <label style={{ display: "block", marginBottom: "0.5rem" }}>
                        <span className="kicker" style={{ display: "block", marginBottom: "0.35rem" }}>
                          Choose a matched biomarker to explain
                        </span>
                        <select
                          className="select-biomarker"
                          value={biomarker}
                          onChange={(e) => setBiomarker(e.target.value)}
                        >
                          {biomarkers.map((b) => <option key={b} value={b}>{b}</option>)}
                        </select>
                      </label>
                      {graphMatch && (
                        <GraphView
                          gene={biomarker.split(" · ")[0]}
                          mutation={biomarker.split(" · ")[1]}
                          match={graphMatch}
                        />
                      )}
                      {graphMatch && (
                        <AiReview
                          gene={biomarker.split(" · ")[0]}
                          mutation={biomarker.split(" · ")[1]}
                          match={graphMatch}
                        />
                      )}
                    </>
                  )}
                </>
              )}
            </>
          )}
        </main>
      </div>
    </>
  );
}

function Folio({ num, title, copy }: { num: string; title: string; copy: string }) {
  return (
    <div className="folio-card">
      <div className="folio-num">{num}</div>
      <div className="folio-title">{title}</div>
      <div className="folio-copy">{copy}</div>
    </div>
  );
}
