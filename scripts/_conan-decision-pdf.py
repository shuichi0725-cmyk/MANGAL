"""[成果物] コナン劇場版関連 最終仕分けPDF。KEEP(コミカライズ→種4) と DROP(理由付き) の両表。
 端末非依存(メイリオ埋込)。本番未適用。出典=楽天題/レーベル + wiki逐語 + ユーザ裁定。"""
import json, io, sys, re, os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

pdfmetrics.registerFont(TTFont("Meiryo", r"C:\Windows\Fonts\meiryo.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("MeiryoB", r"C:\Windows\Fonts\meiryob.ttc", subfontIndex=0))
ss = getSampleStyleSheet()
H = ParagraphStyle("H", parent=ss["Title"], fontName="MeiryoB", fontSize=15, leading=19)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="MeiryoB", fontSize=11, leading=15, spaceBefore=8)
P = ParagraphStyle("P", parent=ss["Normal"], fontName="Meiryo", fontSize=8.5, leading=12)
PS = ParagraphStyle("PS", parent=ss["Normal"], fontName="Meiryo", fontSize=7.5, leading=10)

# 楽天キャッシュで綺麗な題を引く
rk = {}
if os.path.exists(".cache/rakuten-isbn.jsonl"):
    for line in open(".cache/rakuten-isbn.jsonl", encoding="utf-8"):
        if '"isbn"' not in line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        i = str(r.get("isbn") or "")
        it = r.get("item") or {}
        if i and it and i not in rk:
            rk[i] = (it.get("title", ""), it.get("seriesName", ""), it.get("salesDate", ""))

dec = {}
for ln in open(".cache/conan-final-decision.tsv", encoding="utf-8").readlines()[1:]:
    isbn, d, why, title = (ln.rstrip("\n").split("\t") + [""] * 4)[:4]
    ct, sn, sd = rk.get(isbn, (title, "", ""))
    ct = re.sub(r"(原案／青山剛昌\s*作画／阿部ゆたか、丸伝次郎|青山剛昌（案）、阿部ゆたか、丸伝次郎（画）|『|』)", "", ct).strip()
    dec.setdefault(d, []).append((isbn, why, ct[:38], sn[:18], sd))

story = []
story.append(Paragraph("名探偵コナン 劇場版関連 — 最終仕分け表(KEEP / DROP 理由付き)", H))
story.append(Paragraph("出典: 楽天の題・レーベル名 + wiki逐語 + ユーザ裁定。"
                       "判定軸=レーベル「少年サンデーコミックス(素)＋阿部ゆたか・丸伝次郎」＝コミカライズKEEP / "
                       "「〔ビジュアル〕/スペシャル」＝フィルムコミックDROP。 <b>本番未適用</b>。 2026-06-16", PS))


def tbl(rows, head, colw, hexc):
    data = [head]
    for r in rows:
        data.append([Paragraph(str(c), PS) for c in r])
    t = Table(data, colWidths=colw, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "MeiryoB"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(hexc)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f3f3")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t

# ===== KEEP =====
story.append(Paragraph(f"■ KEEP = コミカライズ(掲載) … {len(dec.get('KEEP', []))}件 / 5作", H2))
story.append(Paragraph("DB未収録の5件(時計じかけ1・天国2・迷宮2)は<b>種4に登録して掲載</b>。"
                       "世紀末3巻・漆黒3巻は収録済(漆黒は3sid分裂→1ページに統合)。", PS))
khead = [Paragraph(h, PS) for h in ["ISBN", "書名", "レーベル", "発売", "扱い"]]
krows = []
for isbn, why, t, sn, sd in dec.get("KEEP", []):
    handle = "種4登録" if ("時計じかけ" in t or "天国" in t or "迷宮" in t) else "収録済"
    if "漆黒" in t:
        handle = "収録済(統合要)"
    krows.append([isbn, t, sn, sd, handle])
story.append(tbl(krows, khead, [25 * mm, 62 * mm, 30 * mm, 24 * mm, 22 * mm], "#2a9d8f"))

# ===== KEEP_SEP =====
story.append(Paragraph(f"■ KEEP_SEP = 別シリーズ(切り離し) … {len(dec.get('KEEP_SEP', []))}件", H2))
story.append(Paragraph("「名探偵コナン特別編」(太田勝・窪田一裕／てんとう虫コミックス)は映画クラスタに誤混入。独立連載漫画なので別ページでKEEP。", PS))
srows = [[isbn, t, sn, sd, "別ページ化"] for isbn, why, t, sn, sd in dec.get("KEEP_SEP", [])]
story.append(tbl(srows, khead, [25 * mm, 62 * mm, 30 * mm, 24 * mm, 22 * mm], "#457b9d"))

# ===== DROP(理由別) =====
story.append(Paragraph(f"■ DROP = 非掲載 … {len(dec.get('DROP', []))}件 (種4には入れない)", H2))
# 理由でグルーピング
order = ["フィルムコミック", "総集編", "コンビニ廉価", "TVアニメ"]


def reason_group(why):
    if "フィルムコミック" in why:
        return "フィルムコミック(映画の画面流用本=漫画でない)"
    if "総集編" in why or "企画本" in why:
        return "総集編/セレクション/企画本(既刊の寄せ集め)"
    if "廉価" in why or "My First" in why:
        return "コンビニ廉価再録(My First BIG)"
    if "TVアニメ" in why:
        return "TVアニメのフィルムコミック(ユーザ裁定)"
    return why


grp = {}
for isbn, why, t, sn, sd in dec.get("DROP", []):
    grp.setdefault(reason_group(why), []).append((isbn, t, sn, sd))
for g in sorted(grp, key=lambda x: -len(grp[x])):
    story.append(Paragraph(f"● {g} … {len(grp[g])}件", P))
    dh = [Paragraph(h, PS) for h in ["ISBN", "書名", "レーベル", "発売"]]
    drows = [[isbn, t, sn, sd] for isbn, t, sn, sd in grp[g]]
    story.append(tbl(drows, dh, [25 * mm, 70 * mm, 44 * mm, 24 * mm], "#9b2226"))
    story.append(Spacer(1, 3))

story.append(Spacer(1, 4))
story.append(Paragraph("※ DROPは「漫画でない/本編でない」ため非掲載。種4=取りこぼし巻の<b>掲載補完</b>用なのでDROPは入れない。"
                       "DROPは drop list(非掲載台帳)で管理し、誤判定時に復活可能。", PS))

SimpleDocTemplate("docs/conan-decision-keep-drop.pdf", pagesize=A4,
                  topMargin=13 * mm, bottomMargin=13 * mm, leftMargin=11 * mm, rightMargin=11 * mm).build(story)
print("--> docs/conan-decision-keep-drop.pdf", file=sys.stderr)
