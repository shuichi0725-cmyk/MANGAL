---
name: synopsis_short_requeue_done
description: "【✅完了】短キャッチ/短あらすじ requeue キューは素材あり分を全消化。残2,413は素材ゼロで書き直さない"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e629c9e-d55a-4074-a6ec-d0691965d657
  modified: 2026-07-31T04:26:48.929Z
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

## 次の層(未着手・要方針)
`python scripts/_enrich-captions.py --missing --src data/manga.v2` 実測(2026-07-31): **欠け33,850頁 / 材料あり4,509 / うち2巻以上439**。
★ただし材料の質が低い(後半巻のみ・宣伝文だけ・参考書や画集が混じる)ため、**一律生成は不可**。
切り出し道具は `scripts/_enrichgap-prep.py` / `_enrichgap-done.py` を新設済(MINVOL/MAXVOL env)。

関連: [[catch_synopsis_enrich_pending]] [[enrich_7k_resume_state]] [[ai_genre_closed_vocabulary]]
