from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

class PDFReportService:
    @staticmethod
    # Generates a styled clinical PDF report from the variant evidence dataframe
    def create_clinical_pdf(dataframe) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#1E293B'))
        story.append(Paragraph("PharmaGen Precision Oncology Clinical Report", title_style))
        story.append(Spacer(1, 12))

        table_data = [["Gene", "Mutation", "Disease", "Targeted Therapy", "Evidence"]]
        for _, row in dataframe.head(15).iterrows():
            table_data.append([
                str(row["Gene"]),
                str(row["Mutation"]),
                str(row["Disease"])[:25],
                str(row["Targeted Drug"])[:30],
                str(row["Evidence Level"])
            ])

        t = Table(table_data, colWidths=[60, 70, 150, 180, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        story.append(t)
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()