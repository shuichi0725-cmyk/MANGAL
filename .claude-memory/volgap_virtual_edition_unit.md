---
name: volgap_virtual_edition_unit
description: 【是正済】_volgap-virtual.py のgap判定はtype単位で複数版を合算していた。索引(vol_gap)と同じ版(edition)単位に揃えた
metadata:
  type: project
---

2026-09-07 是正。 `scripts/_volgap-virtual.py`(トリガー語「巻抜け仮想」)の残gap判定が、
索引 `scripts/_build-list-index.py` の `vol_gap` と**別の定義**だった。

- 索引 = `for _e in eds:` = **版(edition)ごと**に min..max の穴を見る
- 旧 virtual = `by[type].add(n)` = **type単位で複数版を合算**

## 何が起きるか
- **過大**: 子連れ狼の `other` は『漫画アクション・コミックス(1971)』[2,3] と
  『劇画キングシリーズ版』[1,9,10,28] の2版。 合算すると 4..8 が欠けて見える(実際は別版)
- **過少**: 同type別版が穴を埋めてしまい、本当の欠番が消える頁がある

## 直し方(実装済)
- `_edvols(eds)` = 巻を **(type, 版index)** キーで持つ(`versions` は同一版なので合算)
- `_seedkey()` = 種4/merge partner の巻は promote と同じ **その型の最初の版**に付ける
  (promote は `by_type[target_type]` の `ed_group[0]` に append する)
- 残gap表の版表記を `standard#0` 形式に(どの版の穴かが読める)

## 数字の読み替え
2026-09-07 実測 = 候補446頁 / 適用前444 → **適用後430**。 旧merge模型では408。
充填前の同日は 504候補 / 適用前482 → 適用後468(旧模型)。

[[volgap_virtual_false_positives]] [[volgap_virtual_tool_trigger]] [[volgap_fill_pipeline_2026_09]]
