---
name: promote_post_stage_overwrites_canonical
description: 【型・是正済】editions-supplement の replace:true が promote後段(edisup)で canonical を丸ごと上書き。targeted反映では再現せず月次だけ巻が消える
metadata: 
  node_type: memory
  type: project
  originSessionId: 3819afb2-c9d0-4149-93f3-a0615b0c157d
  modified: 2026-09-21T02:22:53.969Z
---

2026-09-21 月次1.2.20 の ISBN消失監視で発覚（w3=手塚治虫『ワンダースリー』で9冊消失）。

## 何が起きるか

`_promote-bulk-v2.py` は **promote 内で** `edition-canonical/<SRC slug>.yml` を適用して版タブを組む。
その**後段**に `intake.py` の durability stage があり、`edisup` = `_apply-editions-supplement.py` が
`data/seeds/editions-supplement.yml` の `replace: true` エントリで **editions を丸ごと差し替える**。

→ canonical（新しい・ISBN完備）で組んだ9版が、supplement（古い手書き・ISBN null混じり）の3版に**上書き**され、
巻が黙って消える。**巻抜けにも見えない**（版ごと消えるため）。

## ★なぜ長く気づかれなかったか

- **targeted反映（`_reflect-targeted.py` → `promote --only`）は後段を走らせない** = per-case 修正直後は正しく見える。
- 壊れるのは **intake（月次のフルpromote）を通った時だけ**。つまり「直した直後は正しく、翌月の蒸留で戻る」。

## 掃引と対処

- 両方を持つ頁は **`urusei-yatsura` と `w3` の2つだけ**（2026-09-21 実測）。うる星は supplement が正本なので温存。
- w3 は supplement 側を退役（canonical が正本）。`_apply-editions-supplement.py` 再実行後も9版が残ることを確認済み。
- 新しく canonical を起こす時は **同名 slug が editions-supplement に居ないか**を必ず見る（works は7件しかないので grep 一発）。

**Why:** 同じ頁を2つの seed が別レイヤで支配していると、**どちらが後に走るか**だけで結果が変わる。
**How to apply:** 版の正本は1つに決める。canonical を使うなら supplement の同 slug を消す。
関連: [[edition_canonical_mechanism]] [[edition_typemerge_hides_volumes]] [[seed_silently_ineffective_class]]
