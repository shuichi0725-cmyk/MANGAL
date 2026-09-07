---
name: slug_hiragana_loanword_particle_break
description: 【型・封鎖済】全ひらがな表記の外来語題で「の」を助詞と誤認しslugが砕ける(てくのぱにっくゆにばーす→teku-no-pa-ni-kkuyu-ni-bar-su)。題に漢字が無い時はヨミの助詞分割を使わない
metadata: 
  node_type: memory
  type: project
  originSessionId: f534b513-828c-49d6-9d96-41a3da00cc5a
  modified: 2026-09-07T03:00:45.551Z
---

# 全ひらがな外来語題の slug 破砕 (2026-09-07 封鎖)

`_preorder_draft_lib.make_slug` のヨミ基点是正(2026-08-08新設)は、**漢字題のどこが語境界か**を
「題に見えるひらがな助詞の並び」で復元する仕掛け(日の名残り→ヒ|ノ|ナゴリ→`hi-no-nagori`)。

これを **全ひらがな表記の外来語題** に当てると逆に語を割る:
- 題「てくのぱにっくゆにばーす」/ ヨミ「テクノパニックユニバース」
- 題側の「の」を助詞と見て ヨミを テク|ノ|パニックユニバース に分割 → `teku-no-panikkuyuniba-su`
- 題基点も janome が てく(動詞)|の(助詞)|ぱにっくゆにば|ー|す と割り → `teku-no-pa-ni-kkuyu-ni-bar-su`

★素のヨミをそのまま装置に渡せば janome が長カタカナ連を**1語で保ち**、貪欲辞書変換が効く:
`make_slug("テクノパニックユニバース")` → `techno-panic-universe`。

## 封鎖 = 題に漢字が無い時は助詞分割を使わない

```python
_has_kanji = bool(re.search(r"[一-鿿]", str(base)))
_src = " ".join(...) if (len(_seg) > 1 and _has_kanji) else _k
```
回帰確認済み: 日の名残り→hi-no-nagori / 堕天使ちゃんはがんばれない→datenshichan-wa-ganbarenai / 聖巡→sei-jun。

## 併せて辞書に足した語(本番の綴り慣行を数えてから)

テクノ:techno(techno 1 / tekuno 0)・パニック:panic(38/0)・ユニバース:universe(12/0)・
マッチング:matching(2/0)・ノンストップ:nonstop(1/1=拮抗だが素直な辞書英単語)。
→ ノンストップ・ラブマッチング が `nonsutoppu-love-macchingu` → `nonstop-love-matching` に是正。

**Why:** 装置は「漢字題を直す」前提で作られており、**かな表記の外来語題という第2の入口**が想定外だった。
slug は URL なので後からの rename が高コスト([[slug_rename_kills_slugkeyed_seed]])= 出す前に直す。

**How to apply:** ヨミ基点の再構成を書く時は「その分割の前提(漢字題)」を必ず条件に入れる。
辞書追加は本番索引で綴りを数えてから([[katakana_dict_dead_entry_trap]])。
関連: [[pending_slug_generator]] [[slug_collision_year_rule]]
