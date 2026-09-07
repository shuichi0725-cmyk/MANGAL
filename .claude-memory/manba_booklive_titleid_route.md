---
name: manba_booklive_titleid_route
description: 【機構・進行中】manba.co.jpの302 LocationからBookLive title_idを採取する経路(BookLiveは1回も叩かない)。トリガー「マンバ蒸留して」。誤同定0%実測・台帳data/seeds/manba-titleid.jsonl
metadata: 
  node_type: memory
  type: project
  originSessionId: f534b513-828c-49d6-9d96-41a3da00cc5a
  modified: 2026-09-07T05:07:53.472Z
---

# マンバ蒸留 = 停止札を守ったまま試し読みを増やす経路 (2026-09-07 確立)

**トリガー語「マンバ蒸留して」/「マンバ蒸留続けて」= skill `manba-distill`**(正本はskill。ここは指し先と進行状態)。

## 何が分かったか

- manba.co.jp の作品ページは各ストアへの**自サイト内リンク** `/boards/<id>/stores/booklive` を持ち、
  その **302 Location**(valuecommerceアフィ)の `vc_url` に
  `https://booklive.jp/product/index/title_id/<ID>/vol_no/001` が入っている。
- ★**Locationヘッダを読むだけでリダイレクトを追わない**ので **booklive.jp には1リクエストも出ない**
  = 停止札([[booklive_access_incident]])を守ったまま title_id が採れる。
  そして我々はURLを保存せず title_id+巻番号3桁 から**構築**する([[tameshiyomi_url_is_constructed]])ので、
  **必要なのは title_id だけ**= BookLiveを叩く理由が元々ない。
- 取得は2リクエスト/作品(`/search?q=<題>` でboard特定 → `/boards/<id>/stores/booklive`)。
  検索結果はサーバ描画で board id / 題 / **著者** / 「N巻まで刊行」が取れる = 同定材料が揃う。
- ★**TinyFish(魚)では取れない**。無料Fetchは本文抽出のみで `href` を落とし、302も読めない。素のHTTPの仕事。

## 精度(実測・これが採用根拠)

★**答え合わせ20件**(既に title_id を持つ作品に同じ採取をかけ既知値と照合)= hit 16 で **16/16 完全一致・誤同定 0%**。
未検査53件では hit 38 / 版違い疑い2 / 同定不能4 / 一致なし6 / ゲート不通過2 / 取扱なし1。

## 踏んだ罠(ゲートに焼き済み)

1. **題一致+巻番号だけでは原作ラノベ/外伝を掴む** → 著者overlapを主ゲートに(T1)。
2. **manbaは正式題を使う**(我々「とある科学の超電磁砲」/ manba「とある魔術の禁書目録外伝　とある科学の超電磁砲」)
   → 包含一致(T2)を足すが、緩いので **著者and巻数の両方**を要求する。
3. ★**manbaは版/形態ごとに別boardを立てる**(【単行本版】【合冊版】【完全版】【特装版】＜無修正ver.＞…)。
   包含一致はこの版表記を吸収してしまい**別商品のtitle_id**を掴む(終の退魔師/結婚商売で実踏)
   → `_EDITION` ガードで `hit_edition_suspect` に降格=適用しない。答え合わせ16件は誤降格0。
4. 同定不能の主因も同じ = manba側の**重複board**(薬屋のひとりごと 80647=16巻 / 250285=17巻・著者同一)。
   巻数で寄せれば選べるが別コミカライズの可能性が消せないので機械採用しない。

## 進行状態 (2026-09-07 時点)

- 台帳 = **`data/seeds/manba-titleid.jsonl`(git追跡・追記のみ・同一slugは最終行勝ち)**。
  ★`.cache` から移設済み(/clear・PC移行で消えるため)。
- 記録済み74作品 / うち `result:"hit"` 55(= 適用可。ただし16件は答え合わせ用で既にマップに在る)。
- 対象リスト = `docs/production-diagnostics/no-tameshiyomi-active.tsv`(535件)。**未採取 482件・約80分**。
- ★**`data/tameshiyomi-map.json` へはまだ1件も反映していない**(GO待ち)。反映は本番頁の表示を変える。

**Why:** 規制事故以降、試し読みの新規取得手段が絶えていた。これは相手を叩かずに増やせる唯一の経路。
**How to apply:** 再開は `python scripts/_manba-booklive-titleid.py --from-list --all --status` から。
外部リンクを扱う時は「保存するのか組み立てるのか」を先に問う= 構築なら取得は要らない。
関連: [[feedback_no_negative_record_on_failure]] [[tameshiyomi_adjudication_state]] [[manba_design_learnings]]
