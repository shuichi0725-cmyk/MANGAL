#!/usr/bin/env python3
"""本番データ(軽量版)の項目定義書 PDF を生成。

出力: docs/mangal-data-spec.pdf
本番配信される3ファイル(一覧索引/検索索引/詳細yml)の項目名と役割を、 ★軽量化計画
([[index_lightening_plan]])反映後の構成で文書化する。 種2/seed はビルド素材で非配信=載せない。
"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "mangal-data-spec.pdf"

pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))  # 日本語ゴシック
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))     # 日本語明朝
FONT = "HeiseiKakuGo-W5"

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", fontName=FONT, fontSize=16, leading=20, spaceAfter=6, textColor=colors.HexColor("#1a1a1a"))
H2 = ParagraphStyle("H2", fontName=FONT, fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#0b5a3c"))
H3 = ParagraphStyle("H3", fontName=FONT, fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=2, textColor=colors.HexColor("#333333"))
BODY = ParagraphStyle("BODY", fontName=FONT, fontSize=8.5, leading=11.5)
CELL = ParagraphStyle("CELL", fontName=FONT, fontSize=7.6, leading=9.6)
CELLB = ParagraphStyle("CELLB", fontName=FONT, fontSize=7.6, leading=9.6, textColor=colors.HexColor("#0b5a3c"))
SMALL = ParagraphStyle("SMALL", fontName=FONT, fontSize=7.5, leading=10, textColor=colors.HexColor("#666666"))


def P(t, s=CELL):
    return Paragraph(str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), s)


def field_table(rows, cols=("項目", "型", "役割", "軽量化")):
    # rows: list of (name, type, role, light)
    data = [[P(c, CELLB) for c in cols]]
    for name, typ, role, light in rows:
        data.append([P(name), P(typ), P(role), P(light)])
    tbl = Table(data, colWidths=[34 * mm, 18 * mm, 82 * mm, 38 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f2ec")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8f7")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d4ce")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def simple_table(rows, cols, widths):
    data = [[P(c, CELLB) for c in cols]]
    for r in rows:
        data.append([P(x) for x in r])
    tbl = Table(data, colWidths=widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f2ec")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8f7")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d4ce")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


story = []

story.append(Paragraph("MANGAL 本番データ 項目定義書（軽量版）", H1))
story.append(Paragraph("対象＝これから作る予定の軽量化後の本番配信データ。 生成日 2026-06-22。", SMALL))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "本番でブラウザに配信されるのは下記の3種のみ。 種1(MADB)・種2(sqlite)・種3/種4・各種seed・"
    ".cache は<b>ビルド素材で非配信</b>のため本書には載せない。 軽量化方針＝機能は一切落とさず"
    "「値」をスリム化＋詳細から開発用フラグを除去（計画: index_lightening_plan）。", BODY))
story.append(Spacer(1, 6))

# ── 1. 一覧索引 ──
story.append(Paragraph("1. 一覧索引  manga-list-index.json", H2))
story.append(Paragraph(
    "役割＝トップ/一覧/フィルタ/カード表示。 クライアント起動時に1度だけ遅延fetchし全ページで共有。 "
    "1要素=1作品(MangaListItem)。 現状 約46.8MB → 軽量化で 約40MB 目標。", BODY))
story.append(Spacer(1, 3))
list_rows = [
    ("slug", "str", "ページ識別子。 URL と 詳細/検索索引との結合キー", "保持"),
    ("title", "str", "表示題名（カード見出し）", "保持"),
    ("title_kana", "str", "表示フリガナ＋50音ソート/検索キー（スペース無し連結）", "保持"),
    ("subtitle", "str?", "副題（カード副題）", "空ならomit"),
    ("cover_isbn", "str?", "書影のISBN。 クライアントが楽天URLを定型再構築し画像表示", "★cover URL→ISBN化 (-4MB)"),
    ("year_started", "int", "開始年（年代表示・年フィルタ・年ソート）", "保持"),
    ("year_ended", "int?", "終了年（連載中はnull）", "nullならomit"),
    ("status", "enum", "連載状態 ongoing/completed/hiatus（フィルタ・バッジ）", "保持"),
    ("catch", "str?", "キャッチコピー（カードで4行表示）", "空ならomit"),
    ("authors", "[str]", "著者名（カード表示・著者フィルタ）", "★kana/role削除=名前のみ (-2〜3MB)"),
    ("original_authors", "[str]", "原作者名（カード表示）", "★kana削除=名前のみ"),
    ("genres", "[str]", "ジャンルキー（master32種・ジャンルフィルタ）", "保持"),
    ("themes", "[str]", "要素タグ和訳（要素フィルタ・件数）", "保持"),
    ("demographic", "enum", "分野 少年/少女/青年/女性/児童/その他（フィルタ）", "保持"),
    ("publisher", "str", "代表出版社キー（最多巻の版・ヘッダ表示）", "保持"),
    ("publishers", "[str]", "全版の出版社キー集合（複数社フィルタ）", "代表1社のみならomit"),
    ("magazine", "str?", "掲載誌キー（連載誌フィルタ）", "nullならomit"),
    ("awards", "[str]?", "受賞歴（受賞作フィルタ）", "空ならomit"),
    ("anime_adapted", "bool?", "アニメ化フラグ（アニメ化作品フィルタ）", "falseならomit"),
    ("total_volumes", "int", "全版合計巻数（巻数表示・ソート）", "保持"),
    ("max_edition_volumes", "int", "最大単一版の巻数（カード巻数・ソート）", "保持"),
    ("latest_date", "str?", "最新刊 YYYY-MM（最新刊順ソート）", "nullならomit"),
    ("popularity", "int?", "AniList人気度（人気順discovery）", "無ければomit"),
    ("score", "int?", "AniList平均スコア0-100（高評価順）", "無ければomit"),
]
story.append(field_table(list_rows))
story.append(Spacer(1, 2))
story.append(Paragraph("？=任意（無い時はキーごと省略）。 [str]=文字列配列。", SMALL))

story.append(PageBreak())

# ── 2. 検索索引 ──
story.append(Paragraph("2. 検索索引  manga-search-index.json", H2))
story.append(Paragraph(
    "役割＝検索ボックスに入力があった時だけ遅延fetch（既定ブラウズでは読まない）。 "
    "題名/かなは一覧索引と重複するため<b>持たず slug で join</b>。 現状 約12.9MB → 約9MB。", BODY))
story.append(Spacer(1, 3))
search_rows = [
    ("slug", "str", "結合キー（一覧索引と join して表示）", "保持"),
    ("title_romaji", "str", "ローマ字検索（かな⇄ローマ字双方向照合）", "保持"),
    ("alt", "[str]", "別名 en/fr/de/it/pt の非空値（多言語・SEO検索）", "保持"),
    ("au", "[str]", "人物名＝著者+原作者+credits（人物名検索）", "保持"),
    ("title / title_kana", "—", "（旧）題名・かな検索用", "★削除＝一覧索引から join"),
]
story.append(field_table(search_rows))

story.append(Spacer(1, 10))

# ── 3. 詳細ページ ──
story.append(Paragraph("3. 詳細ページ  data/manga.v2/{slug}.yml", H2))
story.append(Paragraph(
    "役割＝各作品の詳細ページ。 アクセス時にそのページの1ファイルだけ取得（全66k件は配信しない）。 "
    "重い本体はここに集約。 軽量化＝本番UIが参照しない開発・監査用フラグを promote 出力時に strip。", BODY))
story.append(Spacer(1, 3))
story.append(Paragraph("3-1. 作品本体", H3))
detail_rows = [
    ("slug", "str", "識別子・URL", "保持"),
    ("title / title_kana / title_romaji", "str", "題名・フリガナ・ローマ字", "保持"),
    ("subtitle / subtitle_kana", "str?", "副題とその読み", "保持"),
    ("year_started / year_ended", "int", "開始/終了年", "保持"),
    ("status", "enum", "連載状態", "保持"),
    ("authors", "[Author]", "著者（name/role/kana/romaji）", "保持"),
    ("original_authors", "[Author]", "原作者", "保持"),
    ("credits", "[Credit]", "副次クレジット 編集/監修/訳等（表示+検索のみ）", "保持"),
    ("catch", "str?", "キャッチコピー", "保持"),
    ("publisher / publishers", "str / [str]", "代表社／全社キー集合", "保持"),
    ("magazine", "str?", "掲載誌キー", "保持"),
    ("demographic", "enum", "分野", "保持"),
    ("genres", "[str]", "ジャンルキー（master32）", "保持"),
    ("synopsis", "str", "あらすじ（NDL/AniList要約・60-120字）", "保持"),
    ("anime_adapted / anime_first_year", "bool? / int?", "アニメ化フラグ／初アニメ化年", "保持"),
    ("alternative_titles", "obj?", "公式英題等 en/fr/de/it/pt（表示・リダイレクト）", "保持"),
    ("awards", "[str]?", "受賞歴", "保持（空はomit）"),
    ("wikidata_qid", "str?", "著者QID（cross-ref/debug）", "保持"),
    ("work_wikidata_qid", "str?", "作品QID（AniList P8731経由）", "保持"),
    ("wikipedia_url", "str?", "日本語Wikipedia記事URL", "保持"),
    ("genres_anilist", "[str]?", "AniList由来genres（要素欄・比較）", "保持"),
    ("tags", "[obj]?", "AniListタグ name/category/rank（要素欄の元）", "保持"),
    ("anilist_id", "int?", "AniList ID（source追跡・外部リンク）", "保持"),
    ("popularity / score", "int?", "人気度／評価（discovery）", "保持"),
    ("synonyms", "[str]?", "AniList別名（検索補助）", "保持"),
    ("adult", "bool?", "日本MADB成年判定（表示制御）", "保持"),
    ("adult_us", "bool?", "米基準成年（AniList isAdult・geoで非日本は非表示）", "★保持（geo配信は実装予定）"),
    ("editions", "[Edition]", "版の配列（下記）", "保持"),
    ("genres_provisional", "bool?", "genresがAI暫定=低信頼フラグ（開発・監査用）", "★strip（本番UI未参照）"),
    ("genres_rakuten", "bool?", "genresが楽天あらすじ由来フラグ（開発・監査用）", "★strip（本番UI未参照）"),
]
story.append(field_table(detail_rows))

story.append(PageBreak())
story.append(Paragraph("3-2. edition（版）", H3))
story.append(simple_table([
    ("type", "enum", "版種 standard/bunkobon/wideban/kanzenban/shinsoban/aizoban 等"),
    ("label", "str", "版の表示名（通常版/文庫版 等）"),
    ("publisher", "str?", "この版の出版社（再販・他社化で版ごとに保持）"),
    ("imprint", "str?", "レーベル名"),
    ("year_started / year_ended", "int?", "この版の刊行年範囲"),
    ("volumes", "[Volume]", "巻の配列（下記）"),
    ("versions", "[obj]?", "同(社×type)同巻数の別刷 初版/新装版/復刻（古い順タブ）"),
], ("項目", "型", "役割"), [34 * mm, 20 * mm, 118 * mm]))

story.append(Spacer(1, 8))
story.append(Paragraph("3-3. volume（巻）", H3))
story.append(simple_table([
    ("number", "int", "巻番号"),
    ("volume_label", "str?", "巻ラベル 上/下/特装版 等（既定『第N巻』を上書き）"),
    ("isbn13", "str?", "ISBN-13（書影・ストアリンク・dedup・発売日突合の基点）"),
    ("release_date", "str?", "発売日 YYYY-MM（欠落はNDL補完seedで充足・時系列/dedup）"),
    ("cover_url", "str?", "書影URL（楽天/Amazon由来）"),
    ("asin / kindle_asin", "str?", "Amazon ASIN／Kindle ASIN（ストアリンク）"),
    ("description", "str?", "巻あらすじ"),
    ("artists / supervisors", "[str]?", "巻ごとの作画者／監修者（学習まんが等）"),
    ("variants", "[obj]?", "この巻の特装版/限定版 label/isbn13/cover_url/price"),
], ("項目", "型", "役割"), [34 * mm, 20 * mm, 118 * mm]))

story.append(Spacer(1, 8))
story.append(Paragraph("3-4. author（著者）／ credit（副次クレジット）", H3))
story.append(simple_table([
    ("author.name", "str", "著者名"),
    ("author.role", "enum", "writer/artist/writer_artist/editor（原作/作画分離）"),
    ("author.kana / romaji", "str?", "著者読み（50音索引）／ローマ字（検索補助）"),
    ("credit.name", "str", "副次クレジットの人物名"),
    ("credit.role", "str", "役割ラベル 編集/監修/翻訳/装丁/解説/企画/協力 等"),
], ("項目", "型", "役割"), [34 * mm, 20 * mm, 118 * mm]))

story.append(Spacer(1, 12))
story.append(Paragraph("軽量化の効き所（まとめ）", H2))
story.append(Paragraph(
    "① 索引2つ(計59.7MB)が配信の大物 → 値スリム化で約40MBへ：(a)cover URL→ISBN化 -4MB／"
    "(b)authorsのkana・role削除 -2〜3MB／(c)空のoptionalキー省略 -4〜6MB／(d)検索索引のtitle・title_kana削除 -3.5MB。 "
    "② 詳細66kから genres_provisional・genres_rakuten を strip（本番UI未参照の開発用フラグ。 ソースには残す）。 "
    "③ 機能・フィルタ・ソートは一切落とさない。 再生成は Kobo 全作harvest 完走後（今やると書影が中途半端）。", BODY))

doc = SimpleDocTemplate(str(OUT), pagesize=A4,
                        leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=12 * mm,
                        title="MANGAL 本番データ 項目定義書（軽量版）")
doc.build(story)
print(f"生成: {OUT} ({OUT.stat().st_size/1024:.0f}KB)")
