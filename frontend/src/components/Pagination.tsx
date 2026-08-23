interface Props {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
}

export default function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
}: Props) {
  if (totalPages <= 1 && !onPageSizeChange) return null;

  const pages: (number | "...")[] = [];
  const windowSize = 2;
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - windowSize && i <= page + windowSize)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== "...") {
      pages.push("...");
    }
  }

  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="pagination">
      <div className="pagination-meta">
        <span>
          Showing <strong>{start}</strong>–<strong>{end}</strong> of <strong>{total.toLocaleString()}</strong>
        </span>
        {onPageSizeChange && (
          <label className="pagination-size">
            Rows per page{" "}
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      {totalPages > 1 && (
        <div className="pagination-controls" role="navigation" aria-label="Pagination">
          <button className="btn btn--ghost" disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="Previous page">‹ Prev</button>
          {pages.map((p, idx) =>
            p === "..." ? (
              <span key={`e-${idx}`} className="pagination-ellipsis">…</span>
            ) : (
              <button
                key={p}
                className={`btn btn--ghost ${p === page ? "is-active" : ""}`}
                aria-current={p === page ? "page" : undefined}
                aria-label={`Page ${p}`}
                onClick={() => onPageChange(p)}
              >
                {p}
              </button>
            ),
          )}
          <button className="btn btn--ghost" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} aria-label="Next page">Next ›</button>
        </div>
      )}
    </div>
  );
}
