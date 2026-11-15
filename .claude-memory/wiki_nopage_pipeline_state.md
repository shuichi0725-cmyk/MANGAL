---
name: wiki-nopage-pipeline-state
description: ⏳Wikipediaの情報欄(題・巻数)×サイトで「出ていない物」を探す柱(2026-11-15新設)。道具3本・111作品はNDLの429で停止中=続きは --plan をもう一度
metadata:
  type: project
---

ユーザ発案(2026-11-15)「Wikiをダウンロードしてある。機械的に出てない物を探せないか」。きっかけ=9番目のムサシ
(本編に続編の巻が混入/サイレントブラック9巻止まり/レッドスクランブル頁なし=情報欄の巻数で全部見えた)。

## 道具(全部 手元データのみ・モデル不使用)
- `scripts/_audit-wiki-volume-gap.py` → `docs/production-diagnostics/wiki-volume-gap.tsv`(NOPAGE/SHORT/OVER の候補 2,583)
- `scripts/_gen-wiki-nopage-ready.py` → `wiki-nopage-ready.tsv`(ユーザ条件「ISBNと書影が楽天に全巻・抜けなし・漫画・成人でない」= 441作品776冊)
- `scripts/_wiki-nopage-build.py --plan / --emit`(頁seed化。保留表 `wiki-nopage-hold.tsv`・NDL結果 `.cache/wiki-nopage/ndl.jsonl`)

## 現在地(2026-11-15)
- 対象=合格441のうち「同じ著者の近い頁なし・2巻以上」111作品。ユーザGO「進めて」済み。
- ★NDL が 429 → 中断。36件取得(ヒット8)。**「NDL だけが残り」= 36作品**(未取得26+書誌なし10)。全項目そろったのは1作品(ROM-レス。)。
- 1件も頁にしていない(emit していない)。

## 続きのやり方
1. NDL を数時間休ませてから `python scripts/_wiki-nopage-build.py --plan`(取得済みは飛ばす・連続3失敗で自動中断)
2. worksheet(.cache/wiki-nopage/worksheet.jsonl)の slug を記入 → `--emit` → `_promote-bulk-v2.py --only-file .cache/wiki-nopage/emitted-slugs.txt` → preview へ
3. 保留の大きな山 = 役割(情報欄が「作者」に原案/企業名を混ぜる・作者+作画の併記)41+31 / 「既刊」表記19 / 区分18 / ジャンル根拠なし11

**Why:** 役割・ヨミを機械で確定できないものは載せない(新規登録protocol)。1回目に括弧内の役割(原案)を落として writer_artist にしかけた=見直しで捕捉。
**How to apply:** ★「NDL に書誌なし」28件は鵜呑みにしない(NDL が重い日の応答。失敗を否定記録にしない=再取得して確かめる)。
SHORT(巻が足りない・A=112)と 1巻もの211・近い頁あり119 は未着手。月次サニティの検出器登録もまだ。
関連: [[orphan_series_promote_is_srcpage_driven]](孤児=出さない裁定。今回は Wikipedia と楽天で個別に裏が取れた物だけなので別枠)[[ndl_access_rate_method]] [[feedback_never_default_author_role]]
