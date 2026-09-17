---
name: preorder_page_bypasses_mainline_class
description: 【型・総論】予約頁(preorder-pages)は種2本流を通らない=本流に足した機構が1つずつ落ちる。既知6件目まで実測。新しい充填を足したら予約合流ループにも足す
metadata:
  type: project
---

`_promote-bulk-v2.py` の頁producerは2系統ある。

- **本流** = `data/manga/*.yml` + `data/seeds/source-pages/*.yml` の srcループ → `clean_vol` と
  「最終充填pass」(L4155付近)を通る
- **予約合流** = `data/seeds/preorder-pages/*.yml` の合流ブロック(L4300-4470付近) → **どちらも通らない**

このため **本流に新しい seed 充填を足すたび、予約頁だけが取り残される**。 実測で6件:

| # | 落ちていた機構 | 気づいた日 |
|---|---|---|
| 1 | magazine-corrections | |
| 2 | genre-enrich | |
| 3 | genre-append | |
| 4 | cover-override / 書影補完 | 2026-08-04 (仮書影.gifが永久に置き換わらない) |
| 5 | release-date-override / 発売日補完 | 2026-09-04 [[preorder_date_drift_sutegoro_type]] |
| 6 | **巻説明(volume-desc-ja.jsonl)** | **2026-09-17** |

★#6 の実測: seed に文章が在るのに **何度 promote しても出ない** 頁が213頁358巻。
検証は `bff`(seed 4件が 8/16 から在る)= 修正前は `promote --only` を回しても
description 0件・**バイト数すら不変**。 修正後 4件入り 1467→1998バイト。

**How to apply:**
- ★**本流に充填を足したら、同じ規則を予約合流ループにも足す**。 規則の型は2つだけ:
  override系=「キーが在れば必ず勝つ」/ 補完系=「空の時だけ」(既存値を上書きしない)。
- ★**次の穴の探し方**: 予約合流ブロックが通している seed と本流が通している seed を突き合わせ、
  「予約頁にも意味があるのに予約側に無い」層を探す。
- 症状の見分け: 「seed に書いたのに出ない」+「promote を回しても**ファイルが1バイトも変わらない**」
  → 頁の先頭行が `= preorder-pages合流+seed適用` かを見る。
- 関連: [[seed_silently_ineffective_class]] [[preorder_page_zokkan_direct_append]]
