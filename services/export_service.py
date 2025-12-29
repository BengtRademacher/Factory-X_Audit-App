import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import json
from typing import Dict, Any, List

class ExportService:
    """Service für den Export von Daten in verschiedene Formate."""
    
    @staticmethod
    def create_pdf_report(results: List[Dict[str, Any]], title: str = "Machine Efficiency Report") -> BytesIO:
        """Erstellt einen PDF-Bericht aus Analyse-Ergebnissen."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        
        # Custom Style für Pre-formatted Text (AI Assessment)
        ai_style = ParagraphStyle(
            'AIStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=12,
            spaceAfter=10
        )
        
        story = []
        story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
        story.append(Spacer(1, 12))
        
        for result in results:
            story.append(Paragraph(f"<b>File:</b> {result.get('filename', 'N/A')}", styles["Heading2"]))
            
            # Basisdaten
            data = [
                ["Machine Name", result.get("machine_name", "Unknown")],
                ["State", result.get("machine_state", "Unknown")],
                ["Total Energy (kWh)", f"{result.get('total_energy_combined', 0):.3f}"]
            ]
            
            t = Table(data, colWidths=[150, 300])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(t)
            story.append(Spacer(1, 12))
            
            # AI Assessment
            story.append(Paragraph("<b>AI Analysis:</b>", styles["Heading3"]))
            assessment = result.get("assessment", "No analysis available.")
            # Einfache Konvertierung von Newlines zu <br/> für ReportLab
            clean_assessment = assessment.replace("\n", "<br/>")
            story.append(Paragraph(clean_assessment, ai_style))
            story.append(Spacer(1, 20))
            
        doc.build(story)
        buffer.seek(0)
        return buffer

    @staticmethod
    def create_excel_export(data: Dict[str, Any]) -> BytesIO:
        """Exportiert JSON-Daten nach Excel."""
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Beispielhafte Flachklopf-Logik für Excel
            if "metadata" in data:
                pd.DataFrame([data["metadata"]]).to_excel(writer, sheet_name="Metadata")
            
            if "Elektrisch" in data and "Variables" in data["Elektrisch"]:
                pd.DataFrame(data["Elektrisch"]["Variables"]).T.to_excel(writer, sheet_name="Electrical_Details")
                
            if "Pneumatisch" in data and "Variables" in data["Pneumatisch"]:
                pd.DataFrame(data["Pneumatisch"]["Variables"]).T.to_excel(writer, sheet_name="Pneumatic_Details")
                
        buffer.seek(0)
        return buffer

