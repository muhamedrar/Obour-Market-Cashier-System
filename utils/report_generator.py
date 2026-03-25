from __future__ import annotations

from io import BytesIO
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def register_font() -> str:
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    if "CashierFont" in pdfmetrics.getRegisteredFontNames():
        return "CashierFont"
    for candidate in candidates:
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont("CashierFont", candidate))
            return "CashierFont"
    return "Helvetica"


def paragraph_style():
    font_name = register_font()
    styles = getSampleStyleSheet()
    return ParagraphStyle(
        "CashierBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#10222b"),
    )


def shape_text(value) -> str:
    text = str(value or "")
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


def title_style():
    base = paragraph_style()
    return ParagraphStyle(
        "CashierTitle",
        parent=base,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0c5b69"),
        spaceAfter=12,
    )


def build_pdf(
    title: str,
    metadata_lines: list[str],
    table_headers: list[str],
    rows: list[list[str]],
    paper: str = "a4",
):
    buffer = BytesIO()
    if paper == "thermal":
        page_size = (80 * mm, 240 * mm)
        side_margin = 0.5 * cm
        font_size = 8
    else:
        page_size = A4
        side_margin = 1.5 * cm
        font_size = 10

    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=side_margin,
        leftMargin=side_margin,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    body = paragraph_style()
    title_paragraph = title_style()
    body.fontSize = font_size
    body.leading = font_size + 4
    title_paragraph.fontSize = font_size + 4
    title_paragraph.leading = font_size + 8

    elements = [Paragraph(shape_text(title), title_paragraph)]
    for line in metadata_lines:
        elements.append(Paragraph(shape_text(line), body))
    elements.append(Spacer(1, 0.5 * cm))

    table_data = [[shape_text(item) for item in table_headers]]
    table_data.extend([[shape_text(cell) for cell in row] for row in rows])
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), body.fontName),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d5ede8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0d3f47")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdd6d1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6fbf9")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
