---
name: half_volume_number_mechanism
description: 「.5 の半端巻」(番外編)を通す機構=番人4か所を同じ規則で揃える。★lib/schema.ts の int() が最も危険(頁ごとビルドskip=404)。カードの全N巻からは除外
metadata:
  node_type: memory
  type: project
---

番外編の **「15.5 巻」** を本編頁の正しい位置に出すための機構(2026-09-06 新設)。
初例= トリニティセブン『七人の魔道士と日常風景 15.5』(9784040721446)。
NDL の `dcndl:volume` が **"15.5"**、楽天題も末尾15.5、本編15巻(2016-08)と16巻(2017-02)の間の2017-01刊。
種2では別クラスタに `number=15` で入っており本編15巻と衝突して永久に出ていなかった。

## ★規則 = 「非負整数 か .5」。 .5以外の小数(15.3)と負数は誤記として弾く

promote 本体は小数をそのまま運び、sort は `int()` で潰すので **15 と 16 の間に着く**(実測)。
止めていたのは番人side。 ★**4か所を必ず揃える**([[build_input_wiring_three_places]] の同型):

| 場所 | 役割 | 直さないとどうなるか |
|---|---|---|
| `scripts/_check-seeds.py` | 種4 seed lint | seed lint FAIL で反映が止まる |
| `scripts/_reflect-targeted.py` | 反映の検証ゲート | 「不正number」で push 前に停止 |
| ★`lib/schema.ts`(Zod `VolumeSchema`) | ビルド時検証 | ★**その頁が丸ごとビルドskip=404**([[search_404_build_skip_validation]] の型) |
| `scripts/_build-list-index.py` `_card_vol_count()` | カードの「全N巻」 | 34巻の作品が **「全35巻」** と出て事実と食い違う |

- 回帰テスト = `lib/volumeHalfNumber.test.ts`(整数/.5 は通り、15.3・0.25・負数は弾く)。
- `total_volumes` は生の合計なので小数巻も数える(非表示なので放置)。`max_edition_volumes` だけ除外。
- 種4(`volumes-supplement.yml`)に `number: 15.5` で書けばよい。
  ★ただし **種4の `title_display` は出力に載らない**(`load_volumes_supplement` の vol_dict に無く、
  qid照合の名寄せにしか使われない)。 大半の既存entryは title_display に**シリーズ題**を入れているので、
  安易に結線すると全補完巻にシリーズ名が表示されてノイズになる = **結線しないのが正**。

## 限定版(BD付き等)の付け方 = 別の経路

同巻の別装丁は **`special-edition-fix-*.yml` の `_special_by_normal` 経路**(落語心中/ろこどる型)。
`normal_isbn`(頁に在る通常版)+ `variant{label,isbn13,cover_url,price}` を書けば通常版巻に併記される。
★`edition-overrides` は使わない= **巻を固定するので連載中の頁が凍る**([[subtitle_orphan_volume_split_sugar_spice]]
の overrides-frozen-tail)。 トリニティセブン本編は status=ongoing。
実例= 11巻ブルーレイ付き限定版 9784040703503(種2に不在・NDLヒット0・楽天のみで実在確認)。

**Why:** 番外編は実在するのに機構が int しか受けず、しかも Zod だけは失敗が「頁が消える」形で出る(silent)。
**How to apply:** .5巻を足す時は4か所が揃っているか確認。 増やすのは種4に1 entry 書くだけ。
関連: [[orphan_series_promote_is_srcpage_driven]] [[wikipedia_bibliography_crosscheck]] [[seed_yaml_colon_quoting]]
