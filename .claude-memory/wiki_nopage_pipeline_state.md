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

## 現在地(2026-11-15 夜)
- 対象=合格441のうち「同じ著者の近い頁なし・2巻以上」111作品。**31作品を頁seed化してテスト環境へ**(4作品=NDLヨミ一致 / 27作品=下の裁定)。
  seed は data/seeds/preorder-pages/、キャッチ/あらすじは空。本番は差分反映か週次待ち。
- ★ユーザ裁定(2026-11-15・NDL が同日2回 429): **NDL の書誌が取れない時に限り**、ヨミは
  (a) 題がかな・カタカナだけで楽天のヨミと一致、または (b) Wikipedia 記事冒頭の読み=楽天のヨミ、で確定してよい(道具に実装済み)。
- 残り80作品=保留(`wiki-nopage-hold.tsv`)。NDL 未取得23・NDLと楽天のヨミ不一致7・役割が確定しない(41+31)・「既刊」19・区分18・ジャンル根拠なし11 ほか。
- slug は私が規則で付けた(英語綴りは明白な語だけ。ダブルナイト=knight/night 不明で `daburu-naito`)。

## 続きのやり方
1. NDL を休ませてから `python scripts/_wiki-nopage-build.py --plan`(取得済みは飛ばす・連続3失敗で自動中断)
2. worksheet(.cache/wiki-nopage/worksheet.jsonl)の slug を記入 → `--emit` → `_reflect-targeted.py --only <slugs>` → .preview-data へコピー+索引
3. 保留の大きな山 = 役割(情報欄が「作者」に原案/企業名を混ぜる・作者+作画の併記)は1件ずつ

**Why:** 役割・ヨミを機械で確定できないものは載せない(新規登録protocol)。1回目に括弧内の役割(原案)を落として writer_artist にしかけた=見直しで捕捉。
**How to apply:** ★「NDL に書誌なし」28件は鵜呑みにしない(NDL が重い日の応答。失敗を否定記録にしない=再取得して確かめる)。
SHORT(巻が足りない・A=112)と 1巻もの211・近い頁あり119 は未着手。月次サニティの検出器登録もまだ。
関連: [[orphan_series_promote_is_srcpage_driven]](孤児=出さない裁定。今回は Wikipedia と楽天で個別に裏が取れた物だけなので別枠)[[ndl_access_rate_method]] [[feedback_never_default_author_role]]
