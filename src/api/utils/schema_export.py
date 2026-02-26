"""
Schema Export Utilities

Provides functions to export schema information in various formats:
- CSV: Tabular data exports
- PDF: Formatted documentation
- Markdown: Human-readable text format
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _numeric_sort_key(item: tuple[str, Any]) -> tuple[int, Any]:
    """
    Sort key function for sorting code lookups numerically.

    Codes that are numeric are sorted numerically.
    Non-numeric codes are sorted after numeric codes, alphabetically.

    Args:
        item: Tuple of (code, description)

    Returns:
        Tuple for sorting: (0, numeric_value) for numbers, (1, string) for non-numbers
    """
    code = item[0]
    try:
        return (0, int(code))
    except (ValueError, TypeError):
        return (1, str(code))


class SchemaExporter:
    """Handles schema exports to various formats."""

    @staticmethod
    def to_csv_buffer(data: dict[str, Any], export_type: str) -> io.StringIO:
        """
        Export schema data to CSV format.

        Args:
            data: Schema data dictionary
            export_type: Type of export (tables, code_lookups, etc.)

        Returns:
            StringIO buffer containing CSV data
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        if export_type == "tables":
            # Export table structures
            writer.writerow(["Table Name", "Column Name", "Type", "Description", "Nullable", "Range", "Example"])

            tables = data.get("tables", {})
            for table_name, table_info in tables.items():
                columns = table_info.get("columns", {})
                for col_name, col_info in columns.items():
                    writer.writerow(
                        [
                            table_name,
                            col_name,
                            col_info.get("type", ""),
                            col_info.get("description", ""),
                            col_info.get("nullable", ""),
                            col_info.get("range", ""),
                            col_info.get("example", ""),
                        ]
                    )

        elif export_type == "code_lookups":
            # Export code lookup tables
            writer.writerow(["Lookup Name", "Code", "Description"])

            code_lookups = data.get("code_lookups", {})
            for lookup_name, lookup_data in sorted(code_lookups.items()):
                # Filter out metadata fields and sort codes numerically
                code_items = [(k, v) for k, v in lookup_data.items() if k not in ["description", "source_field"]]
                for code, description in sorted(code_items, key=_numeric_sort_key):
                    writer.writerow([lookup_name, code, description])

        elif export_type == "relationships":
            # Export table relationships
            writer.writerow(["Relationship", "Type", "Description", "Join Condition"])

            relationships = data.get("relationships", {})
            for rel_name, rel_info in relationships.items():
                writer.writerow(
                    [rel_name, rel_info.get("type", ""), rel_info.get("description", ""), rel_info.get("join", "")]
                )

        buffer.seek(0)
        return buffer

    @staticmethod
    def to_markdown(data: dict[str, Any], export_type: str) -> str:
        """
        Export schema data to Markdown format.

        Args:
            data: Schema data dictionary
            export_type: Type of export

        Returns:
            Markdown formatted string
        """
        md_lines = []
        md_lines.append("# SnapAnalyst Schema Export")
        md_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        if export_type == "tables":
            md_lines.append("## Database Tables\n")

            tables = data.get("tables", {})
            for table_name, table_info in tables.items():
                md_lines.append(f"### {table_name}\n")
                md_lines.append(f"**Description:** {table_info.get('description', 'N/A')}\n")
                md_lines.append(f"**Row Count:** {table_info.get('row_count', 'N/A')}\n")
                md_lines.append(f"**Primary Key:** {table_info.get('primary_key', 'N/A')}\n")

                md_lines.append("\n#### Columns\n")
                md_lines.append("| Column | Type | Description | Range | Example |")
                md_lines.append("|--------|------|-------------|-------|---------|")

                columns = table_info.get("columns", {})
                for col_name, col_info in columns.items():
                    col_type = col_info.get("type", "")
                    col_desc = col_info.get("description", "").replace("|", "\\|")
                    col_range = str(col_info.get("range", "")).replace("|", "\\|")
                    col_example = str(col_info.get("example", "")).replace("|", "\\|")

                    md_lines.append(f"| {col_name} | {col_type} | {col_desc} | {col_range} | {col_example} |")

                md_lines.append("\n---\n")

        elif export_type == "code_lookups":
            md_lines.append("## Code Lookup Tables\n")

            code_lookups = data.get("code_lookups", {})
            for lookup_name, lookup_data in sorted(code_lookups.items()):
                md_lines.append(f"### {lookup_name}\n")
                md_lines.append(f"**Description:** {lookup_data.get('description', 'N/A')}\n")
                md_lines.append(f"**Source Field:** {lookup_data.get('source_field', 'N/A')}\n")

                md_lines.append("\n| Code | Description |")
                md_lines.append("|------|-------------|")

                # Filter out metadata fields and sort codes numerically
                code_items = [(k, v) for k, v in lookup_data.items() if k not in ["description", "source_field"]]
                for code, description in sorted(code_items, key=_numeric_sort_key):
                    desc_clean = str(description).replace("|", "\\|")
                    md_lines.append(f"| {code} | {desc_clean} |")

                md_lines.append("\n")

        return "\n".join(md_lines)

    @staticmethod
    def to_pdf_buffer(data: dict[str, Any], export_type: str) -> io.BytesIO:
        """
        Export schema data to PDF format.

        Args:
            data: Schema data dictionary
            export_type: Type of export

        Returns:
            BytesIO buffer containing PDF data
        """
        buffer = io.BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.5 * inch,
        )

        # Container for PDF elements
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1f77b4"),
            spaceAfter=30,
            alignment=TA_CENTER,
        )
        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=16,
            textColor=colors.HexColor("#2c3e50"),
            spaceAfter=12,
            spaceBefore=12,
        )
        subheading_style = ParagraphStyle(
            "CustomSubheading",
            parent=styles["Heading3"],
            fontSize=12,
            textColor=colors.HexColor("#34495e"),
            spaceAfter=6,
        )

        # Title
        elements.append(Paragraph("SnapAnalyst Schema Documentation", title_style))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
        elements.append(Spacer(1, 0.3 * inch))

        if export_type == "tables":
            tables = data.get("tables", {})

            for table_name, table_info in tables.items():
                # Table heading
                elements.append(Paragraph(f"Table: {table_name}", heading_style))

                # Table metadata
                elements.append(
                    Paragraph(f"<b>Description:</b> {table_info.get('description', 'N/A')}", styles["Normal"])
                )
                elements.append(Paragraph(f"<b>Row Count:</b> {table_info.get('row_count', 'N/A')}", styles["Normal"]))
                elements.append(Spacer(1, 0.15 * inch))

                # Columns table
                elements.append(Paragraph("Columns", subheading_style))

                columns = table_info.get("columns", {})
                if columns:
                    # Create table data
                    table_data = [["Column", "Type", "Description"]]

                    for col_name, col_info in list(columns.items())[:20]:  # Limit to first 20 columns
                        col_type = col_info.get("type", "")[:30]  # Truncate long types
                        col_desc = col_info.get("description", "")[:60]  # Truncate long descriptions
                        table_data.append([col_name, col_type, col_desc])

                    # Create table
                    col_table = Table(table_data, colWidths=[1.5 * inch, 1.5 * inch, 3.5 * inch])
                    col_table.setStyle(
                        TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, 0), 10),
                                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                                ("FONTSIZE", (0, 1), (-1, -1), 8),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ]
                        )
                    )

                    elements.append(col_table)

                    if len(columns) > 20:
                        elements.append(
                            Paragraph(f"<i>Note: Showing first 20 of {len(columns)} columns</i>", styles["Normal"])
                        )

                elements.append(PageBreak())

        elif export_type == "code_lookups":
            code_lookups = data.get("code_lookups", {})

            for lookup_name, lookup_data in sorted(code_lookups.items()):
                # Lookup heading
                elements.append(Paragraph(f"Code Lookup: {lookup_name}", heading_style))

                # Lookup metadata
                elements.append(
                    Paragraph(f"<b>Description:</b> {lookup_data.get('description', 'N/A')}", styles["Normal"])
                )
                elements.append(
                    Paragraph(f"<b>Source Field:</b> {lookup_data.get('source_field', 'N/A')}", styles["Normal"])
                )
                elements.append(Spacer(1, 0.15 * inch))

                # Codes table
                table_data = [["Code", "Description"]]

                # Filter out metadata fields and sort codes numerically
                code_items = [(k, v) for k, v in lookup_data.items() if k not in ["description", "source_field"]]
                for code, description in sorted(code_items, key=_numeric_sort_key):
                    desc_str = str(description)[:80]  # Truncate long descriptions
                    table_data.append([str(code), desc_str])

                if len(table_data) > 1:
                    lookup_table = Table(table_data, colWidths=[1 * inch, 5.5 * inch])
                    lookup_table.setStyle(
                        TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2ecc71")),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, 0), 10),
                                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                                ("BACKGROUND", (0, 1), (-1, -1), colors.lightgrey),
                                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                                ("FONTSIZE", (0, 1), (-1, -1), 8),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ]
                        )
                    )

                    elements.append(lookup_table)
                    elements.append(Spacer(1, 0.2 * inch))

        elif export_type == "database_info":
            db_info = data.get("database", {})

            elements.append(Paragraph("Database Information", heading_style))

            info_items = [
                ("Name", db_info.get("name", "N/A")),
                ("Version", db_info.get("version", "N/A")),
                ("Description", db_info.get("description", "N/A")),
                ("Purpose", db_info.get("purpose", "N/A")),
                ("Data Source", db_info.get("data_source", "N/A")),
                ("Total Households", db_info.get("total_households", "N/A")),
                ("Fiscal Years", ", ".join(map(str, db_info.get("fiscal_years_available", [])))),
            ]

            for label, value in info_items:
                elements.append(Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]))
                elements.append(Spacer(1, 0.1 * inch))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        return buffer
