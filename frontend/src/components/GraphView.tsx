import type { ClinicalMatch } from "../types";

/**
 * Focused evidence path: Gene → Mutation → Disease → Drug, rendered as a
 * left-to-right SVG chain with responsive alignment and proper text wrapping.
 */
export default function GraphView({ gene, mutation, match }: {
  gene: string;
  mutation: string;
  match: ClinicalMatch;
}) {
  // Responsive layout calculations
  const nodes = [
    { id: "gene", label: gene, sub: "Gene", fill: "var(--accent)", shape: "ellipse" as const },
    { id: "mut", label: mutation, sub: "Mutation", fill: "var(--gold)", shape: "diamond" as const },
    { id: "disease", label: match.disease, sub: "Disease", fill: "var(--ink-soft)", shape: "rect" as const, wide: true },
    { id: "drug", label: match.therapy, sub: match.evidence_tier, fill: "var(--viridian)", shape: "star" as const },
  ];

  return (
    <div className="graph-frame rise">
      <svg viewBox="0 0 960 280" preserveAspectRatio="xMidYMid meet" width="100%" role="img"
        aria-label={`Evidence path from ${gene} ${mutation} to ${match.therapy}`}
        style={{ display: "block", maxWidth: "100%", height: "auto" }}>
        <defs>
          <marker id="arrow-graph" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" style={{ fill: "var(--ink-soft)" }} />
          </marker>
        </defs>

        {/* Background grid for alignment reference */}
        <g opacity="0.04">
          <line x1="0" y1="140" x2="960" y2="140" stroke="var(--line-hard)" strokeWidth="1" strokeDasharray="4 4" />
        </g>

        {/* Edges with proper alignment */}
        <Edge x1={165} y1={140} x2={295} y2={140} />
        <Edge x1={455} y1={140} x2={585} y2={140} label={match.evidence_tier} />

        {/* Nodes */}
        <Node cx={90} cy={140} {...nodes[0]} labelWidth={Math.max(gene.length, 6)} />
        <Node cx={380} cy={140} {...nodes[1]} labelWidth={Math.max(mutation.length, 7)} />
        <Node cx={670} cy={140} {...nodes[2]} labelWidth={18} wide />
        <Node cx={880} cy={140} {...nodes[3]} labelWidth={16} title={`${match.source} · ${match.evidence_tier}`} />
      </svg>
      <div className="graph-caption">
        Why this result appeared: exact match on <b>{gene} + {mutation}</b> ·{" "}
        {match.evidence_tier} · {match.source}. One evidence path — not a diagnosis or an
        independent treatment recommendation.
      </div>
    </div>
  );
}

function Edge({ x1, y1, x2, y2, label }: { x1: number; y1: number; x2: number; y2: number; label?: string }) {
  const mx = (x1 + x2) / 2;
  const my = y1 - 18;
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2 - 6} y2={y2}
        style={{ stroke: "var(--ink-soft)" }} strokeWidth={2.2} strokeLinecap="round" markerEnd="url(#arrow-graph)" />
      {label && (
        <g>
          <rect x={mx - 38} y={my - 10} width={76} height={16} rx={8} fill="var(--panel)" stroke="var(--viridian)" strokeWidth={1} />
          <text x={mx} y={my} dy="0.35em" textAnchor="middle"
            style={{ fill: "var(--viridian)", fontSize: 9.5, fontFamily: "var(--mono)", fontWeight: 600 }}>
            {label}
          </text>
        </g>
      )}
    </g>
  );
}

function Node({ cx, cy, shape, fill, label, sub, wide, labelWidth = 8, title }: {
  cx: number; cy: number;
  shape: "ellipse" | "diamond" | "rect" | "star";
  fill: string; label: string; sub: string;
  wide?: boolean; labelWidth?: number; title?: string;
}) {
  const w = Math.min(Math.max(labelWidth * 8.2 + 28, 76), wide ? 260 : 180);
  const h = 46;
  const textColor = shape === "rect" && fill === "var(--ink-soft)" ? "#fbf8ef" : "#fbf8ef";

  // For diamond/star, ensure text remains centered
  let glyph: React.ReactNode;
  if (shape === "ellipse") {
    glyph = <ellipse cx={cx} cy={cy} rx={w / 2} ry={h / 2 + 5} style={{ fill }} />;
  } else if (shape === "diamond") {
    const rw = w / 2 + 8, rh = h / 2 + 10;
    glyph = <polygon points={`${cx},${cy - rh} ${cx + rw},${cy} ${cx},${cy + rh} ${cx - rw},${cy}`} style={{ fill }} />;
  } else if (shape === "star") {
    glyph = <Star cx={cx} cy={cy} r={h / 2 + 14} style={{ fill }} />;
  } else {
    const rw = wide ? 240 : w;
    glyph = <rect x={cx - rw / 2} y={cy - h / 2} width={rw} height={h} rx={4} style={{ fill }} />;
  }

  // Smart label truncation with tooltip
  const displayLabel = label.length > 28 ? label.slice(0, 27) + "…" : label;
  const isTruncated = label.length > 28;

  return (
    <g>
      {isTruncated && title ? <title>{title}</title> : <title>{`${sub}: ${label}`}</title>}
      {glyph}
      <text x={cx} y={cy - 3} textAnchor="middle"
        style={{ fill: textColor, fontSize: 13.5, fontFamily: "var(--serif-display)", fontWeight: 600 }}>
        {displayLabel}
      </text>
      <text x={cx} y={cy + 13} textAnchor="middle"
        style={{ fill: textColor, opacity: 0.9, fontSize: 8.5, fontFamily: "var(--mono)", letterSpacing: "0.14em", textTransform: "uppercase" }}>
        {sub}
      </text>
    </g>
  );
}

function Star({ cx, cy, r, style }: { cx: number; cy: number; r: number; style?: React.CSSProperties }) {
  const spikes = 5, outer = r, inner = r * 0.42;
  const pts: string[] = [];
  for (let i = 0; i < spikes * 2; i++) {
    const rad = i % 2 === 0 ? outer : inner;
    const a = (Math.PI / spikes) * i - Math.PI / 2;
    pts.push(`${(cx + rad * Math.cos(a)).toFixed(1)},${(cy + rad * Math.sin(a)).toFixed(1)}`);
  }
  return <polygon points={pts.join(" ")} style={style} />;
}
