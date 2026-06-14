# -*- coding: utf-8 -*-
"""ホーム(案11)10コーナーの短縮名＋更新/閲覧計画(たたき台)をPDF化。
日本語は reportlab の CID フォント(HeiseiKakuGo-W5)で外部フォント不要。"""
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

import sys
# 既定=日本語フォント埋め込み(ビューア非依存・~47KB)。 `cid` 引数で非埋込CID(極小~5KB
# =Drive等CJKフォントを持つビューア向け。 アップロード軽量化用)。
FONT = "JP"
if "cid" in sys.argv:
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    FONT = "HeiseiKakuGo-W5"
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))
else:
    for cand in (r"C:\Windows\Fonts\msgothic.ttc", r"C:\Windows\Fonts\meiryo.ttc",
                 r"C:\Windows\Fonts\YuGothR.ttc"):
        try:
            pdfmetrics.registerFont(TTFont(FONT, cand, subfontIndex=0))
            break
        except Exception:
            continue

OUT = "docs/home-corners-naming.pdf"
os.makedirs("docs", exist_ok=True)

# (#, 短縮名, 現在の見出し, 内容, 更新要否, 更新方法(案)/閲覧)
ROWS = [
    ("1", "今週", "今週の一冊", "週替わりの注目1作を大カード＋紹介文で。最上部。",
     "★要・週1", "対象slug＋紹介文を週1指定(featured seed)。閲覧=ホーム最上部"),
    ("2", "ことば", "ことばカード", "作品あらすじの一文を大きく見せる「息継ぎ」。",
     "△自動可", "synopsis-jaから自動抽選 or 手動選定。閲覧=ホーム"),
    ("3", "三世代", "三世代・今日の一冊", "3人のペルソナ(リコ他)が日替わりで1作＋寸評。",
     "★★要・日1(3件)", "日次seed(人物×作品×寸評)。AI下書き＋人手可。閲覧=ホーム3スロット＋過去ログ(/sansedai-archive)"),
    ("4", "新刊", "今月の新刊", "今月発売の新刊棚(表紙＋題＋作者)。",
     "自動(DB)", "月次蒸留で発売日が入れば自動表示。要データ作成なし。閲覧=ホーム"),
    ("5", "暦", "発売カレンダー", "月間発売カレンダー。日付タップで直下に一覧展開。",
     "自動(DB)", "発売日データから自動(蒸留)。要データ作成なし。閲覧=ホーム"),
    ("6", "数字", "数字トリビア", "DB統計の豆知識(全○作品 等)。",
     "自動 or 軽手動", "DB集計から自動、文言だけ足すなら小seed。閲覧=ホーム"),
    ("7", "ルーレット", "ジャンルルーレット", "ランダムでジャンルページへ誘導。",
     "不要(自動)", "genres.ymlから自動抽選。要データ作成なし。閲覧=ホーム→/genre"),
    ("8", "特集", "特集", "ジャンル特集カード。まとめ記事的な入口。",
     "△随時", "特集対象(ジャンル/作品)を随時指定 or 自動ローテ。閲覧=ホーム→/browse?genre"),
    ("9", "書評", "AI書評家リーグ", "週刊・完結作をAI書評家5人がレビュー(ネタバレ無)。",
     "★要・週1(AI生成)", "週1で対象作選定→AI書評生成→seed。閲覧=ホーム＋/column-ai-league"),
    ("10", "運命", "運命の一冊", "ガチャ。↻で再抽選、ランダム1作を提示。",
     "不要(自動)", "候補プールから自動抽選。要データ作成なし。閲覧=ホーム"),
]

styN = ParagraphStyle("n", fontName=FONT, fontSize=8.5, leading=11.5)
styH = ParagraphStyle("h", fontName=FONT, fontSize=8.5, leading=11.5, textColor=colors.white)
styB = ParagraphStyle("b", fontName=FONT, fontSize=13, leading=16)
styT = ParagraphStyle("t", fontName=FONT, fontSize=16, leading=20)
styS = ParagraphStyle("s", fontName=FONT, fontSize=9, leading=13, textColor=colors.HexColor("#555555"))


def P(t, s=styN):
    return Paragraph(str(t).replace("\n", "<br/>"), s)


doc = SimpleDocTemplate(OUT, pagesize=landscape(A4),
                        leftMargin=12 * mm, rightMargin=12 * mm,
                        topMargin=12 * mm, bottomMargin=12 * mm)
story = []
story.append(P("MANGAL ホーム コーナー 命名 ＆ 更新/閲覧 計画（たたき台）", styT))
story.append(Spacer(1, 3 * mm))
story.append(P("案11ホームの上(今週の一冊)→下(運命の一冊)の全10コーナー。短縮名は社内呼称用。"
               "「更新要否」=データを作る必要があるか。★=要・自動=DB等から自動・不要=ランダム等。"
               "更新方法/閲覧は議論用のたたき台です。", styS))
story.append(Spacer(1, 4 * mm))

header = [P("#", styH), P("短縮名", styH), P("現在の見出し", styH),
          P("内容", styH), P("更新要否", styH), P("更新方法(案)・閲覧", styH)]
data = [header]
for r in ROWS:
    data.append([P(r[0]), P(r[1], styB), P(r[2]), P(r[3]), P(r[4]), P(r[5])])

col = [10 * mm, 22 * mm, 38 * mm, 70 * mm, 30 * mm, 0]
used = sum(c for c in col if c)
col[-1] = (landscape(A4)[0] - 24 * mm) - used
tbl = Table(data, colWidths=col, repeatRows=1)
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7a3b2e")),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf6f2")]),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
]))
story.append(tbl)
story.append(Spacer(1, 5 * mm))
story.append(P("まとめ: 要データ作成=【今週(週)】【三世代(日)】【書評(週)】＋【特集(随時)】。"
               "自動/不要=【新刊】【暦】【数字】【ルーレット】【運命】【ことば】。"
               "→ 次は『今週・三世代・書評』の作り方(seed形式・AI下書き運用)と閲覧導線を詰める。", styS))

doc.build(story)
print("wrote", OUT, os.path.getsize(OUT), "bytes")
