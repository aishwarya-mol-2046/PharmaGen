import type { AiReviewResult, AnalysisResponse, HealthResponse } from "./types";

/**
 * API base candidates:
 *  1. VITE_API_URL (Vite-exposed env var, e.g. VITE_API_URL=http://127.0.0.1:8000)
 *  2. Relative origin (via Vite dev proxy) — works when frontend and backend share host
 *  3. Direct localhost fallback for standalone dev
 *
 * Note: legacy PHARMAGEN_API_URL without VITE_ prefix is NOT exposed to the browser
 * by Vite by default; use VITE_API_URL for the frontend. The backend still reads
 * PHARMAGEN_API_URL for its own purposes.
 */
const CANDIDATES = [
  import.meta.env.VITE_API_URL as string | undefined,
  "", // relative via Vite proxy (no CORS)
  "http://127.0.0.1:8000",
]
  .filter((u): u is string => u !== undefined)
  .map((u) => (u === "" ? "" : u.replace(/\/+$/, "")));

let resolvedBase: string | null = null;

export async function resolveApiBase(): Promise<{
  base: string | null;
  health: HealthResponse | null;
}> {
  for (const base of CANDIDATES) {
    const url = base === "" ? "/health" : `${base}/health`;
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        const health = (await res.json()) as HealthResponse;
        resolvedBase = base;
        return { base, health };
      }
    } catch {
      /* probe next candidate */
    }
  }
  resolvedBase = null;
  return { base: null, health: null };
}

function apiBase(): string {
  // Return empty string for relative (proxy) or the resolved absolute URL
  if (resolvedBase === null) throw new Error("API base not resolved — backend not reachable");
  return resolvedBase;
}

function apiUrl(path: string): string {
  const base = apiBase();
  return base === "" ? path : `${base}${path}`;
}

export async function analyzeVcf(
  fileName: string,
  content: ArrayBuffer,
): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append("file", new Blob([content]), fileName);
  const res = await fetch(apiUrl("/api/v1/analyze"), { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    // Surface backend's detail field when present
    try {
      const j = JSON.parse(text) as { detail?: string };
      if (j.detail) throw new Error(j.detail);
    } catch (e) {
      if (e instanceof Error && e.message !== text) throw e;
    }
    throw new Error(`Analyze failed (${res.status}): ${text}`);
  }
  return (await res.json()) as AnalysisResponse;
}

export async function requestPdfReport(body: unknown): Promise<Blob> {
  const res = await fetch(apiUrl("/api/v1/report/pdf"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PDF report failed (${res.status}): ${await res.text()}`);
  return res.blob();
}

export async function requestHtmlReport(body: unknown): Promise<string> {
  const res = await fetch(apiUrl("/api/v1/report/html"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTML report failed (${res.status}): ${await res.text()}`);
  return res.text();
}

export async function requestAiReview(payload: {
  patient_context: string;
  evidence: Record<string, string>;
}): Promise<AiReviewResult> {
  const res = await fetch(apiUrl("/api/v1/ai-review"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as AiReviewResult;
}

export interface KnowledgeBaseParams {
  page?: number;
  page_size?: number;
  search?: string;
  gene?: string;
  disease?: string;
  therapy?: string;
  evidence_tier?: string;
  source?: string;
}

export interface KnowledgeBaseResponse {
  items: Array<{
    gene: string;
    mutation: string;
    disease: string;
    therapy: string;
    evidence_tier: string;
    source: string;
  }>;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  genes: string[];
  tiers: string[];
  sources: string[];
}

export async function fetchKnowledgeBase(
  params: KnowledgeBaseParams = {},
): Promise<KnowledgeBaseResponse> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  if (params.search) searchParams.set("search", params.search);
  if (params.gene) searchParams.set("gene", params.gene);
  if (params.disease) searchParams.set("disease", params.disease);
  if (params.therapy) searchParams.set("therapy", params.therapy);
  if (params.evidence_tier) searchParams.set("evidence_tier", params.evidence_tier);
  if (params.source) searchParams.set("source", params.source);

  const res = await fetch(apiUrl(`/api/v1/knowledge-base?${searchParams.toString()}`));
  if (!res.ok) throw new Error(`Knowledge base fetch failed (${res.status}): ${await res.text()}`);
  return (await res.json()) as KnowledgeBaseResponse;
}

export async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  // crypto.subtle requires secure context (https or localhost); fallback for other hosts
  try {
    if (globalThis.crypto?.subtle) {
      const digest = await crypto.subtle.digest("SHA-256", buf);
      return Array.from(new Uint8Array(digest))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    }
  } catch {
    /* fall through to simple hash */
  }
  // Fallback: fast non-crypto hash based on content length + sampled bytes
  const bytes = new Uint8Array(buf);
  let h = 2166136261;
  const step = Math.max(1, Math.floor(bytes.length / 4096));
  for (let i = 0; i < bytes.length; i += step) {
    h ^= bytes[i]!;
    h = Math.imul(h, 16777619);
  }
  return `${h.toString(16)}-${bytes.length}`;
}
