---
name: worklist_needs_generator_and_freshness
description: 【戒め】人が裁く表(worklist/裁定表)は生成器を持たせ、入力より古ければ自動で作り直す。「書き手がいるか」はgrepでは判定できない(動的ファイル名)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 19c40654-3fa1-4eb7-af6e-40057dab95ee
  modified: 2026-09-06T14:09:12.932Z
---

台帳・裁定表が**凍る**事故が 2026-09-06 に**2件**続けて出た。 どちらもユーザ発見。

| 台帳 | 症状 | 実害 |
|---|---|---|
| `vol_gap.tsv` | 2026-07-16 で停止。 `_volgap-virtual.py` の候補入力だった | 当時の1,417頁を再チェックするだけ = 以後の巻抜けが永久に出ない(『皆様の玩具です』) |
| `shu2-unlisted-review.tsv` | **手打ちで生成器が repo に無い** | 是正済み3頁が表に残り、新規頁は表に入らない |

## ★やること

1. **人が裁く表は必ず生成器を repo に置く**。 検出器の出力(芯TSV)から**毎回組み直す**。
2. 生成器は **入力の鮮度を自分で見る**。 本番/上流が入力より新しければ **自動で作り直す**
   (`scripts/_gen-shu2-unlisted-review.py` が実装形: 本番yml > 芯TSV の mtime なら検出器を回す)。
3. 生成のたびに **「前回比: 解決N / 新規N」** を出す。 これが無いと凍っても気付けない。
4. ★行番号で指す運用(「見なおしの N なおして」)なら **#列に行番号を焼く**。 再生成で振り直るので、
   触る前に必ず1回回してから読む。

## ★「書き手がいるか」を grep で判定するな (2026-09-06 実踏)

`vol_gap.tsv` を「書く script 0本」と記録したが**誤り**だった。 生成器は実在した
(`scripts/_production-diagnostics.py`)。 見つからなかった理由 = **出力名が動的**:

```python
with open(f"{OUT}/{key}.tsv", "w", ...)   # ← リテラルのファイル名がソースに1文字も無い
```

- 帰結: 「grep で書き手0本 → 死んでいる」という推論は**偽陽性を出す**。 逆に、生成器が在っても
  **誰も回していない**なら結果は同じく凍る。 **見るべきは所在ではなく鮮度**。
- 判定は **①mtime(入力より古いか) ②実際に回して差が出るか** の2つで行う。
- 実測(2026-09-06 `docs/production-diagnostics/*.tsv` 193件): 読まれているのに書き手を特定できない 14件 →
  うち3件(`vol_gap` / `pub_unknown` / `solo_nonfirst`)は上の動的生成器が書いていた。 残りは
  過去セッションが手で作った worklist。 **誰も読まない89件は単なる作業ログ**(害は薄い= 消さなくてよい)。

**Why:** 検出器が鳴らない原因は「判定式」だけでなく「入力の鮮度」にもある。 凍った台帳は
**成功したように見えて**取りこぼす(=一番たちが悪い型)。
**How to apply:** worklist を作る時は生成器とセット。 既存の表を使う前に mtime を見る。
関連: [[volgap_leading_gap_and_frozen_input]] [[unlisted_volumes_review_state]]
[[diag_log_prune_before_reading]] [[feedback_sanity_check_tool_warnings]]
[[feedback_raw_count_is_not_worklist]]
