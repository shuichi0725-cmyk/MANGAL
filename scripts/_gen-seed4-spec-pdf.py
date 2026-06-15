# -*- coding: utf-8 -*-
"""種4 拡張 設計仕様 PDF: 来歴(保険)+ 欠番補完(楽天) + 版追加(完全版/フルカラー)。実装はこの承認後。"""
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
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName=FONT, fontSize=12.5, leading=17, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#2a6a3a"))
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName=FONT, fontSize=10.5, leading=14, spaceBefore=7, spaceAfter=2, textColor=colors.HexColor("#333"))
P = ParagraphStyle("P", parent=ss["BodyText"], fontName=FONT, fontSize=9.3, leading=14)
SMALL = ParagraphStyle("S", parent=P, fontSize=8.2, leading=11.5, textColor=colors.HexColor("#444"))
WARN = ParagraphStyle("W", parent=P, fontSize=9.3, leading=14, textColor=colors.HexColor("#a11"))
CELL = ParagraphStyle("C", parent=P, fontSize=8.1, leading=10.8)
CELLH = ParagraphStyle("CH", parent=CELL, textColor=colors.white)
story = []


def para(t, st=P): story.append(Paragraph(t, st))
def sp(h=4): story.append(Spacer(1, h))
def bullets(items, st=P):
    story.append(ListFlowable([ListItem(Paragraph(x, st), leftIndent=10, value="•") for x in items], bulletType="bullet", leftIndent=12))
def steps(items, st=P):
    story.append(ListFlowable([ListItem(Paragraph(x, st), leftIndent=12) for x in items], bulletType="1", leftIndent=14))


def tbl(rows, widths, head="#2a6a3a"):
    data = [[Paragraph(c, CELLH) for c in rows[0]]] + [[Paragraph(c, CELL) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(head)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f7f3")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    story.append(t)


para("種4 拡張 設計仕様 ―― 来歴(保険)+ 欠番補完 + 版追加", H1)
para("作成: 2026-06-15 / 目的: 種4を「MADB取りこぼし巻の手補完」から、(A)欠番補完(楽天起点)・(B)版まるごと追加"
     "(完全版/フルカラー)・(C)来歴(保険)込み へ拡張する。<b>実装はこの承認後。本書はレビュー用。</b>", SMALL)
sp(4)

para("0. 大前提(安全=慎重運用)", H2)
bullets([
    "<b>種2 sqlite は不変</b>。種4は別ファイル=<b>非破壊・可逆</b>(間違えても種4の行を消せば戻る)。",
    "<b>純粋追加 only</b>。既存エントリの上書き/削除はしない。",
    "<b>promote は余分なキーを無視</b>する(必要キーだけ拾う)=項目追加は<b>非破壊</b>(実コードで確認済)。",
    "<b>段階導入</b>: まず手動発見の1–2作で検証 → 自動は confidence=high のみ → 残りは pending(人が見る)。",
])

# ===== 1. 来歴項目 =====
para("1. 種4 スキーマ拡張 ―― 来歴(保険)項目", H2)
para("既存項目: series_keys / qid / number / isbn13 / release_date / pages / publisher / edition_type / title_display / source / added_at / note。これに来歴を追加:", P)
tbl([
    ["追加項目", "問い", "値の例"],
    ["detected_by", "<b>なぜ/どの検査で</b>見つかったか(契機・動機)", "manual.user(あなたが発見)/ manual.curator / audit.volume-gap(全件欠番監査)/ audit.trailing / audit.ndl / audit.&lt;将来&gt;"],
    ["source", "データは<b>どこから</b>取ったか(出所・精密化)", "rakuten-api / ndl / amazon / publisher-official / manual"],
    ["run", "<b>どのスクリプト/バッチ</b>が・いつ実行したか", "_fill-volume-gaps.py@batch12 ・ 2026-06-15"],
    ["checks", "<b>どう確認</b>したか(通った照合)", "[title_match, author_match, publisher_match, number_in_gap, date_monotonic, isbn_prefix]"],
    ["confidence", "信頼度", "high / med / low"],
    ["evidence", "証跡", "{rakuten_title:\"タワーダンジョン(3)\", item_url:\"…\", isbn:\"…\"}"],
    ["state", "状態", "applied / pending / reverted"],
], [26*mm, 60*mm, 74*mm])
para("→「何が抜け / どこから / どう確認 / いつ / <b>なぜ(契機)</b> / 誰が / 取消手がかり」が<b>1エントリで完結</b>。"
     "detected_by は種4に限らず<b>今後の全検査が共通で書く「契機」欄</b>として使う(検査バグ時に由来で一括追跡・巻戻し)。", SMALL)
para("※enum(決め打ち)で表記揺れ防止。値の確定は §6 未決。", SMALL)

# ===== 2. 欠番補完 =====
para("2. 機能A ―― 欠番補完(楽天起点・「錨あり」=安全部分集合)", H2)
para("既知作品の内部欠番(例 tower-dungeon が 1,2,5,6 で 3,4 欠落)を、既存巻を錨に楽天で埋める。", P)
steps([
    "種2/本番を走査し、既知作品の<b>巻番号の抜け</b>を検出(_audit-volume-gaps の結果を利用)。",
    "その作品を<b>楽天タイトル検索</b>→全巻リスト取得。",
    "DBの番号と突合し<b>欠番だけ</b>抽出。各候補を多重照合: <b>題一致・著者一致・出版社一致・番号がgap内・発売日が単調・ISBN発行者帯一致</b>(checksに記録)。",
    "<b>confidence=high(主要signal全通過)のみ種4へ自動登録</b>。グレーは pending(人が確認)。",
    "登録時に来歴(detected_by=audit.volume-gap / source=rakuten-api / run / checks / evidence)を必ず書く。",
])
para("★この「錨あり」クラスは作品同定が済んでいるので<b>NDL不要</b>(新刊は楽天が新鮮)。"
     "危険な「錨なし(宙ぶらりんISBN)」・「再クラスタ」は本機能の対象外=従来どおりNDL/手動。", SMALL)

story.append(PageBreak())

# ===== 3. 版追加 =====
para("3. 機能B ―― 版まるごと追加(完全版 / フルカラー)", H2)
para("例: ドラゴンボールが現在「通常版」のみ → 完全版・フルカラーコミックを版ごと取り込む。", P)
para("仕組みは既にある(実コード確認)", H3)
bullets([
    "種4エントリは <b>edition_type</b> を持つ。promote は該当 edition_type の版へ追加し、<b>無ければ新しい版グループを自動生成</b>(_promote-bulk-v2.py L1481–1489)。",
    "詳細ページは<b>複数版タブ表示に対応済</b>(例: SLAM DUNK の 通常版/デラックス版/愛蔵版)。",
])
para("版追加のために整える3点(コード小修正)", H3)
tbl([
    ["#", "課題(現状)", "対応"],
    ["a", "フルカラーの edition_type が未定義(許可リストは standard/bunkobon/wideban/kanzenban/shinsoban/aizoban/deluxe)", "<b>fullcolor を型に追加</b>+ラベル「フルカラー版」。完全版=kanzenban は既存で可"],
    ["b", "対象作が「版を畳む」設定だと別版が統合される", "対象作を <b>separate_editions 指定</b>(版を畳まず版名タブで分離)"],
    ["c", "新規版グループの初期ラベルが「通常版」固定(L1484)。separate_editions作は後段で上書きされるが非対象作は誤表示", "<b>初期ラベルを edition_type 由来に堅牢化</b>(完全版→「完全版」)"],
], [8*mm, 92*mm, 60*mm])
para("運用: 種4に該当版の全巻を edition_type 付き+ISBN で登録(detected_by=manual.curator / source=楽天 or 出版社)。"
     "promote 再生成で版タブが立つ。種2 は不変。", SMALL)

# ===== 4. 安全策 =====
para("4. 安全策・可逆性(慎重運用の核)", H2)
bullets([
    "種4は別ファイル・<b>種2不変</b>=登録は非破壊。<b>間違えた行を消すだけで巻き戻し</b>。",
    "<b>二重表示防止</b>: 同番号が種2に在れば種4を skip(MADB追いつき時=種2優先・既存ガード)。",
    "<b>誤紐付け防止</b>: series_keys が db に bind しない/巻番号重複 は登録せず pending(既存validate)。",
    "<b>誤ISBN(特装版/別物)防止</b>: checks(題・著者・出版社・番号・日付・ISBN帯)を全通過した high のみ自動。",
    "<b>由来追跡</b>: detected_by + run で「どの検査・どのバッチが入れたか」→ 後で検査バグ判明時に<b>その由来の全件を抽出して再検証/revert</b>。",
])

# ===== 5. 影響範囲 =====
para("5. 触る物 / 触らない物", H2)
tbl([
    ["触る(追加・小修正)", "触らない"],
    ["種4 yml(追加only・来歴項目)<br/>新規 scripts(_fill-volume-gaps.py 等)<br/>promote の3点小修正(版追加用 a/b/c)", "種2 sqlite / 種1 / 種3<br/>本番への即時反映(=promote再生成時に確定)<br/>既存の手動 volumes-supplement.yml(不変)"],
], [85*mm, 75*mm])

# ===== 6. 未決 =====
para("6. 未決点(着手前に確認)", H2)
bullets([
    "(a) confidence=high の<b>閾値</b>: どのsignalが何個一致で high とするか(例: 題+著者+出版社+番号in-gap+日付単調 の5通過=high)。",
    "(b) <b>自動登録 vs pending人手</b> の線引き(highは自動 / medはpending、で良いか)。",
    "(c) detected_by の <b>enum 確定</b>(値の語彙)。",
    "(d) フルカラー以外に新設すべき版型(オールカラー等の呼称統一)。",
    "(e) 段階導入の<b>最初の検証対象</b>(案: tower-dungeon 欠番3,4 / ドラゴンボール完全版)。",
])
sp(6)
para("以上。承認 or 修正点をいただければ、(1)種4スキーマに来歴項目追加 →(2)_fill-volume-gaps.py(楽天・錨あり)→"
     "(3)promote 3点修正(版追加)の順で、<b>1–2作で検証してから</b>慎重に進めます。", P)


SimpleDocTemplate("docs/mangal-seed4-extension-spec.pdf", pagesize=A4, topMargin=15*mm, bottomMargin=14*mm,
                  leftMargin=15*mm, rightMargin=15*mm, title="種4 拡張 設計仕様").build(story)
print("wrote docs/mangal-seed4-extension-spec.pdf", os.path.getsize("docs/mangal-seed4-extension-spec.pdf"))
