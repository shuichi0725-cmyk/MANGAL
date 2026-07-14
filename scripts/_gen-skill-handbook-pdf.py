#!/usr/bin/env python3
"""skillハンドブック PDF を生成 (= .claude/skills/*/SKILL.md 全25本の携帯用リファレンス)。

出力: docs/mangal-skill-handbook.pdf
構成: 表紙 → トリガー早見表(docs/skill-triggers.md があれば要約) → 各skill全文(50音でなくフォルダ名順)。
再生成: skill追加/改訂のたびに `python scripts/_gen-skill-handbook-pdf.py`。
"""
import datetime
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
OUT = ROOT / "docs" / "mangal-skill-handbook.pdf"

pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
FONT = "HeiseiKakuGo-W5"

TITLE = ParagraphStyle("TITLE", fontName=FONT, fontSize=22, leading=28, spaceAfter=8)
H1 = ParagraphStyle("H1", fontName=FONT, fontSize=15, leading=19, spaceBefore=4, spaceAfter=6,
                    textColor=colors.HexColor("#0b5a3c"))
H2 = ParagraphStyle("H2", fontName=FONT, fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=3,
                    textColor=colors.HexColor("#1a1a1a"))
BODY = ParagraphStyle("BODY", fontName=FONT, fontSize=8.6, leading=12)
BULLET = ParagraphStyle("BULLET", fontName=FONT, fontSize=8.6, leading=12, leftIndent=8)
CODE = ParagraphStyle("CODE", fontName=FONT, fontSize=7.8, leading=10.5,
                      textColor=colors.HexColor("#0b3a5a"), leftIndent=6,
                      backColor=colors.HexColor("#f2f5f4"))
CELL = ParagraphStyle("CELL", fontName=FONT, fontSize=7.6, leading=9.8)
CELLB = ParagraphStyle("CELLB", fontName=FONT, fontSize=7.6, leading=9.8,
                       textColor=colors.HexColor("#0b5a3c"))
SMALL = ParagraphStyle("SMALL", fontName=FONT, fontSize=7.6, leading=10,
                       textColor=colors.HexColor("#666666"))


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def P(t, s=BODY):
    return Paragraph(esc(t), s)


def first_line_summary(md: str) -> str:
    """SKILL.md の見出し行(# ...)を要約として返す。"""
    for ln in md.splitlines():
        if ln.startswith("# "):
            return ln[2:].strip()
    return ""


def md_flow(md: str, story: list) -> None:
    """SKILL.md の簡易レンダ: 見出し/箇条書き/コードfence/表行をそれらしく流し込む。"""
    in_code = False
    for raw in md.splitlines():
        ln = raw.rstrip()
        if ln.strip().startswith("```"):
            in_code = not in_code
            continue
        if not ln.strip():
            story.append(Spacer(1, 2.5 * mm))
            continue
        if in_code:
            story.append(P(ln, CODE))
            continue
        if ln.startswith("# "):
            continue  # 章題はセクション見出しで出力済み
        if ln.startswith("## "):
            story.append(P(ln[3:], H2))
            continue
        if ln.startswith("### "):
            story.append(P("◆ " + ln[4:], H2))
            continue
        if re.match(r"^\s*[-*] ", ln):
            story.append(P("・" + re.sub(r"^\s*[-*] ", "", ln), BULLET))
            continue
        if ln.startswith("|"):
            story.append(P(ln, CODE))  # 表はモノ調で崩さず表示
            continue
        story.append(P(ln, BODY))


def main() -> None:
    dirs = sorted(d for d in SKILLS.iterdir() if (d / "SKILL.md").exists())
    doc = SimpleDocTemplate(str(OUT), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title="MANGAL skillハンドブック")
    story = []
    today = datetime.date.today().isoformat()
    story.append(Paragraph("MANGAL skillハンドブック", TITLE))
    story.append(P(f"生成: {today} / 収録 {len(dirs)} skill (.claude/skills/*/SKILL.md 全文)", SMALL))
    story.append(P("再生成: python scripts/_gen-skill-handbook-pdf.py", SMALL))
    story.append(Spacer(1, 6 * mm))

    # 早見表(skill名 + 冒頭見出し)
    rows = [[P("skill", CELLB), P("概要(SKILL.md冒頭見出し)", CELLB)]]
    summaries = {}
    for d in dirs:
        md = (d / "SKILL.md").read_text(encoding="utf-8")
        summaries[d.name] = md
        rows.append([P(d.name, CELL), P(first_line_summary(md), CELL)])
    tbl = Table(rows, colWidths=[42 * mm, 136 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f2ec")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8f7")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d4ce")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(tbl)

    for d in dirs:
        story.append(PageBreak())
        story.append(Paragraph(esc(d.name), H1))
        head = first_line_summary(summaries[d.name])
        if head:
            story.append(P(head, SMALL))
            story.append(Spacer(1, 2 * mm))
        md_flow(summaries[d.name], story)

    doc.build(story)
    print(f"→ {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024}KB / {len(dirs)} skill)")


if __name__ == "__main__":
    main()
