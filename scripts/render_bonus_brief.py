"""Render the submission architecture brief as six reviewable A4 pages.

Uses reportlab (the bundled Codex document runtime supplies it).
Source of truth: submission/bonus/ARCHITECTURE.md.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Preformatted, Table, TableStyle,
    PageBreak, Spacer,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "submission/bonus/ARCHITECTURE.md"
OUTPUT = ROOT / "submission/bonus/ARCHITECTURE.pdf"
pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("ArialBold", "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="ArialBold")
NAVY, TEAL = colors.HexColor("#142d4e"), colors.HexColor("#007f82")
BODY = ParagraphStyle("body", fontName="Arial", fontSize=9.6, leading=13.0,
                      spaceAfter=7, textColor=NAVY, alignment=TA_LEFT)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.3, leading=11.0, spaceAfter=0)
TITLE = ParagraphStyle("title", parent=BODY, fontName="ArialBold", fontSize=17,
                       leading=21, spaceAfter=12)
HEADING = ParagraphStyle("heading", parent=BODY, fontName="ArialBold", fontSize=13,
                         leading=17, spaceBefore=8, spaceAfter=9, textColor=TEAL)
CODE = ParagraphStyle("code", fontName="Courier", fontSize=8, leading=10,
                      textColor=NAVY, spaceAfter=8)


def markup(text: str) -> str:
    text = html.escape(text.replace("—", "-").replace("–", "-"))
    text = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r'<link href="\2" color="#007f82">\1</link>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)


def blocks(text: str):
    lines = text.strip().splitlines()
    result, i = [], 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            result.append(Preformatted("\n".join(code), CODE))
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [s.strip() for s in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[: -]+", s) for s in row):
                    rows.append([Paragraph(markup(s), CELL) for s in row])
                i += 1
            cols = len(rows[0])
            widths = {4: [82, 160, 132, 133], 3: [133, 304, 70]}[cols]
            if cols == 3 and "Failure" in line:
                widths = [95, 140, 272]
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcecef")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, TEAL),
            ]))
            result.extend([table, Spacer(1, 9)])
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            result.append(Paragraph(markup(line.lstrip("# ")), TITLE if level == 1 else HEADING))
            i += 1
        elif line.startswith("- "):
            result.append(Paragraph(markup(line[2:]), BODY, bulletText="-"))
            i += 1
        else:
            paragraph = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "- ", "```")):
                paragraph.append(lines[i].strip())
                i += 1
            result.append(Paragraph(markup(" ".join(paragraph)), BODY))
    return result


def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor("#c9d7e5"))
    canvas.line(44, 39, 551, 39)
    canvas.setFont("Arial", 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(44, 26, "K4-Track02-Day18 | Nguyen Ngoc Bao | 2A202602951")
    canvas.drawRightString(551, 26, f"{doc.page} / 6")


def main():
    source = SOURCE.read_text(encoding="utf-8-sig")
    intro, rest = source.split("## 3.", 1)
    decisions, rest = ("## 3." + rest).split("**Detailed retention:**", 1)
    retention, rest = ("**Detailed retention:**" + rest).split("## 5.", 1)
    storage, rest = ("## 5." + rest).split("| Compute and operations", 1)
    compute, rest = ("| Compute and operations" + rest).split("## 6.", 1)
    mvp, rest = ("## 6." + rest).split("**Local PoC actually run:**", 1)
    poc, sources = ("**Local PoC actually run:**" + rest).split("## Sources", 1)
    pages = [intro, decisions, "## Retention and failure handling\n\n" + retention,
             storage, "## Compute sizing and local evidence\n\n" + compute + poc,
             mvp + "## Sources" + sources]
    story = []
    for number, page in enumerate(pages):
        if number:
            story.append(PageBreak())
        story.extend(blocks(page))
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=44, rightMargin=44,
                            topMargin=36, bottomMargin=52,
                            title="LLM Observability Lakehouse - Architecture Brief",
                            author="Nguyen Ngoc Bao")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
