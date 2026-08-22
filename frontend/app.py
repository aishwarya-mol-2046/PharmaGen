import hashlib
import os
from html import escape

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

API_CANDIDATES = [
    os.environ.get("PHARMAGEN_API_URL", "").strip(),
    "http://127.0.0.1:8000",
]
API_CANDIDATES = [url.rstrip("/") for url in API_CANDIDATES if url]


def resolve_api_base_url():
    for base_url in API_CANDIDATES:
        try:
            response = requests.get(f"{base_url}/health", timeout=1.5)
            if response.ok:
                return base_url, response.json()
        except requests.RequestException:
            continue
    return None, None


st.set_page_config(
    page_title="PharmaGen | Evidence Console",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root {
        --ink: #142b2e;
        --muted: #607779;
        --line: #d8e5e3;
        --paper: #f5f8f6;
        --panel: #ffffff;
        --teal: #0f766e;
        --teal-dark: #0b4f4a;
        --coral: #e76f51;
        --gold: #d29a31;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
    .stApp { background: var(--paper); }
    [data-testid="stHeader"] { background: rgba(245,248,246,0.88); }
    [data-testid="stSidebar"] { background: #102f31; border-right: 1px solid #234b4b; }
    [data-testid="stSidebar"] * { color: #e9f3ef !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] { background: #1a4141; border: 1px solid #356464; }
    [data-testid="stSidebar"] .stFileUploader { background: #173b3b; border: 1px dashed #5c9c91; border-radius: 12px; padding: 0.35rem; }
    .block-container { max-width: 1440px; padding: 2.5rem 4rem 4rem; }
    .brand-kicker, .brand-kicker p { color: #e76f51 !important; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 0.5rem; opacity: 1 !important; }
    .main-header { font-family: 'Space Grotesk', sans-serif; font-size: clamp(2rem, 4vw, 3.7rem); line-height: 1; letter-spacing: -0.04em; font-weight: 700; color: var(--teal-dark); margin-bottom: 0.8rem; }
    .sub-text { font-size: 1.05rem; color: var(--muted); max-width: 690px; margin-bottom: 1.8rem; }
    .hero-rule { height: 5px; width: 74px; background: var(--coral); border-radius: 3px; margin: 0.3rem 0 1.2rem; }
    .section-label { color: var(--teal); font-size: 0.73rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; margin: 1.1rem 0 0.5rem; }
    .status-strip { background: var(--teal-dark); color: #eef8f4; border-radius: 12px; padding: 0.85rem 1rem; margin: 0.3rem 0 1.4rem; font-size: 0.9rem; }
    .status-strip strong { color: #8ce0c3; }
    div[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 1rem 1.1rem; box-shadow: 0 4px 16px rgba(20,43,46,0.05); }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] p { color: var(--muted) !important; font-size: 0.78rem; }
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] div { color: var(--teal-dark) !important; font-family: 'Space Grotesk', sans-serif; }
    div[data-testid="stMetricDelta"] { color: var(--muted) !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 2rem; border-bottom: 1px solid var(--line); }
    .stTabs [data-baseweb="tab"], .stTabs [data-baseweb="tab"] p { color: var(--muted) !important; font-weight: 600; padding: 0.8rem 0; }
    .stTabs [aria-selected="true"], .stTabs [aria-selected="true"] p { color: var(--teal) !important; }
    .stCaption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--muted) !important; }
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { color: var(--ink); }
    [data-testid="stDataFrame"] { color: var(--ink) !important; }
    .stDownloadButton button, .stDownloadButton button p { color: #ffffff !important; background: var(--teal-dark) !important; border: 1px solid var(--teal-dark) !important; font-weight: 700 !important; }
    .stDownloadButton button:hover, .stDownloadButton button:hover p { color: #ffffff !important; background: var(--teal) !important; border-color: var(--teal) !important; }
    .stDataFrame { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
    .evidence-note { color: var(--muted); font-size: 0.86rem; margin: 0.2rem 0 0.8rem; }
    .sidebar-title { font-family: 'Space Grotesk', sans-serif; font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 0.2rem; }
    .sidebar-copy { color: #b5d0cb; font-size: 0.82rem; line-height: 1.5; margin-bottom: 1rem; }
    .sidebar-status { border-radius: 10px; padding: 0.7rem 0.85rem; font-size: 0.82rem; line-height: 1.35; margin: 0.15rem 0 0.9rem; }
    .sidebar-status-ok { background: rgba(140,224,195,0.14); border: 1px solid rgba(140,224,195,0.35); color: #d8fff1; }
    .sidebar-status-neutral { background: rgba(233,248,244,0.08); border: 1px solid rgba(233,248,244,0.16); color: #c7ddd9; }
    @media (max-width: 900px) { .block-container { padding: 2rem 1.1rem 3rem; } .main-header { font-size: 2.3rem; } }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="brand-kicker">Precision oncology / evidence console</div>', unsafe_allow_html=True
)
st.markdown('<div class="main-header">PharmaGen</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-rule"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-text">Translate genomic findings into an auditable treatment evidence trail, from uploaded VCF to disease context and targeted therapy.</div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown('<div class="sidebar-title">Analysis workspace</div>', unsafe_allow_html=True)
st.sidebar.markdown(
    '<div class="sidebar-copy">Upload a VCF to trace variants through the local clinical evidence base.</div>',
    unsafe_allow_html=True,
)
uploaded_file = st.sidebar.file_uploader("Upload genomics VCF", type=["vcf", "txt"])
if uploaded_file:
    current_content = uploaded_file.getvalue()
    current_hash = hashlib.sha256(current_content).hexdigest()
    st.session_state["uploaded_filename"] = uploaded_file.name
    st.session_state["uploaded_content"] = current_content
    st.session_state["uploaded_hash"] = current_hash
else:
    current_content = st.session_state.get("uploaded_content")
    current_hash = st.session_state.get("uploaded_hash")
api_base_url, health_data = resolve_api_base_url()
if api_base_url:
    st.sidebar.markdown(
        f'<div class="sidebar-status sidebar-status-ok"><strong>Backend connected</strong><br>{api_base_url}<br>{health_data.get("evidence_records", 0):,} evidence records loaded</div>',
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        '<div class="sidebar-status sidebar-status-neutral"><strong>Backend not connected yet</strong><br>Start the FastAPI service to enable analysis.</div>',
        unsafe_allow_html=True,
    )
st.sidebar.markdown("---")

if current_content:
    input_filename = uploaded_file.name if uploaded_file else st.session_state["uploaded_filename"]
    input_content = current_content
    input_hash = hashlib.sha256(input_content).hexdigest()
    if st.session_state.get("analysis_file_hash") != input_hash:
        st.session_state.pop("analysis_data", None)
        st.session_state.pop("ai_result", None)
        st.session_state["analysis_file_hash"] = input_hash
    st.markdown(
        f'<div class="status-strip"><strong>Uploaded file active</strong> &nbsp; {input_filename} is being checked against the evidence base.</div>',
        unsafe_allow_html=True,
    )
    if not api_base_url:
        st.error(
            "The backend is not reachable right now. Start the API server, then re-upload the file."
        )
        st.stop()
    if "analysis_data" in st.session_state:
        data = st.session_state["analysis_data"]
        response_content = st.session_state["analysis_response_content"]
    else:
        with st.spinner("Executing Deterministic Evidence Lookup..."):
            try:
                response = requests.post(
                    f"{api_base_url}/api/v1/analyze",
                    files={"file": (input_filename, input_content)},
                )
            except Exception as e:
                st.error(f"Failed to reach FastAPI backend: {e}")
                st.stop()
        if response.status_code != 200:
            st.error(f"API Error {response.status_code}: {response.text}")
            st.stop()
        data = response.json()
        response_content = response.content
        st.session_state["analysis_data"] = data
        st.session_state["analysis_response_content"] = response_content

    if data:
        synthetic_data = data.get("synthetic_data", False)

        if synthetic_data:
            st.info(
                "Synthetic demonstration dataset: genomic coordinates are simulated; clinical relationships come from the local CIViC-derived evidence base."
            )
        elif data.get("exact_matches", 0) > 0:
            st.success(
                f"Annotated genomic input detected · {data['exact_matches']:,} exact clinical matches."
            )
        elif data.get("contextual_matches", 0) > 0:
            st.warning(
                "Input parsed, but no exact gene-plus-mutation matches were found. Contextual gene evidence is shown separately."
            )
        else:
            st.warning("Input parsed, but no direct clinical evidence matches were found.")

        flat_rows = []
        for item in data["annotated_results"]:
            v = item["variant_info"]
            for m in item["clinical_matches"]:
                flat_rows.append(
                    {
                        "Gene": v["gene"],
                        "Mutation": v["mutation"],
                        "Chromosome": v["chrom"],
                        "Disease": m["disease"],
                        "Targeted Drug": m["therapy"],
                        "Evidence Level": m["evidence_tier"],
                        "Source": m["source"],
                        "Match Type": m.get("match_type", "unknown"),
                    }
                )

        matrix_columns = [
            "Gene",
            "Mutation",
            "Chromosome",
            "Disease",
            "Targeted Drug",
            "Evidence Level",
            "Source",
            "Match Type",
        ]
        df = pd.DataFrame(flat_rows, columns=matrix_columns)

        # Cohort aggregation: one row per unique evidence path + patient count.
        # The same hotspot appearing in N patients collapses to a single row with Patients=N.
        def _aggregate_cohort(frame: pd.DataFrame) -> pd.DataFrame:
            if frame.empty:
                return frame
            aggregated = (
                frame.groupby(matrix_columns, dropna=False)
                .size()
                .reset_index(name="Patients")
                .sort_values(["Patients", "Gene", "Mutation"], ascending=[False, True, True], kind="stable")
                .reset_index(drop=True)
            )
            return aggregated

        cohort_df = _aggregate_cohort(df)
        patients_observed = data.get("input_validation", {}).get("patients_observed", 0)

        # Sidebar Filter Controls
        st.sidebar.markdown("---")
        st.sidebar.subheader("Filter Clinical Matrix")
        all_levels = df["Evidence Level"].unique().tolist() if not df.empty else []
        default_levels = all_levels

        selected_levels = st.sidebar.multiselect(
            "Evidence Tiers",
            options=all_levels,
            default=default_levels if default_levels else all_levels,
        )

        all_sources = df["Source"].unique().tolist() if not df.empty else []
        selected_sources = st.sidebar.multiselect(
            "Evidence Sources",
            options=all_sources,
            default=all_sources,
        )

        tier_filtered_df = df[df["Evidence Level"].isin(selected_levels)] if selected_levels else df
        source_filtered_df = (
            tier_filtered_df[tier_filtered_df["Source"].isin(selected_sources)]
            if selected_sources
            else tier_filtered_df
        )
        filtered_df = source_filtered_df[source_filtered_df["Match Type"] == "exact"]
        contextual_df = source_filtered_df[source_filtered_df["Match Type"] == "gene_context"]
        filtered_cohort_df = _aggregate_cohort(filtered_df)
        contextual_cohort_df = _aggregate_cohort(contextual_df)

        st.markdown('<div class="section-label">Evidence overview</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Variants reviewed",
            f"{data['variants_count']:,}",
            delta=f"{patients_observed:,} patients" if patients_observed > 1 else None,
        )
        c2.metric("Exact Clinical Matches", f"{data.get('exact_matches', 0):,}")
        high_confidence_exact = (
            df[
                df["Evidence Level"].str.contains("Level A|Level B", na=False)
                & df["Match Type"].eq("exact")
            ]
            .drop_duplicates(subset=["Gene", "Mutation"])
            if not df.empty
            else df
        )
        c3.metric("High-confidence exact", f"{len(high_confidence_exact):,}")
        c4.metric("Unique genes", f"{data.get('unique_genes', 0):,}")

        st.markdown(
            f"**Analysis coverage:** `{data.get('exact_matches', 0):,}` exact matches · "
            f"`{data.get('contextual_matches', 0):,}` gene-context records · "
            f"`{data.get('no_matches', 0):,}` unmatched variants",
        )

        if patients_observed > 1 and not df.empty:
            with st.expander("Cohort snapshot — most frequently altered genes"):
                top_genes = (
                    df.drop_duplicates(subset=["Gene", "Mutation"])
                    .groupby("Gene")
                    .size()
                    .sort_values(ascending=False)
                    .head(12)
                )
                st.bar_chart(top_genes)
                st.caption(
                    "Unique variant count per gene across the uploaded cohort. "
                    "Frequently altered genes are common drivers (e.g., TP53, PIK3CA) or hotspots."
                )

        validation = data.get("input_validation", {})
        with st.expander("Input quality and evidence policy"):
            quality_cols = st.columns(5)
            quality_cols[0].metric(
                "Valid headers", "Yes" if validation.get("valid_vcf_headers") else "No"
            )
            quality_cols[1].metric("Rows parsed", f"{validation.get('parsed_rows', 0):,}")
            quality_cols[2].metric("Rows skipped", f"{validation.get('skipped_rows', 0):,}")
            quality_cols[3].metric("Duplicates", f"{validation.get('duplicate_rows', 0):,}")
            quality_cols[4].metric(
                "Annotation coverage", f"{validation.get('annotation_coverage_percent', 0)}%"
            )
            st.markdown(
                "**Evidence source:** local CIViC-derived clinical knowledge base. **Match policy:** exact gene plus exact mutation is actionable; gene-only evidence is contextual only; unmatched variants do not receive treatment recommendations."
            )

        st.markdown(
            '<div class="section-label">Clinical interpretation</div>', unsafe_allow_html=True
        )
        t1, t2 = st.tabs(["Actionable Treatment Matrix", "Interactive Knowledge Graph"])

        with t1:
            st.markdown(
                '<div class="evidence-note">Actionable treatment rows require an exact gene-plus-mutation match. Gene-context evidence is kept separate and is not a direct treatment recommendation.</div>',
                unsafe_allow_html=True,
            )
            if filtered_cohort_df.empty:
                st.info("No exact actionable matches in the selected evidence tiers.")
            else:
                st.dataframe(filtered_cohort_df, use_container_width=True, height=420)

            if not contextual_cohort_df.empty:
                with st.expander(
                    f"View {len(contextual_cohort_df):,} gene-context records (not exact matches)"
                ):
                    st.warning(
                        "These records come from other mutations in the same gene. They provide context only and must not be interpreted as a treatment recommendation for the uploaded mutation."
                    )
                    st.dataframe(contextual_cohort_df, use_container_width=True, height=260)

            download_col, report_col = st.columns(2)
            download_col.download_button(
                "Download filtered matrix",
                filtered_cohort_df.to_csv(index=False).encode("utf-8"),
                file_name="pharmagen_evidence_matrix.csv",
                mime="text/csv",
                use_container_width=True,
            )
            report_col.download_button(
                "Download full analysis JSON",
                response_content,
                file_name="pharmagen_analysis.json",
                mime="application/json",
                use_container_width=True,
            )
            exact_report_rows = filtered_df.to_dict("records")
            contextual_report_rows = contextual_df.to_dict("records")
            report_html = f"""<!doctype html><html><head><meta charset='utf-8'><title>PharmaGen Clinical Review</title><style>body{{font-family:Arial;color:#142b2e;margin:40px}}h1{{color:#0b4f4a}}.notice{{padding:14px;background:#e8f5ef;border-left:5px solid #0f766e}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{border:1px solid #d8e5e3;padding:8px;text-align:left}}th{{background:#102f31;color:white}}</style></head><body><h1>PharmaGen Clinical Review</h1><p>File: {escape(input_filename)}</p><p class='notice'><strong>Synthetic/research review:</strong> Demonstration output only. Not a diagnosis or treatment recommendation.</p><p>Variants reviewed: {data["variants_count"]:,} · Exact matches: {data.get("exact_matches", 0):,} · Contextual: {data.get("contextual_matches", 0):,} · Unmatched: {data.get("no_matches", 0):,}</p><h2>Exact clinical evidence</h2>{pd.DataFrame(exact_report_rows).to_html(index=False, border=0) if exact_report_rows else "<p>No exact evidence.</p>"}<h2>Contextual evidence only</h2>{pd.DataFrame(contextual_report_rows).to_html(index=False, border=0) if contextual_report_rows else "<p>No contextual evidence.</p>"}<p>Evidence source: local CIViC-derived clinical knowledge base.</p></body></html>"""
            st.download_button(
                "Download clinical review report",
                report_html.encode("utf-8"),
                file_name="pharmagen_clinical_review.html",
                mime="text/html",
                use_container_width=True,
            )

        with t2:
            exact_records = [
                item
                for item in data["annotated_results"]
                if any(
                    match.get("match_type") == "exact" and match["evidence_tier"] in selected_levels
                    for match in item["clinical_matches"]
                )
            ]
            variant_options = sorted(
                {
                    f"{item['variant_info']['gene']} · {item['variant_info']['mutation']}"
                    for item in exact_records
                }
            )
            if not variant_options:
                st.warning(
                    "No exact gene-plus-mutation matches are available in the selected evidence tiers. Choose another tier or review the matrix."
                )
            else:
                st.caption(
                    f"{len(variant_options):,} matched biomarkers available in the selected evidence tiers"
                )
                selected_variant = st.selectbox(
                    "Choose a matched biomarker to explain", variant_options
                )
                selected_gene, selected_mutation = [
                    part.strip() for part in selected_variant.split(" · ", 1)
                ]
                selected_record = next(
                    item
                    for item in exact_records
                    if item["variant_info"]["gene"] == selected_gene
                    and item["variant_info"]["mutation"] == selected_mutation
                )
                selected_matches = [
                    match
                    for match in selected_record["clinical_matches"]
                    if match.get("match_type") == "exact"
                    and match["evidence_tier"] in selected_levels
                ]
                selected_matches.sort(
                    key=lambda match: (match["evidence_tier"], match["disease"], match["therapy"])
                )
                selected_match = selected_matches[0] if selected_matches else None
                if selected_match is None:
                    st.warning(
                        "The selected biomarker has no match in the currently selected evidence tiers."
                    )
                else:
                    st.markdown(
                        f"**Why this result appeared:** exact match on `{selected_gene}` + `{selected_mutation}` · "
                        f"{selected_match['evidence_tier']} · {selected_match['source']}"
                    )
                    st.caption(
                        "This focused graph explains one evidence path. It is not a diagnosis or an independent treatment recommendation."
                    )

                    with st.expander("AI-assisted clinical review (optional)"):
                        st.markdown(
                            "Provide non-identifying clinical context to generate a cautious summary and context flags. The deterministic CIViC match remains the source of truth."
                        )
                        patient_context = st.text_area(
                            "Clinical patient context",
                            placeholder="Example: Age 62; Stage IV NSCLC; prior therapy failure; reduced kidney function",
                            height=100,
                            key="patient_context",
                        )
                        st.caption(
                            "Do not enter names, identifiers, or confidential patient data. This is review support, not a safety clearance."
                        )
                        if st.button("Generate evidence summary and safety flags", type="primary"):
                            ai_payload = {
                                "patient_context": patient_context,
                                "evidence": {
                                    "gene": selected_gene,
                                    "mutation": selected_mutation,
                                    "disease": selected_match["disease"],
                                    "therapy": selected_match["therapy"],
                                    "evidence_tier": selected_match["evidence_tier"],
                                    "source": selected_match["source"],
                                    "match_type": selected_match.get("match_type"),
                                },
                            }
                            try:
                                ai_response = requests.post(
                                    f"{api_base_url}/api/v1/ai-review", json=ai_payload, timeout=35
                                )
                                if ai_response.ok:
                                    ai_result = ai_response.json()
                                    st.session_state["ai_result"] = ai_result
                                else:
                                    st.error(
                                        f"AI review could not be generated: {ai_response.text}"
                                    )
                            except requests.RequestException as error:
                                st.error(f"AI review service unavailable: {error}")

                        if st.session_state.get("ai_result"):
                            ai_result = st.session_state["ai_result"]
                            st.success(
                                f"Review generated with {ai_result.get('provider', 'local-review')}."
                            )
                            st.markdown(
                                f"**Clinical evidence summary**\n\n{ai_result.get('summary', '')}"
                            )
                            st.markdown("**Key points**")
                            for point in ai_result.get("key_points", []):
                                st.markdown(f"- {point}")
                            st.markdown("**Context flags for professional review**")
                            for flag in ai_result.get("safety_flags", []):
                                st.warning(flag)
                            st.caption(
                                ai_result.get(
                                    "disclaimer",
                                    "AI review support only; verify with a qualified professional.",
                                )
                            )

                    net = Network(
                        height="430px",
                        width="100%",
                        directed=True,
                        bgcolor="#102f31",
                        font_color="#eef8f4",
                    )

                    net.set_options("""
                    var options = {
                        "nodes": {
                                        "font": { "size": 18, "face": "DM Sans", "color": "#eef8f4", "strokeWidth": 3, "strokeColor": "#102f31" },
                                        "borderWidth": 2,
                                        "shadow": true
                      },
                      "edges": {
                                        "arrows": { "to": { "enabled": true, "scaleFactor": 0.7 } },
                                        "color": { "color": "#8ce0c3" },
                                        "width": 2,
                                        "smooth": { "type": "cubicBezier", "forceDirection": "horizontal", "roundness": 0.45 }
                      },
                                    "layout": { "hierarchical": { "enabled": true, "direction": "LR", "sortMethod": "directed", "levelSeparation": 220, "nodeSpacing": 100 } },
                                    "physics": { "enabled": false },
                                    "interaction": { "hover": true, "navigationButtons": true }
                    }
                    """)

                    COLOR_MAP = {
                        "Gene": "#E76F51",
                        "Mutation": "#D29A31",
                        "Disease": "#62B7B0",
                        "Drug": "#8CE0C3",
                    }

                    gene_id = f"Gene:{selected_gene}"
                    mut_id = f"Mut:{selected_gene}_{selected_mutation}"
                    disease_id = f"Disease:{selected_match['disease']}"
                    drug_id = f"Drug:{selected_match['therapy']}"
                    net.add_node(
                        gene_id,
                        label=selected_gene,
                        title="Gene",
                        color=COLOR_MAP["Gene"],
                        shape="ellipse",
                        level=0,
                        size=28,
                    )
                    net.add_node(
                        mut_id,
                        label=selected_mutation,
                        title="Mutation",
                        color=COLOR_MAP["Mutation"],
                        shape="diamond",
                        level=1,
                        size=25,
                    )
                    net.add_node(
                        disease_id,
                        label=selected_match["disease"],
                        title="Disease association",
                        color=COLOR_MAP["Disease"],
                        shape="box",
                        level=2,
                        margin=14,
                    )
                    net.add_node(
                        drug_id,
                        label=selected_match["therapy"],
                        title=f"Therapy | {selected_match['evidence_tier']}",
                        color=COLOR_MAP["Drug"],
                        shape="star",
                        level=3,
                        margin=12,
                    )
                    net.add_edge(gene_id, mut_id, color="#527b78")
                    net.add_edge(mut_id, disease_id, color="#527b78")
                    net.add_edge(disease_id, drug_id, color="#8ce0c3", width=3)
                    # In-memory HTML — no file write, neat and container-safe
                    html_data = net.generate_html(notebook=False)
                    components.html(html_data, height=600)

    else:
        st.error(f"API Error {response.status_code}: {response.text}")
else:
    st.markdown(
        '<div class="status-strip"><strong>Awaiting genomic input</strong> &nbsp; Upload a VCF from the analysis workspace to open the evidence console.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-label">What the console surfaces</div>', unsafe_allow_html=True
    )
    intro = st.columns(3)
    intro[0].markdown(
        "**01 / Variant scan**\n\nExtract gene and mutation signals from the uploaded VCF."
    )
    intro[1].markdown(
        "**02 / Evidence match**\n\nConnect findings to disease, therapy, evidence tier, and source."
    )
    intro[2].markdown(
        "**03 / Explainable graph**\n\nFollow the clinical reasoning path from biomarker to treatment."
    )
