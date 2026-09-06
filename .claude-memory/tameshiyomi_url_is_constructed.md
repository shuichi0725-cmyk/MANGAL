---
name: tameshiyomi-url-is-constructed
description: "【裁定・恒久】試し読みURLは title_id+巻番号 から**組み立てる**もの。BookLiveへのHEAD検証は不要=退役。末尾は本番の巻数まで構築で伸ばす(2,528作品/5,448巻を復活)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fa3eed2c-bf86-4ffe-b701-6b416a249bdb
  modified: 2026-09-06T08:19:22.579Z
---

★**ユーザ裁定(2026-09-06)「BookLive!は憶測でかけるはず。試す必要なし。それを確認してたなら過剰」**。
発見の入口= 「試し読みが8巻ある漫画で7までしかない」(幼なじみが絶対に負けないラブコメ)。

## 確認した事実(この3点が結論の根拠)
1. **URLは保存していない**。client が `https://booklive.jp/bviewer/s/?cid=<title_id>_<巻番号3桁>` を
   組み立てる(`components/VolumeCoverflow`)。**リンクを作るのに検証は要らない**。
   HEAD検証は「ボタンをどこまで出すか」を決めるためだけだった。
2. その検証が **2026-08-29の278万リクエスト規制事故** の原因だった([[booklive_access_incident]])。
3. ★**規制中は正解の巻すら403**(802251_007=既に出ている巻 / _008 / _099 が全部403。3件で実測)。
   → 叩いても存在の有無を判別できない=**検証という行為自体が成立しない**。

## いまの方式
- `_gen-tameshiyomi-map.py` が **末尾を本番頁の巻数まで構築で延長**する(2,528作品 / 5,448巻)。
  健全時に実測した「範囲内の穴」(missing 17作品)だけは残す。
  実例= 幼なじみ 7→8 / 名探偵コナン 14→109 / ブラック・ジャック 1→25 / ダンダダン 1→25。
- 監査= `scripts/_audit-tameshiyomi-gap.py`(**外部を一切叩かない**。出力 tameshiyomi-tail-gap.tsv)。
- ★**BookLiveへのクロールはもう要らない**= アイドル運転の試し読みexpand柱は退役
  ([[tameshiyomi_recheck_idle_loop]])。停止札はそのままでよい。

## 取りこぼしの真因(記録)
2026-08-29の事故当日に `expand-swept.jsonl` の **33,080作品へ「掃引済み」マーカーが書かれた**
(29,313作品で n==seedの最大巻=live確認ではなくseedの値)。さらに取りこぼし5,448巻のうち
**4,615巻が vol-checked.jsonl に「検査済み」**として残り、再走しても永久skipされる状態だった。
→ 構築方式に変えたので、この汚染ごと無効化された。

**Why:** 外部サイトを叩く前に「そもそも叩く必要があるか」を問う。URLが**構築可能**なら取得は要らない。
**How to apply:** 外部リンクを扱う機能では「保存するのか組み立てるのか」を先に確認する。
組み立てなら検証はUI判断のためだけ=コストに見合うか毎回問い直す。[[feedback_efficiency_first]]
