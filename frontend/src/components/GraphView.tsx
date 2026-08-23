import type { ClinicalMatch } from "../types";

/**
 * Focused evidence path: Gene → Mutation → Disease → Drug.
 * Properly aligned, responsive, with wrapped text and consistent typography.
 */
export default function GraphView({ gene, mutation, match }: {
  gene: string;
  mutation: string;
  match: ClinicalMatch;
}) {
  return (
    <div className="graph-frame rise">
      <div className="graph-viewport">
        <svg viewBox="0 0 1000 300" preserveAspectRatio="xMidYMid meet" role="img"
          aria-label={`Evidence path from ${gene} ${mutation} to ${match.therapy}`}>
          <defs>
            <marker id="arrow-graph" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" className="graph-arrow" />
            </marker>
          </defs>

          {/* Subtle horizontal guide */}
          <line x1="40" y1="150" x2="960" y2="150" className="graph-guide" />

          {/* Edges — computed to meet node boundaries */}
          <GraphEdge x1={200} y1={150} x2={310} y2={150} />
          <GraphEdge x1={500} y1={150} x2={610} y2={150} label={match.evidence_tier} />

          {/* Nodes — evenly spaced with proper widths and wrapped text */}
          <GraphNode cx={120} cy={150} label={gene} sub="Gene" variant="gene" />
          <GraphNode cx={400} cy={150} label={mutation} sub="Mutation" variant="mutation" />
          <GraphNode cx={700} cy={150} label={match.disease} sub="Disease" variant="disease" wide />
          <GraphNode cx={890} cy={150} label={match.therapy} sub={match.evidence_tier} variant="drug" wide title={`${match.source} · ${match.evidence_tier}`} />
        </svg>
      </div>
      <div className="graph-caption">
        Why this result appeared: exact match on <b>{gene} + {mutation}</b> ·{" "}
        {match.evidence_tier} · {match.source}. One evidence path — not a diagnosis or an
        independent treatment recommendation.
      </div>
    </div>
  );
}

function GraphEdge({ x1, y1, x2, y2, label }: { x1: number; y1: number; x2: number; y2: number; label?: string }) {
  const mx = (x1 + x2) / 2;
  return (
    <g className="graph-edge">
      <line x1={x1} y1={y1} x2={x2 - 6} y2={y2} className="graph-edge-line" markerEnd="url(#arrow-graph)" />
      {label && (
        <g className="graph-edge-label">
          <rect x={mx - 40} y={y1 - 28} width={80} height={18} rx={9} className="graph-edge-badge" />
          <text x={mx} y={y1 - 18} textAnchor="middle" className="graph-edge-text">{label}</text>
        </g>
      )}
    </g>
  );
}

function GraphNode({ cx, cy, label, sub, variant, wide, title }: {
  cx: number; cy: number; label: string; sub: string; variant: "gene" | "mutation" | "disease" | "drug"; wide?: boolean; title?: string;
}) {
  const isLong = label.length > 22;
  const displayLabel = isLong ? label.slice(0, 22) + "…" : label;
  const fullTitle = title ?? `${sub}: ${label}`;

  // Node dimensions with proper margins
  const w = wide ? 200 : 140;
  const h = 54;
  const rx = variant === "disease" || variant === "drug" ? 6 : variant === "gene" ? w / 2 : 0;

  // Wrap long labels into two lines if needed
  const words = label.split(/[\s,]+/);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const test = current ? current + " " + word : word;
    if (test.length > 18 && current) {
      lines.push(current);
      current = word;
    } else {
      current = test;
    }
    if (lines.length >= 2) break;
  }
  if (current) lines.push(current);
  if (lines.length > 2) {
    lines[1] = lines[1].slice(0, 15) + "…";
    lines.length = 2;
  }
  const useMultiline = lines.length > 1 && label.length > 18;

  let glyph: React.ReactNode;
  const fillClass = `graph-node--${variant}`;

  if (variant === "gene") {
    glyph = <ellipse cx={cx} cy={cy} rx={w / 2} ry={h / 2 + 4} className={fillClass} />;
  } else if (variant === "mutation") {
    const rw = w / 2 + 10, rh = h / 2 + 12;
    glyph = <polygon points={`${cx},${cy - rh} ${cx + rw},${cy} ${cx},${cy + rh} ${cx - rw},${cy}`} className={fillClass} />;
  } else if (variant === "drug") {
    glyph = <Star cx={cx} cy={cy} r={h / 2 + 16} className={fillClass} />;
  } else {
    glyph = <rect x={cx - w / 2} y={cy - h / 2} width={w} height={h} rx={rx} className={fillClass} />;
  }

  return (
    <g className={`graph-node graph-node--${variant}`}>
      <title>{fullTitle}</title>
      {glyph}
      {useMultiline ? (
        <>
          <text x={cx} y={cy - 6} textAnchor="middle" className="graph-node-label">
            {lines[0]}
          </text>
          <text x={cx} y={cy + 8} textAnchor="middle" className="graph-node-label">
            {lines[1]}
          </text>
          <text x={cx} y={cy + 22} textAnchor="middle" className="graph-node-sub">{sub}</text>
        </>
      ) : (
        <>
          <text x={cx} y={cy - 2} textAnchor="middle" className="graph-node-label">
            {displayLabel}
          </text>
          <text x={cx} y={cy + 14} textAnchor="middle" className="graph-node-sub">{sub}</text>
        </>
      )}
    </g>
  );
}

function Star({ cx, cy, r, className }: { cx: number; cy: number; r: number; className?: string }) {
  const spikes = 5, outer = r, inner = r * 0.42;
  const pts: string[] = [];
  for (let i = 0; i < spikes * 2; i++) {
    const rad = i % 2 === 0 ? outer : inner;
    const a = (Math.PI / spikes) * i - Math.PI / 2;
    pts.push(`${(cx + rad * Math.cos(a)).toFixed(1)},${(cy + rad * Math.sin(a)).toFixed(1)}`);
  }
  return <polygon points={pts.join(" ")} className={className} />;
}
