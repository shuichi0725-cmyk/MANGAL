---
name: synopsis_short_requeue_done
description: "【✅完了】短キャッチ/短あらすじ requeue キューは素材あり分を全消化。残2,413は素材ゼロで書き直さない"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e629c9e-d55a-4074-a6ec-d0691965d657
  modified: 2026-07-31T06:28:42.064Z
---

skill `enrich-catch-synopsis` の**再生成キュー2本は 2026-07-31 に消化完了**。

## 到達点
- `docs/production-diagnostics/catch-short-requeue.txt` = **0件**(消化済)。
- `docs/production-diagnostics/synopsis-short-requeue.tsv` = **2,413件残**だが**全て `has_caption=no`**。
  内訳 mild×no 1,203 / severe×no 1,210。★**素材ゼロなので書き直さない**(skill方針=短くても捏造よりまし)。
  = このTSVは今後も減らない。「残件数」だけ見て未完了と誤認しないこと。
- severe×caption有 / mild×caption有 とも **0**。

## 使った道具(再利用可)
- `TIER=mild|severe CAPLEN=95 python scripts/_synrq-prep.py <SN> 40` → 材料batch + digest。
  ★`TIER` env は今回追加。既定 severe。
- `python scripts/_apply-enrich-batch.py <SN> --requeue [--apply]` → 上書き許可で適用。
- `python scripts/_synrqdone.py <SN>` → TSVから消し込み。
- 反映は毎スライス `_reflect-targeted.py --only $(cat .cache/enrich_changed_slugs.txt) --push`。

## 詰まった型(次も出る)
1. **材料未staged**: prep が「材料在庫0」を出したら、`_enrich-captions.py --slugs <csv> --src data/manga.v2 [--live]`
   で回収 → `{'kind':'full','items':[...]}` 形式で `.cache/enrich-batches/batch-<N>.json` を手で作る。
2. ★**ファイル名≠内部slug**(slug-override頁)。`_enrich-captions.py` は**内部 `slug` で照合**するので
   TSVのslug(=ファイル名)では拾えない。内部slugで取得→**itemの `slug` をTSV側の名前に書き換えて**batch化する。
   実例: `hipunoshisumaiku`(内部 `hypnosis-mic`) / `otsukiaishimasenka`(内部 `otsukiai-shimasen-ka`)。
3. **反映ゲートが別の穴で止まる**: 今回 `sukeban-deka-if` の `title_kana` 空で push 停止(ゲートは正しく機能)。
   → `data/seeds/furigana-corrections.yml` に `key: "qid:...|name:..."` で追記して是正。key/titleは `:` を含むので必ずquote([[seed_yaml_colon_quoting]])。

## 空欄補完層(①)も 2026-07-31 に一区切り ✅

`_enrich-captions.py --missing` 実測: **欠け33,850頁 / 材料あり4,509**。内訳=
2巻以上で1〜2巻に60字以上の紹介文 **173** / 2巻以上だが後半巻のみ188 / 1巻のみ3,564 / 短文584。

★**173(フル対象)は完走**(batch-9101〜9106)。**キャッチ149本・あらすじ129本**を付与。
**24件は書かずに見送り**= 非漫画15(画集4/資料集・ムック・フィルムブック5/実用ガイド2/目録1/カタログ1/図誌1/評伝1)
+ premise無し9(「廉価版です」「第2巻です」「話タイトル羅列」だけ)。
→ ★**画集4件(江口寿史の世界/KING OF POP/Fullmetal alchemist(荒川弘画集)/しゅごキャラillustrations)は
  [[art_book_inclusion]] の別カテゴリ運用へ回す候補**。drop はユーザ裁定マター。

★**1巻のみ3,564件は「ジャンル付与が必要」ではない**(genres 空はわずか88件)。私は一度これを
「3,564件のジャンル付与が残っている」と誤って件数化した。skillの「1巻のみ→ジャンルのみ」は
*書いてよい範囲*の規定であって*残件数*ではない。
ジャンル軸の実際の残務は付与ではなく**provisional 25,789頁の底上げ**(楽天由来へ格上げ済は7,440頁)。

道具: `scripts/_enrichgap-prep.py` / `_enrichgap-done.py`(MINVOL/MAXVOL/**EARLYMIN** env)。
`EARLYMIN=60` で「1〜2巻に60字以上」だけに絞れる=skillの「文面は1〜2巻の範囲」規律を満たす頁だけ取れる。
★内部slug≠本番ファイル名(override 1,035頁)で NOFILE 弾かれ+消し込み不発が起きたので
`.cache/slug-file-map.json` を作って prep に結線済。

## ★字数調整を機械化するな(2026-07-31 実踏)

catch 48-74字に足りない時、末尾を規則で伸ばす処理を書いたら
「〜のだろうかなのであると言えるだろう」等の壊れた日本語を量産した(本番投入前に破棄)。
★**私の日本語の字数感覚は実測より5〜8字短い**。書く前に必ず `len()` で測る helper を回し、
足りない分は**手で書き直す**。機械的な末尾付与は禁止。

関連: [[catch_synopsis_enrich_pending]] [[enrich_7k_resume_state]] [[ai_genre_closed_vocabulary]]
