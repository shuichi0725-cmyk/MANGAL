# -*- coding: utf-8 -*-
"""PDF2: 月次蒸留 計画書(全て)。CLAUDE.md の protocol を一冊に整形。"""
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
WARN = ParagraphStyle("W", parent=P, fontSize=9.3, leading=14, textColor=colors.HexColor("#a11"))
CELL = ParagraphStyle("C", parent=P, fontSize=8.2, leading=11)
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


# ============ 表紙 ============
para("月次蒸留 計画書(全文)", H1)
para("MANGAL データ更新の標準手順。トリガー語「<b>月次蒸留して</b>」(完全一致)でこの手順を厳密実行する。"
     "本書は CLAUDE.md の protocol を一冊に整形したもの。", SMALL)
sp(4)

para("0. 大原則(絶対遵守)", H2)
para("<b>種1 / 種2 / 種3 は壊さない。</b> 差分は<b>純粋追加 only</b>。既存への上書き・削除・編集は禁止。"
     "上書き/削除/既存破壊を一件でも検出した時点で<b>即 abort + ユーザ通知</b>。", WARN)
para("種1=MADB raw / 種2=派生DB(sqlite)/ 種3=AI fill蓄積 / 種4=巻補完。系譜は別紙(データ素性PDF)。", SMALL)

# ============ Phase 0 ============
para("1. Phase 0 ―― 前提確認(1つでも欠ければ即 abort)", H2)
para("以下が無い場合「対象Xが無いので蒸留できない」と報告して終了。自動 fallback / 自動作成はしない。", P)
tbl([
    ["必要なもの", "素性"],
    [".cache/madb-last-release.txt", "前回取込んだ MADB release tag"],
    [".cache/db.sqlite", "種2=派生DB"],
    ["data/seeds/series-supplement.yml", "種3=AI fill蓄積"],
    ["種1 raw(cm101.csv / metadata101.json)", "MADB release zip 由来(.cache配下に unzip 想定)"],
    ["data/seed/mangaka.csv", "漫画家マスター(約6,751名・種1とは別input)"],
    ["scripts/_diff-madb.ts / _diff-series.ts / _select-supplement-diff.ts", "種1差分 / 種2差分 / 種3 fill候補生成"],
    ["git status = clean", "dirty なら abort"],
], [80*mm, 80*mm])

# ============ Phase 1 ============
para("2. Phase 1 ―― 差分レポート + Go サイン待ち", H2)
steps([
    "MADB latest release を GitHub API で取得(確定 repo)。",
    "前回取込 tag と比較し、各層の差分件数を表示: <b>種1</b>=新ISBN N件/新mangaka推定 ・ <b>種2</b>=新series M件(4層 adult filter後)・ <b>種3</b>=未fill K件。",
    "AI fill 予想コスト: K/100 batch、Jセッション分、概算金額。",
    "<b>削除予測=0件</b>を明示(0でなければ Phase2 に進まず別途協議)。",
    "「<b>進めて OK?</b>」でユーザ確認。Goサイン(「OK」「進めて」「ゴー」等の明示的肯定)受領まで Phase2 に進まない。",
])

# ============ Phase 2 ============
para("3. Phase 2 ―― Go サイン後の実行(順序厳守)", H2)
steps([
    "<b>種1 取込</b>: cm101.csv 取得 → 新ISBNのみ追記、既存行は不変。",
    "<b>種2 差分反映</b>: fetch-madb incremental、INSERT only(削除禁止)。",
    "<b>派生層+matcher+本番 再生成</b> = <font face='%s'>python scripts/intake.py --run</font>。"
    "内訳: roles→merge→seed4→detect → <b>matcher v9→v13→v14</b> → adult_us map → trailing → "
    "<b>foreigndrop</b>(外国版自動drop)→ <b>promote</b>(adult_us付与)。"
    "※matcherは約20分。終了後 git diff で本番yml確認→commit/push。" % FONT,
    "<b>種a productionization の種3書込</b>(match-v14確定後): en-fill=AniList英題を alternative_titles.en に純粋追加"
    "(.new検証→置換)。将来: anilist_id 結線も同手法で純粋追加。",
    "<b>種3 diff 元生成</b>: select-supplement-diff で未fill key list 出力。",
    "<b>AI fill batch loop</b>: dict形式JSON・100entry/batch・_apply-fills 適用。PUA文字混入時は Python経由で生キー書出。"
    "JST時刻付き block単位報告。commit+push。",
    "<b>最終 summary</b>: 全件数 + 削除0確認 + 次月予測。",
])

story.append(PageBreak())

# ============ 保護策 ============
para("4. 保護策(5層)", H2)
steps([
    "取込前に .cache/db.sqlite を db.sqlite.bak-YYYYMMDD-HHMMSS に backup。",
    "種1/種2/種3 の各取込は<b>単独 commit で分離</b>(後 revert 可)。",
    "各 batch 後に <b>applied=N, missing=0, overwrites=0</b> を強制 log 出力。",
    "tsc / vitest が以前緑なのに<b>赤転落で abort</b>。",
    "想定外 delete / overwrite 検出で abort。",
])

para("5. Abort 条件(検出したら即停止+通知)", H2)
bullets([
    "種1 既存行が変更された(MADBが過去ISBNを訂正したケース)。",
    "種2 series数が<b>減った</b>(削除発生=異常)。",
    "種3 既存 key の content が変わった(上書き=異常)。",
    "typecheck / test の green→red 転落。",
], WARN)

para("6. 報告形式", H2)
bullets([
    "100 batch ごと: 「🎉 Batch NNN/MMM 完了 (= X/Y = Z%) [JST YYYY-MM-DD HH:MM:SS]」。",
    "完了時: 累計件数 + 残件数 + 次月予測。",
])

# ============ データ実態 ============
para("7. データ実態と運用補強(必読)", H2)
para("MADB データ入手=2経路", H3)
bullets([
    "<b>GitHub 全件JSON</b>(github.com/mediaarts-db/dataset)= その日までの全件snapshot(baseline)。"
    "重いが <font face='%s'>madbdata:dateModified</font> を持つ=<b>変更検知に使える</b>。" % FONT,
    "<b>MADBサイト 月次CSV</b>(s-db.artmuseums.go.jp)= 項目×月単位(登録日基準の差分)。軽い・新鮮・"
    "<b>未来の発売前予約も載る</b>。ただし更新日列が無い=修正に気付けない(列52・複数著者は ＼＼ 区切り)。",
    "<b>運用</b>: GitHub全件を定期 re-sync して訂正回収 + 月次サイト差分で新刊 top-up。",
])
para("master 凍結の実態", H3)
bullets([
    "<b>cm104(シリーズmaster)/ cm105(雑誌)/ cm103 は 2024-11-25 で凍結</b>。最新リリースでも同じ=再DL無駄。"
    "更新は cm101(巻)+ cm504(著者)のみ。",
    "帰結: 新刊は「マンガ単行本シリーズ」链 0%=シリーズ層は空。著者役割([原作]/[漫画])は cm104 にしか無く、"
    "新作は <b>AniList 補完が恒久策</b>(gapは毎月増える)。",
])
para("取込の必須2策", H3)
bullets([
    "<b>重複</b>: MADB-ID で upsert + ISBN/巻番号で dedup(冪等・経路が重なっても安全)。"
    "危険型=「別MADB-ID+別ISBNでの再登録」(虚構推理vol23型)→ 監査で検知。",
    "<b>変更検知</b>: 月次CSVは更新日列が無く修正を見逃す → GitHub全件の dateModified を定期比較して訂正回収。",
])
para("enrich=毎月の必須ステップ(masterが埋めないため)", H3)
bullets([
    "AniList 照合 → 著者補完(原作/作画分離)/ synopsis和訳 / 作品QID / 種4 trailing補完。",
    "凍結で新作 gap が累積 → 毎蒸留で再フェッチ(一度きりでない)。",
])

story.append(PageBreak())

para("8. synopsis 和訳 = git追跡 seed(永続化の正規ルート)", H2)
bullets([
    "<b>何</b>: AniList英descを AIが60–120字の日本語<b>要約</b>に(逐語訳でなく要約=著作権配慮)。key=<b>anilist_id</b>(作品単位)。",
    "<b>どこ</b>: data/seeds/synopsis-ja.json(git追跡seed・{anilist_id:ja}の単純map)。",
    "<b>なぜseed化</b>: synopsisだけが「高価なAI生成物」。他のenrich(synonyms/genres/tags/anilist_id/QID)は dump+match から"
    "毎promoteタダで再joinできるので git に焼かない(再生成可能なものは永続化しない原則)。種3本体にも焼かない。",
])
para("蒸留での扱い(純粋追加only)", H3)
steps([
    "enrich(match-v14)で新規 anilist_id が増える → _build-anilist-enrich-map.py。",
    "未訳delta抽出: enrichのaidのうち synopsis-ja.json に未存在 かつ AniList desc有 を todo化(100件/batch)。",
    "分散workflowで各batchをAI要約 → 書出(中断耐性)。",
    "全出力を merge → _apply-synopsis.py で synopsis-ja.json へ純粋追加(新規N/上書き0を確認)。",
    "commit + push(git永続化=別PC・モバイルでも消えない)。",
    "本番反映は全DB promote 時に manga.v2 へ焼かれて確定(seed commitだけでは本番に出ない)。",
])
para("成人(isAdult): 露骨な性描写は要約に含めない/中立化。表示は adult_us/geo で出し分け。", SMALL)

# ============ サニティ監査 ============
para("9. 月次サニティ監査(silent例外の安全網)", H2)
para("取込後に<b>前月差分で異常を機械flag</b>する。個別例外を全部予見できない前提の最後の砦。", P)
tbl([
    ["監査層", "ツール / 内容"],
    ["土台(被覆・品質)", "_coverage-audit.py=真の公開数・被覆・品質flag。前月差分で『今月だけ急増した異常』を浮かす"],
    ["巻番号", "_audit-volume-numbering.py=AUTO_FIXED(下=3型水増し是正済・件数監視)/ MISSING_HALF(片側欠落=種4領域)/ GAP_OTHER(真の欠番・外れ値)"],
    ["フリガナ", "_furigana-audit.py=NDL公式読みをground-truthに誤フリガナ検出"],
    ["外国版", "_audit-foreign-editions.py=複数証拠(latin題/全ISBN非9784/複数巻)で scope外を検出→foreigndropで純粋追加drop"],
    ["出版社", "各版の出版社は ISBN→metadata101 schema:publisher から自動導出。新規の未キー社名を巻数順にflag→主要なら publishers.yml にキー追加"],
], [30*mm, 130*mm])
para("既知の例外型: 再登録の別ID二重化 / MADB形式変更(タグ消失・年→巻番号)/ 成年誤flag(新レーベル未カバー)/ "
     "雑誌漏れ(cm105凍結)/ 巻番号水増し(下=3型)/ 外国版流入(ISBN国コード非9784)。", SMALL)

# ============ 種4 ============
para("10. 種4(MADB取りこぼし巻 補完)の扱い", H2)
bullets([
    "種4 = data/seeds/volumes-supplement.yml。公式販売されているが MADB record に無い巻を、別source"
    "(Amazon/NDL/出版社公式)で確認後に登録。種2 sqlite は不変。",
    "<b>月次蒸留では触らない</b>(手動add only)。audit + 本番yml生成時に load される。",
    "render時ガード: 同番号が種2に在れば種4を skip(MADB追いつき時の二重表示防止)。",
    "退役 hygiene: MADBが追いついた種4 entry を月次で除去=lean維持。",
])
sp(6)
para("以上が月次蒸留の全手順。トリガーは「月次蒸留して」。Phase0→1(Goサイン)→2 を順序厳守、純粋追加only、"
     "異常検出で即abort。", SMALL)


SimpleDocTemplate("docs/mangal-distillation-plan.pdf", pagesize=A4, topMargin=15*mm, bottomMargin=14*mm,
                  leftMargin=15*mm, rightMargin=15*mm, title="月次蒸留 計画書").build(story)
print("wrote docs/mangal-distillation-plan.pdf", os.path.getsize("docs/mangal-distillation-plan.pdf"))
