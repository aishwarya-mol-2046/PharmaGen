import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.services.ai_layer import review_evidence
from app.services.pdf_generator import PDFReportService
from app.services.report_generator import generate_html_report
from app.services.vcf_parser import DB_PATH, VariantAnnotationEngine

app = FastAPI(title="PharmaGen Clinical API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep upload guard small and deterministic for industry demo (<2s path)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@app.on_event("startup")
def create_db_indices():
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_variant_evidence_upper_gene_mut ON variant_evidence (UPPER(gene), UPPER(mutation))"
            )
    except Exception as e:
        print(f"Warning: Failed to create database index: {e}")


@app.get("/health")
async def health_check():
    db_path = Path(DB_PATH)
    if not db_path.exists():
        return {"status": "ok", "knowledge_base": "missing", "evidence_records": 0}
    try:
        with sqlite3.connect(DB_PATH) as connection:
            evidence_count = connection.execute("SELECT COUNT(*) FROM variant_evidence").fetchone()[
                0
            ]
    except sqlite3.OperationalError:
        return {"status": "ok", "knowledge_base": "empty", "evidence_records": 0}
    return {"status": "ok", "knowledge_base": "loaded", "evidence_records": evidence_count}


@app.post("/api/v1/analyze")
# Handles VCF upload, annotates variants with clinical evidence, and returns JSON results
async def analyze_patient_vcf(file: UploadFile = File(...)):
    contents = await file.read()
    if not contents or not contents.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    raw_variants, validation = VariantAnnotationEngine.parse_vcf_stream_detailed(contents)
    if not raw_variants and validation["data_rows"] == 0:
        raise HTTPException(
            status_code=400, detail="No valid VCF variants found. Check headers and data rows."
        )

    if not Path(DB_PATH).exists():
        raise HTTPException(
            status_code=503, detail="Knowledge base not initialized. Run: make bootstrap"
        )
    annotated = []
    # Deduplicate variants to query database only once per unique variant
    unique_variant_keys = {}
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        for v in raw_variants:
            key = (v["gene"].upper(), v["mutation"].upper())
            if key not in unique_variant_keys:
                matches = VariantAnnotationEngine.match_clinical_evidence(
                    v["gene"], v["mutation"], cursor=cursor
                )
                unique_variant_keys[key] = matches

            annotated.append({"variant_info": v, "clinical_matches": unique_variant_keys[key]})

    exact_matches = sum(
        1
        for item in annotated
        if any(match.get("match_type") == "exact" for match in item["clinical_matches"])
    )
    contextual_matches = sum(
        1
        for item in annotated
        if any(match.get("match_type") == "gene_context" for match in item["clinical_matches"])
    )
    no_matches = sum(
        1
        for item in annotated
        if all(match.get("match_type") == "none" for match in item["clinical_matches"])
    )
    synthetic_data = (
        b"##synthetic_data=true" in contents[:8192] or b"SYNTHETIC=1" in contents[:8192]
    )

    return {
        "status": "success",
        "variants_count": len(raw_variants),
        "unique_genes": len({variant["gene"] for variant in raw_variants}),
        "exact_matches": exact_matches,
        "contextual_matches": contextual_matches,
        "no_matches": no_matches,
        "synthetic_data": synthetic_data,
        "input_validation": validation,
        "annotated_results": annotated,
    }


@app.post("/api/v1/ai-review")
async def ai_review(payload: dict):
    evidence = payload.get("evidence") or {}
    context = str(payload.get("patient_context") or "").strip()
    if evidence.get("match_type") != "exact":
        raise HTTPException(
            status_code=400, detail="AI review requires an exact clinical evidence match."
        )
    required = ("gene", "mutation", "disease", "therapy", "evidence_tier")
    if any(not evidence.get(field) for field in required):
        raise HTTPException(status_code=400, detail="Evidence is missing required fields.")
    return review_evidence(evidence, context)


@app.get("/api/v1/knowledge-base")
async def browse_knowledge_base(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    gene: str = "",
    disease: str = "",
    therapy: str = "",
    evidence_tier: str = "",
    source: str = "",
):
    """Browse the clinical knowledge base with pagination and filtering."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    db_path = Path(DB_PATH)
    if not db_path.exists():
        raise HTTPException(
            status_code=503, detail="Knowledge base not initialized. Run: make bootstrap"
        )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            where_clauses = []
            params: list = []

            if search:
                where_clauses.append(
                    "(UPPER(gene) LIKE UPPER(?) OR UPPER(mutation) LIKE UPPER(?) OR UPPER(disease) LIKE UPPER(?) OR UPPER(therapy) LIKE UPPER(?))"
                )
                like = f"%{search}%"
                params.extend([like, like, like, like])
            if gene:
                where_clauses.append("UPPER(gene) = UPPER(?)")
                params.append(gene)
            if disease:
                where_clauses.append("UPPER(disease) LIKE UPPER(?)")
                params.append(f"%{disease}%")
            if therapy:
                where_clauses.append("UPPER(therapy) LIKE UPPER(?)")
                params.append(f"%{therapy}%")
            if evidence_tier:
                where_clauses.append("UPPER(evidence_tier) = UPPER(?)")
                params.append(evidence_tier)
            if source:
                where_clauses.append("UPPER(source) = UPPER(?)")
                params.append(source)

            where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            cur.execute(f"SELECT COUNT(*) FROM variant_evidence{where_sql}", params)
            total = cur.fetchone()[0]

            offset = (page - 1) * page_size
            cur.execute(
                f"SELECT gene, mutation, disease, therapy, evidence_tier, source FROM variant_evidence{where_sql} ORDER BY gene, mutation, disease LIMIT ? OFFSET ?",
                params + [page_size, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT DISTINCT gene FROM variant_evidence ORDER BY gene LIMIT 100")
            genes = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT DISTINCT evidence_tier FROM variant_evidence ORDER BY evidence_tier"
            )
            tiers = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT source FROM variant_evidence ORDER BY source")
            sources = [r[0] for r in cur.fetchall()]

            total_pages = (total + page_size - 1) // page_size if total else 0

            return {
                "items": rows,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "genes": genes,
                "tiers": tiers,
                "sources": sources,
            }
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e


def _report_filename(raw_name, extension: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", Path(raw_name or "").stem) or "pharmagen_report"
    return f"{stem}_clinical_review.{extension}"


@app.post("/api/v1/report/pdf")
async def export_pdf_report(payload: dict):
    rows = payload.get("rows") or []
    if not rows:
        raise HTTPException(status_code=400, detail="No evidence rows supplied for PDF report.")
    analysis = payload.get("analysis") or {}
    validation = analysis.get("input_validation") or {}
    meta = {
        "filename": str(payload.get("filename") or "pharmagen_analysis"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "synthetic_data": bool(analysis.get("synthetic_data", False)),
        "patients_observed": validation.get("patients_observed", 0),
        "validation": validation,
        "summary": {
            "variants_count": analysis.get("variants_count", len(rows)),
            "exact_matches": analysis.get("exact_matches"),
            "contextual_matches": analysis.get("contextual_matches"),
            "no_matches": analysis.get("no_matches"),
        },
    }
    pdf_bytes = PDFReportService.create_clinical_pdf(pd.DataFrame(rows), meta=meta)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="'
            + _report_filename(payload.get("filename"), "pdf")
            + '"'
        },
    )


@app.post("/api/v1/report/html")
async def export_html_report(payload: dict):
    analysis = payload.get("analysis")
    rows = payload.get("rows") or []
    if not isinstance(analysis, dict) or not rows:
        raise HTTPException(
            status_code=400,
            detail="HTML report requires an analysis summary and evidence rows.",
        )
    html = generate_html_report(
        str(payload.get("filename") or "pharmagen_analysis"), analysis, rows
    )
    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Content-Disposition": 'attachment; filename="'
            + _report_filename(payload.get("filename"), "html")
            + '"'
        },
    )
