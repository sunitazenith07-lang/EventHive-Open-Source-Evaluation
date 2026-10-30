#!/usr/bin/env python3
"""Build a student-facing PDF from STUDENT_PROBLEM_STATEMENT.md.

The generated PDF stays aligned with the Markdown source of truth.
"""
from __future__ import annotations

import argparse
import os
import re
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "STUDENT_PROBLEM_STATEMENT.md"
OUTPUT = ROOT / "docs" / "Problem_Statement.pdf"


def inline_markup(value: str) -> str:
    value = escape(value)
    value = re.sub(r"`([^`]+)`", r'<font name="Courier" size="8">\1</font>', value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    value = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<link href="\2" color="#2459A9"><u>\1</u></link>',
        value,
    )
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository-url",
        default=f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}",
    )
    args = parser.parse_args()

    if not SOURCE.exists():
        raise SystemExit(f"Missing source statement: {SOURCE}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ZenithKicker", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, textColor=colors.HexColor("#4F46A5"),
        alignment=TA_CENTER, spaceAfter=5*mm,
    ))
    styles.add(ParagraphStyle(
        name="ProblemTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=20, leading=25, textColor=colors.HexColor("#171923"),
        alignment=TA_CENTER, spaceAfter=4*mm,
    ))
    styles.add(ParagraphStyle(
        name="H1Custom", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=15, leading=19, textColor=colors.HexColor("#27245E"),
        spaceBefore=7*mm, spaceAfter=2.5*mm, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="H2Custom", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11.5, leading=15, textColor=colors.HexColor("#3730A3"),
        spaceBefore=4*mm, spaceAfter=1.5*mm, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="BodyCustom", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9.2, leading=13, textColor=colors.HexColor("#22252B"),
        alignment=TA_LEFT, spaceAfter=2.2*mm, splitLongWords=True,
    ))
    styles.add(ParagraphStyle(
        name="BulletCustom", parent=styles["BodyCustom"], leftIndent=5*mm,
        firstLineIndent=-3*mm, spaceAfter=1.3*mm,
    ))
    styles.add(ParagraphStyle(
        name="RepoLink", parent=styles["BodyCustom"], alignment=TA_CENTER,
        fontSize=8.5, textColor=colors.HexColor("#2459A9"), spaceAfter=4*mm,
    ))
    styles.add(ParagraphStyle(
        name="CodeCustom", parent=styles["Code"], fontName="Courier",
        fontSize=8, leading=10, leftIndent=4*mm, rightIndent=4*mm,
        backColor=colors.HexColor("#F3F4F6"), borderPadding=3*mm,
        spaceBefore=1*mm, spaceAfter=2*mm,
    ))

    story = [
        Paragraph("ZENITH SCHOOL OF AI  •  OPEN-SOURCE EVALUATION", styles["ZenithKicker"]),
        HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#E5E7EB")),
        Spacer(1, 3*mm),
    ]

    raw = SOURCE.read_text(encoding="utf-8").splitlines()
    title_seen = False
    in_code = False
    code_lines: list[str] = []

    for line in raw:
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                code_lines = []
            else:
                text = "\n".join(escape(x) for x in code_lines)
                story.append(Paragraph(text.replace("\n", "<br/>"), styles["CodeCustom"]))
                in_code = False
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            story.append(Spacer(1, 1.1*mm))
            continue
        if stripped == "---":
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#E5E7EB")))
            story.append(Spacer(1, 2*mm))
            continue
        if stripped.startswith("# "):
            heading = stripped[2:].strip()
            story.append(Paragraph(inline_markup(heading), styles["ProblemTitle" if not title_seen else "H1Custom"]))
            title_seen = True
            continue
        if stripped.startswith("## "):
            story.append(Paragraph(inline_markup(stripped[3:].strip()), styles["H1Custom"]))
            continue
        if stripped.startswith("### "):
            story.append(Paragraph(inline_markup(stripped[4:].strip()), styles["H2Custom"]))
            continue
        if stripped.startswith("- "):
            story.append(Paragraph("•  " + inline_markup(stripped[2:].strip()), styles["BulletCustom"]))
            continue
        story.append(Paragraph(inline_markup(stripped), styles["BodyCustom"]))

    if in_code and code_lines:
        story.append(Paragraph("<br/>".join(escape(x) for x in code_lines), styles["CodeCustom"]))

    if args.repository_url:
        story.insert(3, Paragraph(
            f'Repository: <link href="{escape(args.repository_url, quote=True)}" color="#2459A9"><u>{escape(args.repository_url)}</u></link>',
            styles["RepoLink"],
        ))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
        canvas.line(18*mm, 14*mm, A4[0] - 18*mm, 14*mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(18*mm, 8.5*mm, "Zenith School of AI • Synthetic challenge data only")
        canvas.drawRightString(A4[0] - 18*mm, 8.5*mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
        topMargin=16*mm, bottomMargin=20*mm,
        title=raw[0].lstrip("# ").strip() if raw else "Problem Statement",
        author="Zenith School of AI",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Built {OUTPUT}")


if __name__ == "__main__":
    main()
