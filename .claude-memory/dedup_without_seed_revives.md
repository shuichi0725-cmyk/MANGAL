---
name: dedup-without-seed-revives
description: 【型・恒久機構】重複頁をファイル削除だけで消すとフルpromoteで復活する。正規の受け皿は data/seeds/page-dedup.yml
metadata:
  node_type: memory
  type: project
  originSessionId: 4eb881fe-cc0f-412d-b718-0578babc3249
  modified: 2026-10-20T09:11:07.318Z
---

**2026-09-22 週次 preflight で実踏**: 「aliasのキーが実在の公開slugと衝突(転送が効くと実頁が消える)」2件。
調べると `u12-2018`(=`u12` と9冊ISBN完全一致・同著者 闇川コウ)と
`dokidoki-locomotion`(=`touhou-tetsuwan-komachi-dokidoki-locomotion` と3冊完全一致・同著者 幸田朋弘)の**重複頁が復活**していた。
`slug-aliases.yml` に旧dedup裁定が残っているのに **seed に登録されていなかった**ため、
フルpromoteが種2から素直に再生成した(前週=無 → 今週=在)。

**正規の受け皿 = `data/seeds/page-dedup.yml`**(promote が `_load_page_dedup()` で読み、drop側を出力しない)。
```yaml
- drop: <消す公開slug>
  canonical: <残す公開slug>
  title: <題>
  isbns: <冊数>
  note: <根拠>
```
**ファイルを消すだけの dedup は必ず再発する**。alias だけ張って seed を書かないのも同じ。

**掃引の型(10秒)**: 全 `data/manga.v2/*.yml` の **ISBN集合を frozenset にして畳む**。
集合が完全一致する頁グループ = ほぼ確実に重複。2026-09-22 実測 = 69,465頁中 **8組**。
★同一slug二重ファイル([[duplicate_slug_two_files_blindspot]] 検出器#33)は slug が同じ場合しか見ないので、
**slugが違う重複はこの ISBN集合キーでしか出ない**。

**残務(6組・ユーザ裁定待ち)**:
- `ultra-seven-1978` ⇔ `ultra-seven`(13冊)
- `esu-rank-party-kara-kaikosareta-jugushi` ⇔ `esurankupaateikarakaikosaretajugushi-...`(14冊)
- `esu-kyuu-party-kara-tsuihousareta-kariudo-...` ⇔ `esukyuupaateiikara...-shateiki`(5冊)
- `jigoku-shoujo-enma-ai-selection-geki-kowa-story` ⇔ `...-gekikowa-story`(1冊)
- ~~`tezuka-osamu-scenario-shuu` ⇔ `tezuka-osamu-shinarioshuu`(1冊)~~ → **2026-10-20 解決**: 正= scenario-shuu(予約頁 seed・7/21 全集400冊の別巻386として作った頁)、shinarioshuu を page-dedup に登録+alias
- ★予約頁が片割れの重複(seed=preorder-pages)は page-dedup が効かない(予約合流ブロックは page-dedup を見ない)= **seed ファイルを消す**+alias(2026-10-20 無自覚聖女 tare-nagasu / カジムヌガタイ文庫 / 妖ー深淵の事件簿ー の3頁)。消し忘れると targeted promote の「無ければ補充コピー」で復活する
- ★`god-mazinger`『ゴッドマジンガー』⇔ `majindensetsu`『魔神伝説』(4冊)= **題が違うので単純重複ではない**。
  ISBNの付け違いの疑いがあり要判断([[merge_needs_external_proof]])。

**別件(同題・別作品なので重複ではない)**: 『異世界に来たみたいだけど如何すれば良いのだろう』が2頁
(森ゆきなつ2018/1巻 と 天野こひつじ2022/6巻)。現在はローマ字綴りの違いだけで区別されており、
規則どおりなら従版は「姓+発売年」にすべき([[slug_collision_year_rule]])。

**2026-10-19 追記**: ★drop キーは **SRC ファイルの slug 欄**(promote は slug-override **前**の `src["slug"]` で照合)。公開slug(override 後)で書くと効かない(09-23 の `shounan-graffiti-1989` は SRC slug 欄が `shounangurafutei` で素通り→復活)。登録前に「その slug 欄を持つ源が1件だけか」を確かめる。[[distill_2026_10_1221]]
