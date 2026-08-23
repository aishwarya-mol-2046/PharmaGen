import { useEffect, useRef, useState } from "react";
import type { HealthResponse } from "../types";

type Page = "console" | "knowledge";
interface Props {
  current: Page;
  onNavigate: (p: Page) => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  health: HealthResponse | null;
  apiBase: string | null;
  pendingFile?: string | null;
}

export default function Navbar({ current, onNavigate, theme, onToggleTheme, health, apiBase }: Props) {
  const [open, setOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);

  // Close mobile menu on route change or outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [open]);

  const isActive = (p: Page) => current === p;

  return (
    <nav className="navbar" ref={navRef} aria-label="Primary">
      <div className="navbar-inner">
        {/* Brand */}
        <button className="navbar-brand" onClick={() => onNavigate("console")} aria-label="Go to console">
          <span className="navbar-logo" aria-hidden="true">
            <svg width="34" height="34" viewBox="0 0 34 34" fill="none">
              <rect width="34" height="34" rx="7" fill="var(--ink)" />
              <path d="M11 7c8 5-8 15 0 20M23 7c-8 5 8 15 0 20M12 12h10M11 17h12M12 22h10" stroke="var(--accent)" strokeWidth="2.1" strokeLinecap="round" />
              <circle cx="17" cy="17" r="2.2" fill="var(--accent)" />
            </svg>
          </span>
          <span className="navbar-wordmark">
            <span className="navbar-title">PharmaGen</span>
            <span className="navbar-subtitle">Evidence Console</span>
          </span>
        </button>

        {/* Desktop links */}
        <div className="navbar-links" role="list">
          <NavLink active={isActive("console")} onClick={() => onNavigate("console")} label="Console" desc="Analyze VCF" />
          <NavLink active={isActive("knowledge")} onClick={() => onNavigate("knowledge")} label="Knowledge Base" desc={`${health?.evidence_records.toLocaleString() ?? "—"} records`} />
        </div>

        {/* Actions */}
        <div className="navbar-actions">
          <span className={`navbar-health ${apiBase !== null ? "navbar-health--ok" : "navbar-health--down"}`} title={apiBase ?? "Backend not connected"}>
            <span className="navbar-health-dot" />
            {apiBase !== null ? `${(health?.evidence_records ?? 0).toLocaleString()} evidence` : "Offline"}
          </span>

          <button className="theme-toggle theme-toggle--nav" onClick={onToggleTheme} aria-label={`Switch to ${theme === "dark" ? "day" : "night"} mode`}>
            <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
            <span className="theme-toggle-label">{theme === "dark" ? "Daypaper" : "Nightfall"}</span>
          </button>

          <button
            className="navbar-burger"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
          >
            <span /><span /><span />
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="navbar-drawer" role="menu">
          <button role="menuitem" className={`navbar-drawer-link ${isActive("console") ? "is-active" : ""}`} onClick={() => { onNavigate("console"); setOpen(false); }}>
            <span className="kicker" style={{ fontSize: "0.58rem" }}>Analyze</span>
            <strong>Console</strong>
          </button>
          <button role="menuitem" className={`navbar-drawer-link ${isActive("knowledge") ? "is-active" : ""}`} onClick={() => { onNavigate("knowledge"); setOpen(false); }}>
            <span className="kicker" style={{ fontSize: "0.58rem" }}>Browse</span>
            <strong>Knowledge Base</strong>
          </button>
          <div className="navbar-drawer-foot">
            <button className="theme-toggle" onClick={onToggleTheme}>
              {theme === "dark" ? "☀ Daypaper" : "☾ Nightfall"}
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}

function NavLink({ active, onClick, label, desc }: { active: boolean; onClick: () => void; label: string; desc: string }) {
  return (
    <button
      className={`navbar-link ${active ? "is-active" : ""}`}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
    >
      <span className="navbar-link-label">{label}</span>
      <span className="navbar-link-desc">{desc}</span>
    </button>
  );
}
