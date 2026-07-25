---
name: orphan_series_promote_is_srcpage_driven
description: "promoteは元頁駆動でDB駆動でない=種2に足すだけでは新規シリーズが永久に出ない(未掲載46,874)"
metadata: 
  node_type: memory
  type: project
  originSessionId: dff8a305-89f9-41d1-baa4-d9b9d0478784
  modified: 2026-07-25T00:06:57.271Z
---

★**promote は「元頁駆動」であって「DB駆動」ではない**(2026-07-25 発見)。
`_promote-bulk-v2.py:2929` = `for ypath in sorted(SRC_DIR.glob("*.yml"))` (SRC_DIR=`data/manga`) + 末尾で
`data/seeds/preorder-pages/*.yml` を合流。**種2(db-v2)を起点に新しい頁を作る処理は無い**。

## 実害
- 月次蒸留は 種2に series/volumes を INSERT するだけ = **元頁が無い新規シリーズは永久にサイトに出ない**。
- 1.2.18(2026-07)実測: 新292 series → 頁化 **85**(うち **preorder由来75** = 予約ルートで先に頁があった分) / **未頁化207**。
  207にはモーニングKC・ビッグコミックス・YJC・少年チャンピオン等の一般商業単行本が43件含まれる(=除外対象ではない)。
- 全期間: 対象58,962 → 正当drop 9,991 → 孤児48,971 = **未掲載46,874** + 分裂クラスタ2,097。
  未掲載は 単巻45,582(97%)/3巻以上534。発売年は2017-2026がほぼ均等に**年2,000件前後**=毎年ずっと漏れている。

## 原因(裏取り済み)
**著者マスター起点の初期設計**の副作用。`data/seed/mangaka.csv`(6,748名/別名込9,562表記)に載る作家から頁を作った。
- 掲載済み series = 著者がマスターに在る率 **70%** / 孤児 = **0%**。
- 成人漫画を出さないための安全側設計としては合理的。代償がマスター外作家の掲載可能作の構造的欠落。
- 残りの主体は 一般レーベル32,341(マーガレット/角川エース/りぼんMC等) / TL・BL・レディコミ系8,996 / レーベル空5,537。

## ★成人・コンビニ本での圧縮は不可(実証済)
種2不変のまま **DBコピー上で `_apply-adult-filter-v2.py` を再実行**(同scriptに `ADULT_SIM_DB` env を追加=対象DB差替)。
→ 全体 adult 6,738(現行と同等=判定は最新)、**残46,874から新規adult判定は0件**、コンビニ本imprintは37件のみ。
つまり「出すべきでない物が混ざって止まっている」のではない。**掲載scopeの方針判断**マター。 [[exclusion_priority_policy]] [[adult_judgment_architecture]]

## 検出器
`scripts/_audit-orphan-new-series.py` = 種2の巻ISBNが本番出力`data/manga.v2`に1本も無いseriesを検出。
promoteのdrop条件は**promote本体をimportして**適用(二重管理回避)。分裂クラスタは`class`列で切り分け。
出力=`docs/production-diagnostics/orphan-new-series.tsv`。`--since YYYY-MM` / `--rebuild`(promote後は必須)。
CLAUDE.md 月次サニティ監査に登録済み = **新規series中の未頁化件数が0でなければsignal**。

## 未決(GO待ち)
頁化スコープ: ①今月207件 ②3巻以上534件 ③2026年1,770件 ④全46,874件。
新規登録protocol([[new_manga_registration_order]])は1作ずつNDL/楽天で題・ヨミ・全巻を確定する手順なので④は一括不可。
