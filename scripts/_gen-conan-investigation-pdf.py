# -*- coding: utf-8 -*-
"""名探偵コナン 入れ物混線(フィルムコミック/漫画版)調査と結果 PDF。"""
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
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName=FONT, fontSize=12.5, leading=17, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#7a1f1f"))
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName=FONT, fontSize=10.5, leading=14, spaceBefore=7, spaceAfter=2, textColor=colors.HexColor("#333"))
P = ParagraphStyle("P", parent=ss["BodyText"], fontName=FONT, fontSize=9.3, leading=14)
SMALL = ParagraphStyle("S", parent=P, fontSize=8.2, leading=11.5, textColor=colors.HexColor("#444"))
CELL = ParagraphStyle("C", parent=P, fontSize=8.0, leading=10.6)
CELLH = ParagraphStyle("CH", parent=CELL, textColor=colors.white)
story = []


def para(t, st=P): story.append(Paragraph(t, st))
def sp(h=4): story.append(Spacer(1, h))
def bullets(items, st=P):
    story.append(ListFlowable([ListItem(Paragraph(x, st), leftIndent=10, value="•") for x in items], bulletType="bullet", leftIndent=12))
def steps(items, st=P):
    story.append(ListFlowable([ListItem(Paragraph(x, st), leftIndent=12) for x in items], bulletType="1", leftIndent=14))


def tbl(rows, widths, head="#7a1f1f"):
    data = [[Paragraph(c, CELLH) for c in rows[0]]] + [[Paragraph(c, CELL) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(head)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf6f6")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    story.append(t)


para("名探偵コナン 「入れ物」混線 調査と結果", H1)
para("作成: 2026-06-15 / 対象: フィルムコミックと漫画版(コミカライズ)が1作品(クラスタ)に混ざる問題。"
     "発端=テスト環境の「世紀末の魔術師 全3巻(上/第2巻/下)」で発売日が矛盾。調査のみ・本番未変更。", SMALL)
sp(4)

para("0. 結論(先に)", H2)
bullets([
    "コナンには <b>本編(青山剛昌)/ 映画コミカライズ漫画版(阿部ゆたか 等)/ 映画フィルムコミック / 特別編・スピンオフ</b> が多数あり、これらが<b>誤って混線</b>している。",
    "<b>決定打=各映画のWikipedia記事</b>。漫画版とフィルムコミックを<b>ISBN付きで別項目に明記</b>しており、我々のISBNと突合すれば<b>keep/dropを機械的・確実に確定</b>できる(実証で100%一致)。",
    "vision(表紙画像)は<b>著者取り違え</b>(本編の著者が太田勝→実は青山剛昌)を検出。Wikipedia欠落時の補助に有効。",
    "日付逆行監査は<b>弱い</b>(再版日混在の良性が大半・本件は番号0で逆行に出ない)。",
])

para("1. 問題の正体(入れ物の混線)", H2)
para("テスト環境の「名探偵コナン 世紀末の魔術師 通常版 全3巻」を調べると、3冊が別商品の寄せ集めだった:", P)
tbl([
    ["巻", "発売日", "ISBN", "実体"],
    ["1", "1999-10", "9784091248756", "フィルムコミック 上(=drop対象)"],
    ["2", "2012-09", "9784091238665", "漫画版(コミカライズ)VOL2(=keep対象)"],
    ["3", "1999-11", "9784091248763", "フィルムコミック 下(=drop対象)"],
], [10*mm, 22*mm, 42*mm, 86*mm])
bullets([
    "= <b>フィルムコミック(1999)＋漫画版(2012)のフランケンシュタイン</b>。種類の違う2商品が1ページに合体。",
    "さらに <b>AniList #31061(本編コナンのID)に誤リンク</b> → 本編のあらすじ・多言語タイトルを継承して表示。",
])

para("2. 調査の経緯(検出手法の試行)", H2)
tbl([
    ["手法", "結果", "評価"],
    ["発売日逆行監査(db-v2)", "巻番号順に発売日が逆行する版を1,646件検出。だが大半は「古い名作＋最近の再版日」混在=良性。世紀末は上下が番号0で逆行に出ない", "弱い(ノイズ多・取りこぼし)"],
    ["vision(表紙画像認識)", "本編クラスタの表紙4枚が全て「青山剛昌」表記 → データの著者「太田勝」が誤りと判明", "著者取り違え検出に有効"],
    ["Wikipedia映画記事のISBN", "漫画版/フィルムコミックを別項目でISBN付き明記。我々のISBNと突合で keep/drop が確定", "★決定打(権威・ISBN単位)"],
], [40*mm, 88*mm, 32*mm])

story.append(PageBreak())

para("3. 権威ソース=Wikipedia(漫画版 vs フィルムコミックをISBNで区別)", H2)
para("検証した5映画。漫画版=コミカライズ(描き手=阿部ゆたか等)=keep、フィルムコミック=アニメ静止画構成=drop。", SMALL)
tbl([
    ["映画", "漫画版(keep)のISBN", "フィルムコミック(drop)のISBN"],
    ["世紀末の魔術師", "9784091237095 / 238665 / 240293<br/>(阿部ゆたか・丸伝次郎・2012–13)", "9784091248756 / 248763 / 203069(完全版)"],
    ["時計じかけの摩天楼", "9784091250896(阿部ゆたか・丸伝次郎)", "9784091248718 / 248725 / 202994(完全版)"],
    ["14番目の標的", "—(漫画版は存在しない)", "9784091248732 / 248749 / 203007(完全版)"],
    ["ベイカー街の亡霊", "—(記事に「未」=漫画版なし)", "9784091268518 / 268525 / 203106(完全版)"],
    ["天空の難破船", "9784091294364 / 294517<br/>(「ロスト・シップ」・ユーザ補完)", "9784091242754 / 225740 / 225757"],
], [30*mm, 66*mm, 64*mm])
para("※Wikipediaに漫画版が無い映画(天空)も、DBのクラスタ題(「ロスト・シップ」)＋ISBNで判別できた。", SMALL)

para("4. 突合結果(我々のISBN vs Wikipedia)= 100%整合", H2)
bullets([
    "世紀末: 巻1/巻3=フィルムコミック(drop) ・ 巻2=漫画版(keep)。漫画版の残り2巻は別クラスタに存在。",
    "時計じかけ/14番目/ベイカー街: 我々の所持はすべて<b>フィルムコミック</b> → クラスタ丸ごと drop(時計じかけの漫画版1冊はDB未収録)。",
    "天空: フィルムコミック側クラスタ(drop)＋漫画版側クラスタ「ロスト・シップ」(keep)が<b>別々に存在</b>。",
])

story.append(PageBreak())

para("5. 現フォルダ(slug)分類表 ― 本番のコナン系 28件", H2)
tbl([
    ["区分 / 判定", "フォルダ(slug)= 作品", "備考"],
    ["① 本編 KEEP(著者是正)", "meitantei-conan-2011(107巻)", "著者=太田勝 → <b>青山剛昌に是正</b>(表紙で確認)"],
    ["② 要分離(フランケン)", "meitantei-conan-seikimatsu-no-majutsushi", "film上下+漫画版vol2混在・aid31061誤リンク → 分離+剥がし"],
    ["③ 映画コミカライズ漫画版 KEEP<br/>(作画 阿部ゆたか/丸伝次郎)", "ハロウィンの花嫁 / 緋色の弾丸 / 異次元の狙撃手 / 純黒の悪夢 / から紅の恋歌 / 黒鉄の魚影 / 迷宮の十字路 / 漆黒の追跡者 / 天国へのカウントダウン / 絶海の探偵 / ルパンvsコナン(×2)", "★各内部にフィルムコミック巻が混在していないか<b>ISBN要確認</b>(世紀末型の再発)"],
    ["④ 特別編・スピンオフ漫画 KEEP", "特別編2005(38巻) / 特別編2016 / 犯沢さん / ゼロの日常 / 警察学校編 / はん人をおえ / 挑戦状 / エピソードONE", "漫画として keep"],
    ["⑤ 要確認(再録セレクション)", "灰原哀 / 工藤新一 / ロマンチック の各セレクション", "既刊再録なら drop、描き下ろし有なら keep"],
    ["⑥ DROP(非漫画)", "『名探偵コナン』の推理ミス(京都トリック研究会)", "考察・研究本 → drop"],
    ["⑦ 別カテゴリ(画集)", "カラーイラスト全集", "画集 → 漫画でなく画集ストリームへ"],
], [38*mm, 78*mm, 44*mm])

para("6. 未作成 / 欠落 / 要確認フォルダ", H2)
bullets([
    "<b>時計じかけの摩天楼 漫画版</b>(9784091250896)= 本番slug無し → keepなら種4で作成候補。",
    "<b>天空の難破船 漫画版「ロスト・シップ」</b>(9784091294364/294517)= db-v2に在るが本番slug未確認 → promoteで落ちていないか要確認。",
    "<b>14番目の標的 / ベイカー街の亡霊</b>= 漫画版が元々存在しない(フィルムコミックのみ)→ 未作成で正しい(作らない)。",
])

para("7. 確定した修正方針(承認後・来歴付き・非破壊)", H2)
steps([
    "本編 meitantei-conan-2011 の著者 太田勝(作画)→ 青山剛昌 単独に是正(author補正seed)。",
    "世紀末フランケンを分離: フィルムコミックISBN=drop / 漫画版3巻=独立keep / AniList#31061剥がし(本編あらすじの誤継承解消)。",
    "③各映画の内部ISBNを残りWikipediaで突合 → フィルムコミック混在巻があれば drop。",
    "純フィルムコミック(14番目/ベイカー街 等)= drop(non-manga-drop)。",
    "全ての変更に来歴 detected_by=wikipedia-isbn / vision-cover、source、checks を付与(可逆)。",
])

para("8. 一般化と次の手", H2)
bullets([
    "同じ構造は<b>映画を持つ全フランチャイズ</b>(ドラえもん/クレヨンしんちゃん/ポケモン 等)に存在。コナンで確立した「Wikipedia ISBN × 我々のISBN」手順を横展開できる。",
    "次: コナン全映画(③含む)のWikipedia突合で<b>混在の全件確定</b> → 分類表を完成 → 承認後に上記7を適用。",
    "Wikipedia欠落の映画のみ vision / 手動補完(天空のロスト・シップ型)で埋める。",
])
sp(6)
para("以上。本書は調査結果のまとめ。データ・本番ページは未変更。", SMALL)


SimpleDocTemplate("docs/conan-investigation.pdf", pagesize=A4, topMargin=15*mm, bottomMargin=14*mm,
                  leftMargin=15*mm, rightMargin=15*mm, title="名探偵コナン 入れ物混線 調査と結果").build(story)
print("wrote docs/conan-investigation.pdf", os.path.getsize("docs/conan-investigation.pdf"))
