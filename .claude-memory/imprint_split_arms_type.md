---
name: imprint_split_arms_type
description: 【型】ARMS型=レーベル表記ゆれで同一runが版タブに分裂。真因はMADBの表記ゆれ+種2のクラスタ分裂で、2026-08-17のギャラ型一括是正がそれをcanonicalへ焼き込んだ。14件中9件統合済/1件は正当/3件は別問題
metadata: 
  node_type: memory
  type: project
  originSessionId: 79cc8af0-e2f8-4bd2-b6af-b897f077da5c
  modified: 2026-08-28T04:44:03.579Z
---

2026-08-28 ユーザ発見(「ARMSの21巻が同じ箇所に分裂してる」)から型化した。

## 症状と真因
版タブに**同一レーベルが2つ以上**並び、片方が数巻だけ持つ。主版はその巻が**巻抜け**になる(=巻抜け仮想にも出る)。
- 表面の原因 = MADBのレーベル表記ゆれ。**中黒の有無 / 小書きカナ(ッ↔ツ, ィ↔イ) / 英字とカナ / スペース**。
  ARMS = 「少年サンデーコミ**ツ**クススペシャル」(正: コミ**ッ**クス)で21巻だけ別edition行。
- ★**真因はそれだけではない**。調べると多くは **種2のクラスタ分裂**([[series_fragmentation_rootcause]])だった:
  - MADBの一部の巻にだけ付く **「[編]白泉社」** の編集クレジットでクラスタキー(著者+題)が変わり、同一runが2 seriesに割れる
    (1・2のアッホ / かくれんぼキッス / すすめ!!パイレーツ で実証)。
  - 原作者と作画者で別QIDに割れる(ホールインワン=金井たつお側とハード＆ルーズ=かわぐちかいじ/狩撫麻礼側)。
  - ★**生のbrand値はタブの割れ方と逆にクロスしていることがある**(1・2のアッホ)。「中黒の有無で割れた」と決めつけない。
- ★そして **2026-08-17の「ギャラ型是正」一括処理が、種2のedition区切りをそのまま `edition-canonical` へ焼き込んだ**。
  だから直す場所は種2ではなく **`data/seeds/edition-canonical/<SRC slug>.yml`**。

## 検出器
`scripts/_audit-canonical-imprint-split.py` (月次サニティ監査に登録済)。
imprintを正規化(小書きカナ→大書き/中黒・空白除去)して一致する版が同一頁に2つ以上あれば flag。
★**巻番号が相補=統合候補 / 重複=別run濃厚** が一次シグナル。出力=`docs/production-diagnostics/canonical-imprint-split.tsv`。

## 裏取りの手順(この順で安い→高い)
1. ★**楽天キャッシュを1パス走査**して全ISBNの `seriesName`/`publisherName`/`salesDate` を一括取得。
   `.cache/rakuten-isbn.jsonl` + `-delta.jsonl` を**正規表現の一括alternationで1回だけ舐める**(212 ISBNが8秒。ISBN毎に走査すると死ぬ)。
   ★live照会はほぼ不要だった(211/212がキャッシュ命中)。
2. ISBNが無い巻(1970-80年代)は楽天に無い。**MADB raw(`.cache/madb/metadata101.json` / `metadata104.json`)の
   シリーズ容器ID `schema:isPartOf`(C数字)** が最強の一次証拠。同一容器なら同一run。
3. Wikipedia/出版社公式の刊行リストで巻数と刊行年を突合。
4. NDL JPNOの連番も効く。★NDLは1.2s/req、**並列禁止**。

## 裁定結果 (14件)
- **統合済9件**: 1-2-no-ahho / elite-kyousoukyoku / hard-ando-ruuzu / hole-in-one /
  hyakuoku-no-hiru-to-senoku-no-yoru / kakurenbo-kiss / shin-piihyoro-ikka / spider-man / susume-pirates
  (+ arms)。★**既存の巻を版間で移すだけ。ISBN/日付の新規追加はしない**。二重登録の巻だけ捨てた(3件)。
- **正当に別版=触るな1件**: torajima-no-mii-me(1978初版 vs **2025復刻版**)。統合すると初版が消える。
- **別問題3件(版分裂ではない)**: desire-2nd-season(本編25巻と続編7巻が1頁) / ou-sama-no-shitateya(4部構成が1頁) /
  hime-2006(同名異作3作の過統合。★統合すると8年の日付逆行=ギャラ型を新造する)。

## 作業上の注意
- ★reflectの**損失ガードが必ず鳴る**(版数が減るため)。巻の総数が減っていないことを確認してから `--allow-loss`。
- ★`edition-canonical` のキーは **SRC slug**(= data/manga のファイル名)。overridesの公開slugとは逆([[edition_canonical_key_is_src_slug]])。
- 適用後は `_check-edition-canonical.py --slugs ...` で異常0を確認してから反映。

関連: [[edition_canonical_mechanism]] [[merge_needs_external_proof]] [[never_delete_because_broken]] [[feedback_one_bug_means_a_class]]
