---
name: subtitle-orphan-volume-split-sugar-spice
description: "【型・検出器あり】Sugar&Spice型=巻題(副題)を題としてMADBが単独登録→種2で別sidに分裂→本編頁から末尾巻が欠ける。_audit-subtitle-orphan-volume.py(初回 芯1,365巻/809頁)+第2部=override固定頁の続巻取りこぼし25巻。裁定・適用はGO待ち"
metadata: 
  node_type: memory
  type: project
  originSessionId: f8fa63b4-3ce7-45e1-b2ab-f3f4fbab02f4
  modified: 2026-09-03T04:12:38.387Z
---

**型 (2026-09-03 ユーザ発見 sugar-spice)**: 各巻に固有の巻題を持つシリーズ(Sugar & Spice=全巻ジャズ標準曲題)で、MADBが
17/19/20巻を巻題「Somethin' stupid」「Rose & beast」「Over the rainbow」を**題として**別MADB-IDで登録し、
種2のクラスタキー(著者+題)がそれを別sid(number=0/1, is_extra=1)に落とした。本編sid(1-16,18)と結線されず、
頁は「17巻欠け+18巻で終わり」に見えた(完結・全20巻なのに)。是正済= 種4結線(commit bc190f0c6)+4巻の
後刷り日付 2008-05→2006-04-17(楽天+Amazon 2源。笠倉のNDL納本は後刷り混じり)。

**なぜ既存監査が拾えないか**: 孤児sidは単巻・未頁化なので `_audit-solo-truncated.py`(vol1不在の孤立**頁**)の
対象外。巻抜け仮想は 1-16,18 の内側(17)しか見えず、末尾の19/20は「無い」ことが分からない。

**検出器 = `scripts/_audit-subtitle-orphan-volume.py`** (2026-09-03 同日に作成、ユーザ「無駄かもだがやってみて」):
楽天キャッシュ1パス(24秒)で副題/題の「親題+巻番号」を既存頁と照合し、本番に無いISBNを 巻状態×種2×tier×一致×疑 で列挙。
初回= 候補23,957 / **芯(MISSING×A×EXACT×疑なし) 1,365巻・809頁** = ABSENT 1,134(真の取込もれ・双葉社/少年画報社/竹書房の
1990-2000年代が厚い+2020年代324) / **SPLIT 172(69頁=本型)** / SAME_SID 59。
★SPLITの大物: トリニティセブン19-34・六道の悪女たち9-26・ドカベンDT編32-34・Papa told me cocohana ver 6-14・
図書館戦争別冊編6-10・進撃Before the fall 15-17・エンジェルハート2nd 12-16・凍牌ミナゴロシ編3-10(=arc頁の続巻が
親題クラスタに登録される型が多い)。
★偽陽性の型(疑フラグ): SEQTITLE(リング2/トイ・ストーリー2=続編題 vs ふしぎトーボくん 5=番号入り巻題、機械で割れない) /
LABEL(本宮ひろ志傑作集7=叢書番号) / YEARLIKE('04・05) / EDITION・SPINOFF / DROPIMPRINT(My first big等=出ないのが正) /
PUBMISMATCH(別社=別版か移籍)。CLAUDE.md 月次サニティに登録済。

**第2部(楽天非依存)= edition-overrides固定頁の続巻取りこぼし**: overridesは巻リストを固定するので連載中の頁は
種2に続巻が来ても永久に出ない(canonicalの検査7に当たる番人がoverrides側に無かった)。初回25巻/10頁、うち現役=
フェルマーの料理8巻(2026-06)/聖女に嘘は通じない6巻/最弱な僕は壁抜けバグで成り上がる12巻(2026-07)。
出力 `docs/production-diagnostics/overrides-frozen-tail.tsv`。

**SAME_SIDの内訳(59)**: ①number=0規則で隠れた**真の0巻**(ドラえもん0巻/ハヤテ0/地縛少年花子くん0/ケンガンアシュラ0…
=表示方針の裁定マター) ②page-dedup残骸(Bird 3-8/ホヒンダ村だより1-7/Ψchic academy10-11) ③override固定(上記)
④MADB誤番号(C級さらりーまん講座12,13が number=1 extra=1)。

**次の一手(GO待ち)**: SPLIT 69頁は種4結線(or merge)を1頁ずつ裏取り(種2側に著者・出版社・日付が既にある=証拠は揃いやすい)。
ABSENTは既存 `_register-seed4-ndl.py` ゲート(種2既存ISBN→pending/series_key bind/番号既存skip)に流すのが安全。
第2部の現役3頁は override に巻を追記 or override解除で即直る。
[[volume_split_merge]] [[series_fragmentation_rootcause]] [[feedback_one_bug_means_a_class]] [[harvest_match_mechanism_applied]]
