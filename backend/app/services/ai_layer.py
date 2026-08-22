from __future__ import annotations

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


DISCLAIMER = (
    "AI-generated review support only. Verify the source evidence, current prescribing information, "
    "and patient-specific factors with a qualified oncology professional. This is not a diagnosis "
    "or treatment recommendation."
)


def _local_review(evidence: dict[str, Any], context: str) -> dict[str, Any]:
    gene = evidence.get("gene", "Unknown")
    mutation = evidence.get("mutation", "Unknown")
    disease = evidence.get("disease", "No disease association")
    therapy = evidence.get("therapy", "No therapy")
    tier = evidence.get("evidence_tier", "Unclassified")
    context_lower = context.lower()
    flags = []

    if "kidney" in context_lower or "renal" in context_lower:
        flags.append("Review renal function and product-specific dose guidance before considering therapy.")
    if "liver" in context_lower or "hepatic" in context_lower:
        flags.append("Review hepatic function and product-specific dose guidance before considering therapy.")
    if "prior therapy failure" in context_lower or "progression" in context_lower:
        flags.append("Review prior exposure, resistance history, and sequencing evidence.")
    if not context.strip():
        flags.append("No patient context was supplied; safety cannot be assessed from genomic evidence alone.")
    if not flags:
        flags.append("No rule-based context flag was triggered; this is not a clearance or safety determination.")

    return {
        "provider": "local-review",
        "summary": (
            f"The uploaded finding {gene} {mutation} has an exact {tier} evidence match "
            f"associated with {disease} and {therapy}. This summarizes the database record only."
        ),
        "key_points": [
            f"Exact molecular match: {gene} {mutation}.",
            f"CIViC-derived evidence tier: {tier}.",
            f"Database-associated therapy: {therapy}.",
        ],
        "safety_flags": flags,
        "disclaimer": DISCLAIMER,
    }


def _llm_review(evidence: dict[str, Any], context: str) -> dict[str, Any] | None:
    provider = os.environ.get("PHARMAGEN_LLM_PROVIDER", "groq").strip().lower()
    if provider == "groq":
        endpoint = os.environ.get(
            "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"
        ).strip()
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    else:
        endpoint = os.environ.get("PHARMAGEN_LLM_API_URL", "").strip()
        api_key = os.environ.get("PHARMAGEN_LLM_API_KEY", "").strip()
        model = os.environ.get("PHARMAGEN_LLM_MODEL", "gpt-4o-mini").strip()
    if not endpoint or not api_key:
        return None

    prompt = {
        "role": "system",
        "content": (
            "You are a clinical evidence summarization assistant. Do not diagnose, prescribe, "
            "approve a drug, claim regulatory status, or claim safety. Use only the supplied "
            "evidence and patient context. Say when information is missing. Return ONLY JSON "
            "with summary, key_points (array), safety_flags (array), and disclaimer."
        ),
    }
    user_message = {
        "role": "user",
        "content": json.dumps({"evidence": evidence, "patient_context": context}),
    }
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "temperature": 0.1, "messages": [prompt, user_message]},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if content.strip().startswith("```"):
            content = content.strip().split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(content)
        result["provider"] = f"{provider}-llm"
        result["disclaimer"] = DISCLAIMER
        return result
    except (requests.RequestException, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None


def review_evidence(evidence: dict[str, Any], context: str) -> dict[str, Any]:
    """Summarize one exact match and flag context concerns without making a decision."""
    return _llm_review(evidence, context) or _local_review(evidence, context)
