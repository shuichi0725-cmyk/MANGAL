---
name: series_merge_last_entry_wins
description: 【罠】series-merge.yml は sid_to_group[sid]=sids の後勝ち。同じシリーズに別entryを足すと先の結線が消える(悪役令嬢で4巻が落ちた)
metadata:
  node_type: memory
  type: project
---

`_promote-bulk-v2.py: load_merge_sids()` は
`for sid in sids: sid_to_group[sid] = sids` = **代入**なので、
同じ sid を含む entry が複数あると **ファイルの後ろに在る entry が勝ち、先の結線は消える**
(auto JSON を先に読み → 手書き YAML で上書き、という設計の副作用)。

## 実害(2026-09-06 悪役令嬢後宮物語～王国激動編～)
このシリーズは種2で **3 sid に分裂**していた:
- sid=154485 `name:涼風|name:悪役令嬢後宮物語王国激動編`(波線なし) = 1,2,3 巻 ← 頁の _skey
- sid=154486 `name:涼風|name:悪役令嬢後宮物語～王国激動編～`(波線あり) = 6,7 巻
- sid=154487 `name:鈴ノ助|name:悪役令嬢後宮物語～王国激動編～` = **4 巻だけ creator が鈴ノ助(イラスト)**

6,7巻を出すために 154485+154486 の entry を**新規追加**したところ、
既存 entry(154485+154487)の結線が上書きされ **4巻が頁から落ちた**。
→ promote の **消滅ISBNゲートが 9784866577647 を検出**して発覚(番人が効いた)。

## ★正しい手順
1. `grep -n "<作品名>" data/seeds/series-merge.yml` で **既存 entry を先に探す**。
2. 在れば **その entry に不足キーを足す**。 別entryを新設しない。
3. 種2の分裂を全部洗う: `SELECT id,series_key,title FROM series WHERE title LIKE '%題%'`
   → 巻を持つ sid を全部 merge_keys に入れる(1つでも漏らすとその巻が落ちる)。
4. 反映後に **巻が減っていないか**を必ず確認(`減少なし` 行 + 消滅ISBN行)。
5. ★同題の**別作品**は入れない(悪役令嬢では sid=154484「悪役令嬢後宮物語」1,2巻 = 本編で別作品)。

## 分裂の作られ方(3型が同居していた)
題の**波線 ～ の有無** / **著者の振り分け差異**(原作 vs イラスト) / 表記ゆれ。
[[series_fragmentation_rootcause]] のクラスタキー = 「単一著者+生title」なので、
どちらか一方でも揺れると別 sid になる。

**Why:** merge は「足す」つもりで書くが機構は「置き換え」。 番人が無ければ静かに巻が消える。
**How to apply:** merge を書く前に既存entryを grep。 書いた後に巻数の減少を確認。
関連: [[volume_split_merge]] [[merge_needs_external_proof]] [[volgap_leading_gap_and_frozen_input]]
