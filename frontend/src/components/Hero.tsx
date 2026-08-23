import { Fragment, useEffect, useMemo, useRef } from "react";
import { animate, scrambleText } from "animejs";
import { prefersReducedMotion } from "../theme";

interface Pt { x1: number; y: number; x2: number }

function helixPoints(): { d1: string; d2: string; rungs: Pt[] } {
  const cx = 190, A = 52, yTop = 18, yBot = 282, turns = 2.6;
  const total = turns * Math.PI * 2;
  const pt = (t: number): Pt => {
    const y = yTop + ((yBot - yTop) * t) / total;
    return { x1: cx + A * Math.sin(t), y, x2: cx - A * Math.sin(t) };
  };
  let d1 = "", d2 = "";
  const rungs: Pt[] = [];
  for (let s = 0; s <= total + 0.001; s += 0.12) {
    const p = pt(s);
    d1 += `${d1 ? "L" : "M"}${p.x1.toFixed(1)} ${p.y.toFixed(1)} `;
    d2 += `${d2 ? "L" : "M"}${p.x2.toFixed(1)} ${p.y.toFixed(1)} `;
  }
  for (let r = 0; r <= total; r += Math.PI / 7) rungs.push(pt(r));
  return { d1, d2, rungs };
}

const BASES = "ATG CCA GGT TAC CGT AAG TGC ATC GGA TTT CCA GAT ".repeat(6);

export default function Hero() {
  const moveRef = useRef<SVGGElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const { d1, d2, rungs } = useMemo(helixPoints, []);

  // Diagonal roll driven by page scroll (lerped in rAF for smoothness).
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let cur = 0;
    let raf = 0;
    const loop = () => {
      const vh = window.innerHeight || 800;
      const target = Math.min(1, Math.max(0, (vh - rootRef.current?.getBoundingClientRect().top!) / (vh * 1.15)));
      cur += (target - cur) * 0.07;
      moveRef.current?.setAttribute(
        "transform",
        `translate(${(cur * 170).toFixed(1)} ${(cur * 120).toFixed(1)}) rotate(${(cur * 430).toFixed(1)} 190 150)`,
      );
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  // anime.js v4 — settle each headline through a named character preset.
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const timer = setTimeout(() => {
      const targets: Array<[string, string]> = [
        [".hero-kicker", "braille"],
        [".scr-the", "numbers"],
        [".scr-name", "shades"],
        [".scr-tail", "uppercase"],
        [".hero-tag", "lowercase"],
      ];
      targets.forEach(([sel, chars], i) => {
        const el = rootRef.current?.querySelector(sel);
        if (!el) return;
        animate(el as HTMLElement, {
          innerHTML: scrambleText({ chars }),
          duration: 850,
          delay: i * 160,
          ease: "out(3)",
        });
      });
      rootRef.current?.querySelector("h1")?.addEventListener("mouseenter", () => {
        rootRef.current?.querySelectorAll<HTMLElement>(".scr").forEach((el, j) => {
          animate(el, {
            innerHTML: scrambleText({ chars: j === 1 ? "braille" : "a-zA-Z0-9!%#_" }),
            duration: 520,
            delay: j * 70,
            ease: "out(2)",
          });
        });
      });
    }, 1050);
    timers.push(timer);
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="hero" ref={rootRef}>
      <div className="hero-headline">
        <div className="kicker hero-kicker">Precision oncology · evidence archive</div>
        <h1>
          <span className="scr scr-the">The </span>
          <em className="scr scr-name">PharmaGen</em>
          <span className="scr scr-tail"> Console</span>
        </h1>
        <p className="hero-tag">
          From an uploaded variant call to disease context and targeted therapy — an auditable
          trail through the clinical evidence base.
        </p>
      </div>

      <svg className="hero-helix" viewBox="0 0 380 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <g ref={moveRef}>
          <g className="idle-spin">
            <g transform="rotate(-34 190 150)">
              {rungs.map((r, i) => (
                <line
                  key={i}
                  x1={r.x1} y1={r.y} x2={r.x2} y2={r.y}
                  style={{ stroke: i % 2 ? "var(--viridian)" : "var(--accent)" }}
                  strokeWidth={2} opacity={0.55}
                />
              ))}
              <path d={d1} fill="none" style={{ stroke: "var(--ink)" }} strokeWidth={3.2} opacity={0.92} />
              <path d={d2} fill="none" style={{ stroke: "var(--ink)" }} strokeWidth={3.2} opacity={0.92} />
            </g>
          </g>
        </g>
      </svg>

      <div className="hero-cue">scroll · the helix follows <b>↘</b></div>
      <div className="hero-ticker" aria-hidden="true">
        <div className="ticker-inner">
          <span>{BASES}</span>
          <span>
            {BASES.split("G").map((seg, i) => (
              <Fragment key={i}>
                {i > 0 && <b>G</b>}
                {seg}
              </Fragment>
            ))}
          </span>
        </div>
      </div>
    </div>
  );
}
