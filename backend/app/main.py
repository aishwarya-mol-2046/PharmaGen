import sqlite3
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.services.ai_layer import review_evidence
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

@app.get("/health")
async def health_check():
    db_path = Path(DB_PATH)
    if not db_path.exists():
        return {"status": "ok", "knowledge_base": "missing", "evidence_records": 0}
    try:
        with sqlite3.connect(DB_PATH) as connection:
            evidence_count = connection.execute("SELECT COUNT(*) FROM variant_evidence").fetchone()[0]
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
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB).")
    raw_variants, validation = VariantAnnotationEngine.parse_vcf_stream_detailed(contents)
    if not raw_variants and validation["data_rows"] == 0:
        raise HTTPException(status_code=400, detail="No valid VCF variants found. Check headers and data rows.")

    if not Path(DB_PATH).exists():
        raise HTTPException(status_code=503, detail="Knowledge base not initialized. Run: make bootstrap")
    annotated = []
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        for v in raw_variants:
            matches = VariantAnnotationEngine.match_clinical_evidence(v["gene"], v["mutation"], cursor=cursor)
            annotated.append({"variant_info": v, "clinical_matches": matches})

    exact_matches = sum(
        1 for item in annotated
        if any(match.get("match_type") == "exact" for match in item["clinical_matches"])
    )
    contextual_matches = sum(
        1 for item in annotated
        if any(match.get("match_type") == "gene_context" for match in item["clinical_matches"])
    )
    no_matches = sum(
        1 for item in annotated
        if all(match.get("match_type") == "none" for match in item["clinical_matches"])
    )
    synthetic_data = b"##synthetic_data=true" in contents[:8192] or b"SYNTHETIC=1" in contents[:8192]

    return {
        "status": "success",
        "variants_count": len(raw_variants),
        "unique_genes": len({variant["gene"] for variant in raw_variants}),
        "exact_matches": exact_matches,
        "contextual_matches": contextual_matches,
        "no_matches": no_matches,
        "synthetic_data": synthetic_data,
        "input_validation": validation,
        "annotated_results": annotated
    }


@app.post("/api/v1/ai-review")
async def ai_review(payload: dict):
    evidence = payload.get("evidence") or {}
    context = str(payload.get("patient_context") or "").strip()
    if evidence.get("match_type") != "exact":
        raise HTTPException(status_code=400, detail="AI review requires an exact clinical evidence match.")
    required = ("gene", "mutation", "disease", "therapy", "evidence_tier")
    if any(not evidence.get(field) for field in required):
        raise HTTPException(status_code=400, detail="Evidence is missing required fields.")
    return review_evidence(evidence, context)