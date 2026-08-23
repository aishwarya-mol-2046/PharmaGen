import { useCallback, useEffect, useRef, useState } from "react";
import { fetchKnowledgeBase, type KnowledgeBaseResponse } from "../api";

const PAGE_SIZES = [10, 20, 50];

export default function KnowledgeBase() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [geneFilter, setGeneFilter] = useState("");
  const [tierFilter, setTierFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [data, setData] = useState<KnowledgeBaseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<number | null>(null);

  // Debounce search input
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      setDebouncedQuery(query);
      setPage(1);
    }, 320);
    return () => { if (debounceRef.current) window.clearTimeout(debounceRef.current); };
  }, [query]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchKnowledgeBase({
        page, page_size: pageSize,
        search: debouncedQuery || undefined,
        gene: geneFilter || undefined,
        evidence_tier: tierFilter || undefined,
        source: sourceFilter || undefined,
      });
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, debouncedQuery, geneFilter, tierFilter, sourceFilter]);

  useEffect(() => { void load(); }, [load]);

  const resetFilters = () => {
    setQuery(""); setDebouncedQuery(""); setGeneFilter(""); setTierFilter(""); setSourceFilter(""); setPage(1);
  };

  return (
    <div className="kb-page">
      <div className="kb-header">
        <div>
          <div className="kicker">Browse · search · filter</div>
          <h2 className="kb-title">Clinical Knowledge Base</h2>
          <p className="kb-subtitle">
            Explore the full CIViC + OncoKB evidence catalog — {data?.total.toLocaleString() ?? "…"} curated gene → mutation → disease → therapy links.
            Every row is an exact molecular pairing with its evidence tier and provenance.
          </p>
        </div>
        <div className="kb-stats">
          <div className="kb-stat"><span className="kb-stat-num">{data?.total.toLocaleString() ?? "—"}</span><span className="kb-stat-label">Total records</span></div>
          <div className="kb-stat"><span className="kb-stat-num">{data?.genes.length ?? "—"}</span><span className="kb-stat-label">Genes</span></div>
          <div className="kb-stat"><span className="kb-stat-num">{data?.tiers.length ?? "—"}</span><span className="kb-stat-label">Tiers</span></div>
        </div>
      </div>

      <div className="kb-toolbar">
        <div className="kb-search">
          <input
            type="search"
            placeholder="Search gene, mutation, disease or therapy…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search knowledge base"
          />
        </div>
        <div className="kb-filters">
          <select value={geneFilter} onChange={(e) => { setGeneFilter(e.target.value); setPage(1); }} aria-label="Filter by gene">
            <option value="">All genes</option>
            {(data?.genes ?? []).map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
          <select value={tierFilter} onChange={(e) => { setTierFilter(e.target.value); setPage(1); }} aria-label="Filter by tier">
            <option value="">All tiers</option>
            {(data?.tiers ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={sourceFilter} onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }} aria-label="Filter by source">
            <option value="">All sources</option>
            {(data?.sources ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button className="btn btn--ghost" onClick={resetFilters}>Clear</button>
        </div>
      </div>

      {error && <div className="banner banner--error" role="alert">{error}</div>}
      {loading && <div className="banner banner--info" role="status">Loading knowledge base…</div>}

      {data && (
        <>
          <div className="table-wrap">
            <table className="matrix">
              <thead>
                <tr>
                  <th>Gene</th><th>Mutation</th><th>Disease</th><th>Therapy</th><th>Tier</th><th>Source</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr><td colSpan={6} style={{ textAlign: "center", padding: "1.4rem", color: "var(--ink-soft)", fontStyle: "italic" }}>No records match those filters.</td></tr>
                ) : (
                  data.items.map((r, i) => (
                    <tr key={`${r.gene}-${r.mutation}-${r.disease}-${r.therapy}-${i}`}>
                      <td><strong>{r.gene}</strong></td>
                      <td><code style={{ fontFamily: "var(--mono)", fontSize: "0.82em" }}>{r.mutation}</code></td>
                      <td>{r.disease}</td>
                      <td>{r.therapy}</td>
                      <td><span className={`tier-badge tier-${r.evidence_tier.replace(/\s/g, "")}`}>{r.evidence_tier}</span></td>
                      <td><span style={{ fontFamily: "var(--mono)", fontSize: "0.74em", opacity: 0.8 }}>{r.source}</span></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="kb-pagination">
            <span className="kb-pagination-meta">
              Showing <strong>{data.total === 0 ? 0 : (page - 1) * pageSize + 1}</strong>–<strong>{Math.min(page * pageSize, data.total)}</strong> of <strong>{data.total.toLocaleString()}</strong>
            </span>
            <div className="kb-pagination-controls">
              <button className="btn btn--ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
              {pageButtons(page, data.total_pages).map((p, idx) =>
                p === "..." ? <span key={idx} className="pagination-ellipsis">…</span> : (
                  <button key={p} className={`btn btn--ghost ${p === page ? "is-active" : ""}`} aria-current={p === page ? "page" : undefined} onClick={() => setPage(p as number)}>{p}</button>
                )
              )}
              <button className="btn btn--ghost" disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)}>Next ›</button>
            </div>
            <label className="pagination-size">
              Rows{" "}
              <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}>
                {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </div>
        </>
      )}
    </div>
  );
}

function pageButtons(page: number, total: number): (number | "...")[] {
  const out: (number | "...")[] = [];
  const w = 2;
  for (let i = 1; i <= total; i++) {
    if (i === 1 || i === total || (i >= page - w && i <= page + w)) out.push(i);
    else if (out[out.length - 1] !== "...") out.push("...");
  }
  return out;
}
