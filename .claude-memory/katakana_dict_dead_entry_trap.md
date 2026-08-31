---
name: katakana-dict-dead-entry-trap
description: katakana-english.ymlへの機械追記がmappings外(インデント無し)に落ちるとlint通過のままsilentに死ぬ
metadata: 
  node_type: memory
  type: project
  originSessionId: 59d8d8ff-b25f-483a-a575-3e5765b36905
  modified: 2026-08-31T06:21:50.603Z
---

`data/seeds/katakana-english.yml` は `mappings:` 配下の2スペースインデントが実体。
**インデント無しで末尾追記するとYAMLとしては合法**(トップレベルの兄弟キー)なので
seed lintは通るが、ローダーは `mappings` しか読まず**エントリはsilentに無効**になる。

2026-08-31 実踏: 過去の追記事故で5行(アイラブユー/キューブリック/デスレス/フェリーニ/ブライド)が
mappings外で死んでいたのを発掘・mappings内へ取り込み修復(全体をソート済み形に正規化)。

**How to apply:** 辞書へ機械追記する時は必ず2スペースインデントでmappings内に挿入し、
直後に `yaml.safe_load` で `len(d['mappings'])` が増えたことを確認する。
[[seed_yaml_colon_quoting]] と同族の「seed機械追記のsilent無効」型。
