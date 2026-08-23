import { useRef, useState } from "react";
import type { HealthResponse } from "../types";

interface Props {
  health: HealthResponse | null;
  apiBase: string | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onFile: (name: string, content: ArrayBuffer) => void;
  activeFileName: string | null;
  allLevels: string[];
  allSources: string[];
  selectedLevels: string[];
  selectedSources: string[];
  onToggleLevel: (level: string) => void;
  onToggleSource: (source: string) => void;
}

export default function Sidebar(props: Props) {
  const {
    health, apiBase, theme, onToggleTheme, onFile, activeFileName,
    allLevels, allSources, selectedLevels, selectedSources,
    onToggleLevel, onToggleSource,
  } = props;

  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const accept = (file: File | undefined) => {
    if (!file) return;
    file
      .arrayBuffer()
      .then((buf) => onFile(file.name, buf))
      .catch(() => onFile(file.name, new ArrayBuffer(0)));
  };

  return (
    <aside className="sidebar">
      <button className="theme-toggle" onClick={onToggleTheme} aria-label="Toggle color mode">
        {theme === "dark" ? "☾ Nightfall" : "☀ Daypaper"}
      </button>

      <h2 className="sidebar-title">Analysis workspace</h2>
      <p className="sidebar-copy">
        Upload a VCF to trace variants through the local clinical evidence base.
      </p>

      <div
        className={`dropzone${dragging ? " dropzone--active" : ""}`}
        role="button" tabIndex={0}
        aria-label="Upload genomics VCF"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          accept(e.dataTransfer.files[0]);
        }}
      >
        <p>{activeFileName ?? "Drop a .vcf / .txt here"}</p>
        <div className="hint">or click to browse — parsed locally, sent only to the API</div>
      </div>
      <input
        ref={inputRef} type="file" accept=".vcf,.txt" hidden
        onChange={(e) => accept(e.target.files?.[0])}
      />

      {apiBase !== null ? (
        <div className="status-chip status-chip--ok">
          <strong>Backend connected</strong>
          {apiBase === "" ? "via proxy (same origin)" : apiBase}
          <br />
          {health?.evidence_records.toLocaleString() ?? "0"} evidence records loaded
        </div>
      ) : (
        <div className="status-chip status-chip--neutral">
          <strong>Backend not connected</strong>
          Start the FastAPI service to enable analysis.
        </div>
      )}

      {(allLevels.length > 0 || allSources.length > 0) && (
        <>
          <hr />
          <div className="filter-group">
            <h3>Filter clinical matrix</h3>
            <div className="chip-row" role="group" aria-label="Evidence tiers">
              {allLevels.map((level) => (
                <button
                  key={level} className="chip"
                  aria-pressed={selectedLevels.includes(level)}
                  onClick={() => onToggleLevel(level)}
                >
                  {level}
                </button>
              ))}
            </div>
          </div>
          <div className="filter-group">
            <div className="chip-row" role="group" aria-label="Evidence sources">
              {allSources.map((source) => (
                <button
                  key={source} className="chip"
                  aria-pressed={selectedSources.includes(source)}
                  onClick={() => onToggleSource(source)}
                >
                  {source}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
