# -*- coding: utf-8 -*-
"""PDF1: MANGAL データファイルの素性と名称(取得物 vs 制作物・簡略版)。"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
                                ListFlowable, ListItem)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT = "JP"
for cand in (r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\msgothic.ttc"):
    if os.path.exists(cand):
        pdfmetrics.registerFont(TTFont(FONT, cand, subfontIndex=0)); break

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName=FONT, fontSize=16, leading=21, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#1a1a1a"))
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName=FONT, fontSize=12.5, leading=17, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#1f5a7a"))
P = ParagraphStyle("P", parent=ss["BodyText"], fontName=FONT, fontSize=9.3, leading=14)
SMALL = ParagraphStyle("S", parent=P, fontSize=8.2, leading=11.5, textColor=colors.HexColor("#444"))
CELL = ParagraphStyle("C", parent=P, fontSize=8.0, leading=10.5)
CELLH = ParagraphStyle("CH", parent=CELL, textColor=colors.white)
story = []


def para(t, st=P): story.append(Paragraph(t, st))
def sp(h=4): story.append(Spacer(1, h))
def bullets(items, st=P):
    story.append(ListFlowable([ListItem(Paragraph(x, st), leftIndent=10, value="•") for x in items], bulletType="bullet", leftIndent=12))


def tbl(rows, widths, head="#1f5a7a"):
    data = [[Paragraph(c, CELLH) for c in rows[0]]] + [[Paragraph(c, CELL) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(head)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f7fa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    story.append(t)


para("MANGAL データファイルの素性と名称 ―― 取得物 / 制作物(簡略版)", H1)
para("作成: 2026-06-15 / 目的: いま&今後使うデータを「外から取る物=取得物」と「我々が作る物=制作物」に二分し、"
     "名称・素性・取得元・頻度を一枚で把握する。※細かな補正seedは束ねて簡略化。", SMALL)
sp(4)

para("0. 一行で", H2)
para("<b>取得物</b>(外部から取る素材)を、<b>制作物</b>(我々が組み上げる物)が食べて、最終的に "
     "<b>本番DB(data/manga.v2)→ 索引 → 配信(out/・R2)</b> になる。取得物の更新頻度は "
     "<b>毎蒸留 / 凍結(再取得不要) / 随時 / 将来</b> の4段。", P)

# ===== 取得物 =====
para("1. 取得物(外部から取る素材)", H2)
tbl([
    ["名称(素性)", "何が入っているか", "取得元", "頻度"],
    ["種1: MADB巻データ<br/>(cm101 / metadata101)", "単行本の書誌=ISBN・巻番号・発売日・出版社・タイトル", "MADB(GitHub全件JSON or 公式サイト月次CSV)", "<b>毎蒸留</b>(新刊)"],
    ["MADB著者(cm504)", "著者マスター・読み・NDL典拠ID", "MADB", "<b>毎蒸留</b>"],
    ["MADBシリーズ/雑誌master<br/>(cm104 / cm105 / cm103)", "シリーズ束ね・著者役割([原作]/[作画])・雑誌", "MADB", "<b>凍結</b>(2024-11で更新停止=再取得不要)"],
    ["漫画家マスター<br/>(data/seed/mangaka.csv)", "漫画家 約6,751名(別input)", "手元CSV", "ほぼ固定"],
    ["AniList", "英あらすじ・ジャンル・タグ・別名・人気/評価・staff(著者)・anilist_id", "AniList API", "<b>毎蒸留</b>(新作enrich)"],
    ["楽天ブックス", "表紙・価格・発売日(日精度)・アフィリエイトURL", "楽天 Books API(1req/秒)", "<b>毎蒸留</b>(新ISBN)"],
    ["Wikidata / Wikipedia", "作品QID・著者QID・ジャンルカテゴリ・記事URL", "WDQS / QLever / API", "随時(品質・enrich時)"],
    ["NDL(国立国会図書館)", "タイトル読み(ふりがな正)・著者典拠・巻構造", "NDL SRU", "随時(品質監査時)"],
    ["成年判定リスト", "成年作家/出版社/雑誌", "adultcomic.dbsearch.net 等", "随時"],
    ["Amazon PA-API", "表紙・ASIN(楽天に無い旧巻の補完)", "Amazon", "<b>将来</b>(売上ゲート達成後)"],
], [38*mm, 56*mm, 38*mm, 25*mm])
para("※OpenBD はサービス終了のため不使用。書影の本命は楽天(無料)→将来Amazon。", SMALL)

story.append(PageBreak())

# ===== 制作物 =====
para("2. 制作物(我々が作る物)と、食べている取得物", H2)
tbl([
    ["名称(素性)", "何", "元になる取得物", "再生成/更新頻度"],
    ["種2: 派生DB<br/>(.cache/db.sqlite, db-v2.sqlite)", "種1を正規化したSQLite(series/volumes/mangaka)", "種1(MADB)", "<b>毎蒸留</b>(取込時)。.cache=再生成可"],
    ["種3: series-supplement.yml", "作品単位のAI補完の蓄積", "AI(AniList素材)", "<b>毎蒸留</b>(純粋追加only)"],
    ["種4: volumes-supplement.yml", "MADB取りこぼし巻の手補完", "手(Amazon/NDL/公式で確認)", "随時(手動add)"],
    ["synopsis-ja.json", "AI日本語あらすじ要約(anilist_id key)=高価なAI生成物", "AniList英descをAI要約", "<b>毎蒸留</b>(純粋追加)"],
    ["catch-ja.json", "キャッチコピー(slug key)", "AI生成(あらすじ素材)", "随時/蒸留"],
    ["release-date-fill.json", "発売日の日精度補完(isbn key)", "楽天", "<b>毎蒸留</b>"],
    ["品質補正seed群<br/>(furigana-corrections / author-yomi /<br/>author-role-corrections / slug-aliases /<br/>non-manga-drop / page-dedup / series-merge 等)", "ふりがな・著者読み・役割・slug別名・除外・重複統合などの補正蓄積", "NDL / 手 / AI", "随時(純粋追加)"],
    ["master(設定)<br/>(genres / publishers / magazines /<br/>demographics .yml)", "語彙・キー定義(裁定マター)", "手(ユーザ裁定)", "随時(新キーflag時)"],
    ["★本番DB: data/manga.v2", "全部を焼き込んだ公開出力(約66,582作・gitignore)", "promote=種2+種3+種4+seed+取得をjoin", "<b>毎蒸留</b>(全再生成)"],
    ["索引(A SQLite + S1/S2/S3)", "検索/監査/配信用の索引(別仕様書)", "data/manga.v2", "promote毎(再生成可)"],
    ["配信: out/ + R2バケット", "静的サイト本体(HTML/JS/索引)", "data/manga.v2 + 索引", "デプロイ毎"],
], [44*mm, 40*mm, 40*mm, 33*mm])

# ===== 系譜 =====
para("3. 系譜(取得 → 制作 → 配信)の一望", H2)
para("取得物 ──┬─ <b>種1(MADB巻/著者)</b> ─→ <b>種2(派生DB)</b> ┐<br/>"
     "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ AniList / 楽天 / NDL / Wikidata ─→ <b>種3・synopsis-ja・release-date-fill・各補正seed</b> ┤<br/>"
     "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└─ 手(種4・master) ─────────────────────────┘<br/>"
     "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↓ <b>promote(全部join・焼き込み)</b><br/>"
     "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>本番DB data/manga.v2</b> ─→ <b>索引(A/S1/S2/S3)</b> ─→ <b>out/ ・ R2 配信</b>", P)

# ===== 頻度まとめ =====
para("4. 「どこから・どの頻度で取るべきか」まとめ", H2)
bullets([
    "<b>毎蒸留(必須)</b>: MADB(cm101巻+cm504著者)/ AniList(enrich)/ 楽天(表紙・価格・日付)。"
    "→ これらが新刊と補完の源。cm104凍結で著者役割が新作に無い分も AniList で恒久補完。",
    "<b>凍結(再取得不要)</b>: MADB cm104/cm105/cm103(2024-11停止)。シリーズ束ね・雑誌・役割マスターは固定。",
    "<b>随時</b>: NDL(ふりがな/巻構造の裏取り)/ Wikidata(QID・ジャンル)/ 成年リスト。品質監査・特定課題のとき。",
    "<b>将来</b>: Amazon PA-API(楽天に無い旧巻表紙)。売上ゲート達成後。",
])

para("5. 運用原則(素性の扱い)", H2)
bullets([
    "<b>再生成できる物は git に焼かない</b>: 種2DB・索引・out/ は .cache/出力(レシピ=スクリプトだけ追跡)。",
    "<b>高価なAI生成物だけ seed 化</b>: synopsis-ja.json / catch-ja.json / 種3 は作り直しが高いので git 永続化。",
    "<b>取得物は dedup 前提</b>: MADB-IDで upsert + ISBN/巻番号で重複除去(経路が重なっても安全)。",
    "<b>純粋追加 only</b>(種1/2/3): 既存の上書き/削除は禁止=蒸留の大原則。",
], SMALL)
sp(4)
para("要約: 取得物=MADB/AniList/楽天/NDL/Wikidata/成年/(将来Amazon)。制作物=種2DB・種3/4・各seed・master・本番manga.v2・索引・配信。"
     "毎蒸留で動く取得物は MADB・AniList・楽天 の3本。", SMALL)


SimpleDocTemplate("docs/mangal-data-assets.pdf", pagesize=A4, topMargin=15*mm, bottomMargin=14*mm,
                  leftMargin=15*mm, rightMargin=15*mm, title="MANGAL データファイルの素性と名称").build(story)
print("wrote docs/mangal-data-assets.pdf", os.path.getsize("docs/mangal-data-assets.pdf"))
