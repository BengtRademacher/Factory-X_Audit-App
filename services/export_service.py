import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
import json
from html import escape
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
                ["State", result.get("operating_state") or result.get("machine_state", "Unknown")],
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
    def create_management_audit_report(
        audit_results: Dict[str, Any],
        audit_draft: Dict[str, Any],
        title: str = "Machine Energy Audit Report",
    ) -> BytesIO:
        """Creates a management-oriented PDF audit report."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=66, bottomMargin=54)
        styles = getSampleStyleSheet()
        body = styles["BodyText"]
        heading = styles["Heading2"]
        small = ParagraphStyle("Small", parent=body, fontSize=8, leading=10)
        audit_name = audit_results.get("metadata", {}).get("machine_name", "Machine Energy Audit")

        story = ExportService._cover_page(audit_results, title, styles) + [
            PageBreak(),
            Paragraph(escape(audit_draft.get("executive_summary", "")), body),
            Spacer(1, 16),
            ExportService._traffic_light_table(audit_draft.get("traffic_lights", {})),
            Spacer(1, 18),
            Paragraph("<b>Datenbasis und Mapping-Qualitaet</b>", heading),
            ExportService._dict_table(audit_draft.get("data_basis", {})),
            Spacer(1, 14),
            Paragraph("<b>Zeitspalten- und Sampling-Analyse</b>", heading),
            ExportService._time_sampling_table(audit_results.get("mapping", {})),
            Spacer(1, 14),
            Paragraph("<b>Bilanzierte Energie und Leistung</b>", heading),
            ExportService._key_metrics_table(audit_draft.get("key_metrics", {})),
            Spacer(1, 12),
            ExportService._balance_table(audit_results.get("balance", {})),
            PageBreak(),
            Paragraph("<b>Elektrische Hauptversorgung und Unterverbraucher</b>", heading),
            ExportService._supply_table(audit_results, "Elektrisch", small),
            Spacer(1, 14),
            Paragraph("<b>Druckluft-Hauptversorgung und Unterverbraucher</b>", heading),
            ExportService._supply_table(audit_results, "Pneumatisch", small),
            Spacer(1, 14),
            Paragraph("<b>Top-Verbraucher und Lastspitzen</b>", heading),
            ExportService._top_consumers_chart(audit_draft.get("top_consumers", {})),
            Spacer(1, 16),
            ExportService._energy_group_pie(audit_results),
            PageBreak(),
            Paragraph("<b>Empfehlungen: Retrofit-Potenzial</b>", heading),
            ExportService._measures_table(audit_draft.get("recommended_measures", []), "Retrofit-Potenzial"),
            Spacer(1, 16),
            Paragraph("<b>Empfehlungen: Betriebspotenzial</b>", heading),
            ExportService._measures_table(audit_draft.get("recommended_measures", []), "Betriebspotenzial"),
            PageBreak(),
            Paragraph("<b>Literature Evidence</b>", heading),
            ExportService._evidence_table(audit_draft.get("evidence_cards", []), small),
            PageBreak(),
            Paragraph("<b>Manual Notes and Assumptions</b>", heading),
            Paragraph(escape(audit_draft.get("manual_notes", "") or "No manual notes provided."), body),
            Spacer(1, 16),
            Paragraph("<b>Mapping Summary</b>", heading),
            ExportService._mapping_table(audit_results.get("mapping", {}), small),
        ]

        def first_page(canvas, document):
            return None

        def later_pages(canvas, document):
            ExportService._draw_audit_header_footer(canvas, document, audit_name)

        doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
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

    @staticmethod
    def _traffic_light_table(traffic_lights: Dict[str, str]) -> Table:
        data = [["Area", "Rating"]] + [[area, rating] for area, rating in traffic_lights.items()]
        table = Table(data, colWidths=[250, 160])
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        color_map = {"Green": HexColor("#01A579"), "Yellow": HexColor("#F9B31A"), "Red": HexColor("#E50037")}
        for row_idx, row in enumerate(data[1:], start=1):
            style.append(('TEXTCOLOR', (1, row_idx), (1, row_idx), colors.white))
            style.append(('BACKGROUND', (1, row_idx), (1, row_idx), color_map.get(row[1], colors.grey)))
        table.setStyle(TableStyle(style))
        return table

    @staticmethod
    def _cover_page(audit_results: Dict[str, Any], title: str, styles) -> List[Any]:
        metadata = audit_results.get("metadata", {})
        summary = audit_results.get("Overall Summary", {})
        cover_title = Paragraph(f"<b>{escape(title)}</b>", styles["Title"])
        subtitle = Paragraph(
            escape(f"Audit: {metadata.get('machine_name', 'not specified')}"),
            styles["Heading2"],
        )
        details = [
            ["Machine", metadata.get("machine_name", "not specified")],
            ["Material", metadata.get("material", "not specified")],
            ["Operating state", metadata.get("operating_state", "not specified")],
            ["Audit state", metadata.get("machine_state", "not specified")],
            ["Operator", metadata.get("operator", "not specified")],
            ["Audit duration (s)", metadata.get("duration_seconds", 0)],
            ["Total energy (kWh)", summary.get("Total Energy (kWh)", 0)],
            ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ]
        table = Table([["Audit field", "Value"]] + [[a, str(b)] for a, b in details], colWidths=[180, 280])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        return [
            Spacer(1, 120),
            cover_title,
            Spacer(1, 24),
            subtitle,
            Spacer(1, 36),
            table,
            Spacer(1, 60),
            Paragraph("Factory-X Machine Energy Audit", styles["Heading3"]),
        ]

    @staticmethod
    def _draw_audit_header_footer(canvas, document, audit_name: str):
        width, height = A4
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(document.leftMargin, height - 34, "Factory-X Machine Energy Audit")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - document.rightMargin, height - 34, str(audit_name))
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(document.leftMargin, height - 42, width - document.rightMargin, height - 42)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - document.rightMargin, 28, f"Seite {document.page}")
        canvas.restoreState()

    @staticmethod
    def _key_metrics_table(metrics: Dict[str, Any]) -> Table:
        data = [["Metric", "Value"]] + [[key, str(value)] for key, value in metrics.items()]
        table = Table(data, colWidths=[250, 160])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return table

    @staticmethod
    def _dict_table(values: Dict[str, Any]) -> Table:
        data = [["Item", "Value"]] + [[key, str(value)] for key, value in values.items()]
        if len(data) == 1:
            data.append(["No data", ""])
        table = Table(data, colWidths=[210, 250])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return table

    @staticmethod
    def _time_sampling_table(mapping: Dict[str, Any]) -> Table:
        data = [
            ["Time column", str(mapping.get("time_column", "not specified"))],
            ["Sampling rate (Hz)", str(mapping.get("sampling_rate_hz", "not specified"))],
            ["Mapping notes", str(mapping.get("notes", ""))],
        ]
        table = Table([["Item", "Value"]] + data, colWidths=[160, 310])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return table

    @staticmethod
    def _balance_table(balance: Dict[str, Any]) -> Table:
        rows = [
            ["Electric source", balance.get("electric_source") or "component sum"],
            ["Pneumatic source", balance.get("pneumatic_source") or "component sum"],
            ["Electric total (kWh)", balance.get("electric_total_kWh", 0)],
            ["Pneumatic total (kWh)", balance.get("pneumatic_total_kWh", 0)],
            ["Total energy (kWh)", balance.get("total_energy_kWh", 0)],
            ["Mean power (W)", balance.get("mean_power_W", 0)],
        ]
        table = Table([["Balance item", "Value"]] + [[a, str(b)] for a, b in rows], colWidths=[210, 250])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return table

    @staticmethod
    def _top_consumers_chart(top_consumers: Dict[str, Any]) -> Drawing:
        drawing = Drawing(460, 220)
        chart = VerticalBarChart()
        chart.x = 40
        chart.y = 40
        chart.height = 150
        chart.width = 360
        names = list(top_consumers.keys())[:5] or ["No data"]
        values = [float(top_consumers.get(name, 0) or 0) for name in names]
        chart.data = [values or [0]]
        chart.categoryAxis.categoryNames = [name[:18] for name in names]
        chart.valueAxis.valueMin = 0
        chart.bars[0].fillColor = HexColor("#007CC5")
        drawing.add(chart)
        return drawing

    @staticmethod
    def _energy_group_pie(audit_results: Dict[str, Any]) -> Drawing:
        balance = audit_results.get("balance", {})
        electric = balance.get("electric_total_kWh", audit_results.get("Elektrisch", {}).get("Total Elektrisch", {}).get("total_energy_kWh", 0))
        pneumatic = balance.get("pneumatic_total_kWh", audit_results.get("Pneumatisch", {}).get("Total Pneumatisch", {}).get("total_energy_kWh", 0))
        drawing = Drawing(460, 220)
        pie = Pie()
        pie.x = 150
        pie.y = 30
        pie.width = 170
        pie.height = 170
        values = [float(electric or 0), float(pneumatic or 0)]
        pie.data = values if any(values) else [1]
        pie.labels = ["Electric", "Pneumatic"] if any(values) else ["No energy"]
        pie.slices[0].fillColor = HexColor("#007CC5")
        if any(values):
            pie.slices[1].fillColor = HexColor("#B1CB21")
        drawing.add(pie)
        return drawing

    @staticmethod
    def _measures_table(measures: List[Dict[str, str]], category: str | None = None) -> Table:
        data = [["Priority", "Area", "Measure", "Expected effect", "Confidence"]]
        selected = [measure for measure in measures if category is None or measure.get("category") == category]
        for measure in selected:
            data.append([
                measure.get("priority", ""),
                Paragraph(escape(str(measure.get("area", ""))), getSampleStyleSheet()["BodyText"]),
                Paragraph(escape(str(measure.get("measure", ""))), getSampleStyleSheet()["BodyText"]),
                Paragraph(escape(str(measure.get("expected_effect", ""))), getSampleStyleSheet()["BodyText"]),
                measure.get("confidence", ""),
            ])
        if len(data) == 1:
            data.append(["-", "No recommendations", "", "", ""])
        table = Table(data, colWidths=[50, 85, 175, 115, 60])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        return table

    @staticmethod
    def _supply_table(audit_results: Dict[str, Any], group_key: str, style: ParagraphStyle) -> Table:
        variables = audit_results.get(group_key, {}).get("Variables", {})
        data = [["Component", "Role", "Energy kWh", "Mean W", "Peak W", "Parent supply"]]
        for name, metrics in variables.items():
            data.append([
                Paragraph(escape(str(name)[:70]), style),
                metrics.get("supply_role", ""),
                metrics.get("total_energy_kWh", 0),
                metrics.get("mean", 0),
                metrics.get("max", 0),
                Paragraph(escape(str(metrics.get("parent_supply") or "")), style),
            ])
        if len(data) == 1:
            data.append(["No data", "", "", "", "", ""])
        table = Table(data, colWidths=[115, 75, 70, 70, 70, 110])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        return table

    @staticmethod
    def _evidence_table(cards: List[Dict[str, Any]], style: ParagraphStyle) -> Table:
        data = [["Source", "Claim", "Value"]]
        for card in cards[:10]:
            data.append([
                Paragraph(escape(str(card.get("source_title", ""))[:90]), style),
                Paragraph(escape(str(card.get("claim_key", ""))), style),
                Paragraph(escape(str(card.get("value", ""))[:180]), style),
            ])
        table = Table(data, colWidths=[180, 120, 190])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return table

    @staticmethod
    def _mapping_table(mapping: Dict[str, Any], style: ParagraphStyle) -> Table:
        data = [["Source", "Canonical", "Medium", "Role", "Unit", "Conf."]]
        for channel in mapping.get("channels", [])[:20]:
            data.append([
                Paragraph(escape(str(channel.get("source_column", ""))), style),
                Paragraph(escape(str(channel.get("canonical_name", ""))), style),
                channel.get("medium", ""),
                channel.get("supply_role", ""),
                channel.get("unit", ""),
                f"{float(channel.get('confidence', 0) or 0):.2f}",
            ])
        table = Table(data, colWidths=[110, 130, 70, 80, 45, 45])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        return table

