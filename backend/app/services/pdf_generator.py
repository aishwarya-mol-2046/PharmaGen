import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DISCLAIMER = (
    "Synthetic/research review: this document supports demonstration and evidence review only. "
    "It is not a diagnosis or a treatment recommendation. Verify source evidence, current "
    "prescribing information, and patient-specific factors with a qualified oncology professional."
)
FOOTER_NOTE = "For evidence review only — not a diagnosis or treatment recommendation."

TIER_GUIDE = [
    (
        "Level A",
        "Validated in professional guidelines or FDA-recognized; strongest clinical evidence.",
    ),
    ("Level B", "Supported by well-powered clinical trials or peer-reviewed clinical studies."),
    ("Level C", "Evidence from case studies or small series; emerging clinical support."),
    ("Level D", "Preclinical evidence only (cell lines, xenografts, functional studies)."),
]

_COLUMNS = [
    "Gene",
    "Mutation",
    "Chromosome",
    "Disease",
    "Targeted Drug",
    "Evidence Level",
    "Source",
]
_WIDTHS = {
    "Gene": 58,
    "Mutation": 64,
    "Chromosome": 52,
    "Disease": 142,
    "Targeted Drug": 126,
    "Evidence Level": 56,
    "Source": 54,
}


def _cell_style(header=False):
    return ParagraphStyle(
        "HeaderCell" if header else "BodyCell",
        parent=getSampleStyleSheet()["BodyText"],
        fontName="Helvetica-Bold" if header else "Helvetica",
        fontSize=8.5,
        leading=10.5,
        textColor=colors.white if header else colors.HexColor("#142B2E"),
    )


def _evidence_table(rows) -> LongTable:
    columns = [c for c in _COLUMNS if rows and c in rows[0]]
    header = [Paragraph(c, _cell_style(header=True)) for c in columns]
    body = [[Paragraph(str(row.get(c, "")), _cell_style()) for c in columns] for row in rows]
    table = LongTable([header] + body, colWidths=[_WIDTHS[c] for c in columns], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8F6")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


class PDFReportService:
    @staticmethod
    # Generates a styled multi-section clinical PDF; meta carries report context
    def create_clinical_pdf(dataframe, meta=None) -> bytes:
        meta = meta or {}
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=42,
            title="PharmaGen Precision Oncology Clinical Report",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0B4F4A"),
        )
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#0F766E"),
            spaceBefore=14,
        )
        muted_style = ParagraphStyle(
            "Muted", parent=styles["BodyText"], fontSize=8.5, textColor=colors.HexColor("#607779")
        )
        warning_style = ParagraphStyle(
            "Warn", parent=muted_style, textColor=colors.HexColor("#8A5A00"), spaceAfter=6
        )
        cell = _cell_style()

        story = [
            Paragraph("PharmaGen Precision Oncology Clinical Report", title_style),
            Paragraph(
                f"Source file: {meta.get('filename', 'unknown')} &nbsp;·&nbsp; "
                f"Generated: {meta.get('generated_at', 'n/a')}",
                muted_style,
            ),
            Spacer(1, 10),
        ]

        if meta.get("synthetic_data"):
            story.append(
                Paragraph(
                    "Synthetic demonstration dataset — genomic coordinates are simulated; "
                    "clinical relationships come from the local evidence base.",
                    warning_style,
                )
            )

        summary = meta.get("summary") or {}
        metric_rows = [
            ("Variants reviewed", summary.get("variants_count")),
            ("Exact matches", summary.get("exact_matches")),
            ("Contextual records", summary.get("contextual_matches")),
            ("Unmatched variants", summary.get("no_matches")),
        ]
        if meta.get("patients_observed"):
            metric_rows.append(("Patients observed", meta["patients_observed"]))
        metrics = Table(
            [
                [Paragraph(label, cell), Paragraph(str(value) if value is not None else "-", cell)]
                for label, value in metric_rows
            ],
            colWidths=[150, 90],
        )
        metrics.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF4F2")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story += [Paragraph("Analysis overview", section_style), metrics]

        validation = meta.get("validation") or {}
        if validation:
            story.append(
                Paragraph(
                    "Input quality: valid VCF headers {hdr} · parsed rows {parsed} · skipped {skip} · "
                    "duplicates {dup} · annotation coverage {cov}%".format(
                        hdr="yes" if validation.get("valid_vcf_headers") else "no",
                        parsed=validation.get("parsed_rows", 0),
                        skip=validation.get("skipped_rows", 0),
                        dup=validation.get("duplicate_rows", 0),
                        cov=validation.get("annotation_coverage_percent", 0),
                    ),
                    muted_style,
                )
            )

        records = dataframe.to_dict("records")
        if records and "Match Type" in dataframe.columns:
            exact_rows = [r for r in records if r.get("Match Type") == "exact"]
            contextual_rows = [r for r in records if r.get("Match Type") == "gene_context"]
        else:
            exact_rows, contextual_rows = records, []

        story.append(Paragraph("Exact clinical evidence", section_style))
        if exact_rows:
            story += [
                _evidence_table(exact_rows),
                Paragraph(f"{len(exact_rows)} exact record(s).", muted_style),
            ]
        else:
            story.append(
                Paragraph("No exact gene-plus-mutation evidence in this selection.", muted_style)
            )

        story.append(Paragraph("Contextual evidence only", section_style))
        if contextual_rows:
            story.append(
                Paragraph(
                    "These records match the gene but NOT the uploaded mutation. They provide "
                    "context only and must not be interpreted as treatment recommendations.",
                    warning_style,
                )
            )
            story += [
                _evidence_table(contextual_rows),
                Paragraph(f"{len(contextual_rows)} contextual record(s).", muted_style),
            ]
        else:
            story.append(Paragraph("No contextual-only records.", muted_style))

        story.append(Paragraph("Evidence level guide", section_style))
        for tier, description in TIER_GUIDE:
            story.append(Paragraph(f"<b>{tier}</b> — {description}", muted_style))

        story += [Spacer(1, 14), Paragraph(DISCLAIMER, muted_style)]

        def footer(canvas, _doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#607779"))
            canvas.drawString(30, 20, FOOTER_NOTE)
            canvas.drawRightString(letter[0] - 30, 20, f"Page {canvas.getPageNumber()}")
            canvas.restoreState()

        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        buffer.seek(0)
        return buffer.getvalue()
