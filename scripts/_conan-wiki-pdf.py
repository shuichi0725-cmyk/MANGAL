"""[調査成果物] コナン劇場版 漫画版/フィルムコミック 確定表をPDF化(端末非依存・メイリオ埋込)。
 wiki逐語(8作=確定) + DBクラスタ52件のパターン照合(暫定)。本番未変更・適用なし。"""
import json, io, sys, re
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
H = ParagraphStyle("H", parent=ss["Title"], fontName="MeiryoB", fontSize=15, leading=20)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="MeiryoB", fontSize=11, leading=15, spaceBefore=8)
P = ParagraphStyle("P", parent=ss["Normal"], fontName="Meiryo", fontSize=8.5, leading=12)
PS = ParagraphStyle("PS", parent=ss["Normal"], fontName="Meiryo", fontSize=7.5, leading=10)

story = []
story.append(Paragraph("名探偵コナン 劇場版 — 漫画版/フィルムコミック 仕分け調査", H))
story.append(Paragraph("出典: ja.wikipedia 各作品記事の書籍欄を逐語抽出(action=raw)。"
                       "<b>調査のみ・本番未適用</b>。 2026-06-16", P))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "■ 結論: コミカライズ(=漫画版, 阿部ゆたか・丸伝次郎ら作画)は <b>第1・3・5・7作のみ</b>に存在。"
    "他作は「フィルムコミック(上巻/下巻/完全版)」だけ。"
    "フィルムコミック=映画の画面を流用した本=<b>漫画ではない→DROP</b>。"
    "漫画版=描き起こしコミカライズ=<b>KEEP</b>。", P))
story.append(Spacer(1, 6))

# ---- 表1: wiki確定(8作) ----
story.append(Paragraph("表1. wikiが書籍欄に明記した8作 (確定度=高)", H2))
data = [["作", "区分", "ISBN", "DB", "書名/発売"]]
for ln in open(".cache/conan-wiki-keepdrop.tsv", encoding="utf-8").readlines()[1:]:
    movie, dec, cat, isbn, indb, title = (ln.rstrip("\n").split("\t") + [""] * 6)[:6]
    mv = re.sub(r"^#\d+\s+\d{4}\s+名探偵コナン\s*", "", movie)
    kd = "KEEP漫画" if dec == "KEEP" else "DROP film"
    db = "◎" if indb == "1" else "＋種4" if dec == "KEEP" else "－"
    t = re.sub(r"(原案／青山剛昌\s*作画／|阿部ゆたか、丸伝次郎|青山剛昌（案）、|『|』|ISBN.*$)", "", title).strip()
    data.append([Paragraph(mv, PS), Paragraph(kd, PS), Paragraph(isbn, PS),
                 Paragraph(db, PS), Paragraph(t[:34], PS)])
t1 = Table(data, colWidths=[26 * mm, 20 * mm, 26 * mm, 12 * mm, 78 * mm], repeatRows=1)
t1.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, 0), "MeiryoB"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#264653")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
story.append(t1)
story.append(Paragraph("◎=DB収録済 / ＋種4=DB未収録の漫画版(種4で要追加) / －=DB外", PS))

# ---- 表2: DBにあるがwiki未掲載の52件 = パターン照合(暫定) ----
story.append(Paragraph("表2. DBクラスタにあるがwikiが書籍欄に載せなかった52件 — 題のパターンで暫定仕分け", H2))
story.append(Paragraph(
    "wikiは第9作以降の書籍を列挙しないが、楽天の題で型が判る。"
    "(上)(下)(上巻)(下巻)+単巻=フィルムコミック型→DROP。"
    "「○○セレクション/重要書類」=既刊の総集編(傑作選相当)→DROP。"
    "「特別編 41/42」=別シリーズ(太田勝・窪田一裕の連載コミック)で誤混入→<b>別ページでKEEP</b>。"
    "「漆黒の追跡者 1/2」(2013-14・番号付)=コミカライズの可能性→<b>要確認</b>。", PS))

groups = {
    "フィルムコミック型 → DROP (映画の画面流用本)": [
        "11人目のストライカー(上巻)+劇場版単巻", "から紅の恋歌(上)(下)", "絶海の探偵(上)(下)",
        "天空の難破船 ロスト・シップ(上巻)(下巻)+単巻", "探偵たちの鎮魂歌(上巻)(下巻)+レクイエム単巻",
        "水平線上の陰謀(上巻)(下巻)+単巻", "沈黙の15分(上)(下)+クォーター単巻",
        "異次元の狙撃手 スナイパー(上)(下)", "紺碧の棺(上)(下)+ジョリー・ロジャー単巻",
        "漆黒の追跡者 アニメコミック(上)(下)+チェイサー単巻"],
    "総集編/セレクション → DROP (既刊の寄せ集め=傑作選相当)": [
        "FBIセレクション", "SEASONAL SELECTION 春/夏/秋/冬(計10冊)", "サッカーセレクション",
        "ダブルフェイスセレクション", "トリック別セレクション", "ロマンチックセレクション",
        "5つの重要書類 file1-5", "コナンからの挑戦状!!(1)=クイズ本", "コナンと海老蔵 歌舞伎十八番ミステリー=企画本"],
    "別シリーズ誤混入 → 別ページでKEEP": [
        "特別編 41 / 特別編 42 (名探偵コナン特別編=独立した連載漫画)"],
    "要確認 → 適用前に個別判定": [
        "漆黒の追跡者 1 / 2 (2013-14・番号付=コミカライズ候補。wiki書籍欄は未掲載だが題が漫画型)"],
}
for g, items in groups.items():
    story.append(Paragraph("● " + g, P))
    for it in items:
        story.append(Paragraph("　・" + it, PS))
    story.append(Spacer(1, 2))

story.append(Spacer(1, 4))
story.append(Paragraph(
    "■ 適用時の方針(GO待ち): KEEP漫画=8作分(うちDB未収録5件は種4登録)。"
    "DROPフィルムコミック=DB内の該当を非掲載。総集編・クイズ本=DROP。"
    "特別編=movie cluster から切離し別ページ。漆黒1/2のみ要確認。", P))

SimpleDocTemplate("docs/conan-wiki-investigation.pdf", pagesize=A4,
                  topMargin=14 * mm, bottomMargin=14 * mm,
                  leftMargin=12 * mm, rightMargin=12 * mm).build(story)
print("--> docs/conan-wiki-investigation.pdf", file=sys.stderr)
