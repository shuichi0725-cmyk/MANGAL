---
name: r2_storage_gzip_declined
description: 【裁定・何もしない】R2容量9.65GB(無料枠10GB直下)。gzip保存で1.9GBにできるがCFが既にbrotliで配っている=素のgzip保存は転送+24%。超過も月$0.03で動機なし
metadata:
  type: project
---

2026-09-17。ユーザ「容量が10GB近くになってきた。小さくできないか?」→ 実測して選択肢を出し、
**ユーザ裁定 = 何もしない**。以後、同じ提案を蒸し返さないための正本。

## 実測(2026-09-17)

- R2 `mangal-site` = **9.65 GB / 183,745 オブジェクト**(boto3 の list_objects_v2 全走査)。
  `.html` 91,632 = 6.60GB / `.txt`(RSC) 91,633 = 2.99GB / 残り 0.06GB。
  前置き別 = `manga/` 7.71GB(139,432obj) / `author/` 1.10GB(40,406obj) / 他 0.84GB。
- ★**床(全頁共通シェル)が約3.9GB = 全体の40%**。中身ゼロの `contact.html` で 29.7KB
  (内訳: RSC インライン 14.9KB + 素マークアップ 11.3KB)、`contact.txt` で 14.5KB。
  [[shell_props_serialized_to_all_routes]] の masters 是正後もこの床は残っている。
- **ローカルは圧迫ゼロ**。C: 空き816GB / D: 空き16.7TB。リポジトリ計59GB
  (`.cache` 37GB / `.next` 10.5GB / `out` 9.4GB / `data` 1.3GB / `.git` 735MB)。
  → 「10GB」はローカルでなく**R2のこと**、が毎回の読み替え。

## なぜやらないか(決定打 = 本番の実測)

`curl -H "Accept-Encoding: ..." https://mangal-db.com/manga/one-piece`(素 352,341B):

| Accept-Encoding | 実転送 |
|---|---|
| `br, gzip` | **31,317 B** ← 今これ |
| `gzip` | 38,956 B |
| 無し | 352,341 B |

★**R2 には素のバイトが在り、CF のエッジが brotli で圧縮して配っている**。
gzip を自前で付けて `Content-Encoding: gzip` で返すと **CF は再圧縮しない** = 全訪問者が恒久的に **+24%**。
サンプル150頁の実測比も同傾向(gzip6 19.1% / br q5 16.4% / br q11 14.7%)。
brotli 保存で逃げる道は塞がっている = Workers の `DecompressionStream` は **gzip/deflate のみ、br を戻せない**。

**費用も動機にならない**: R2 ストレージ超過は $0.015/GB・月。12GB でも **月 $0.03**。
(Class A オペの話とは別軸 → [[r2_class_a_budget_arithmetic]]。容量を減らしてもオペ数は減らない)

## もし将来やるなら(案は検証済み、実装はしていない)

★**①' = R2 には gzip で置き、worker は必ず `DecompressionStream("gzip")` で展開して identity を返す。
圧縮は今まで通り CF エッジの brotli に任せる。** → 容量 9.65→約1.9GB・転送は不変・
worker が常に identity を返すのでエッジキャッシュの符号化取り違え(`Vary`/cacheKey 分割)事故も消える。
最初の関門 = `wrangler dev` で `DecompressionStream("gzip")` が実機で通ることの実演。

それでも残る弊害4つ:
1. ★**書き手が4本**: `_r2-sync.py` / `_deploy-differential.py` / `_deploy-feature.py` / `_r2-upload.mjs`。
   1本でも素のまま PUT すると**その経路で出した頁だけ本番で壊れる**。
   → worker を「オブジェクトの `ContentEncoding` を見て分岐」にすれば混在が安全=経路ごとに刻める(必須設計)。
2. `_r2-sync.py` の **manifest 欠損時の ETag 実物照合**(2026-07-17 の破損で実際に使った復旧経路)が
   「全件別物」と誤判定してフル PUT に化ける。通常の差分判定(ローカル sha256 vs manifest)は無傷。
3. `workers/r2-serve.js` の **404 経路**(`nf.body` を直に返す分岐)が符号化処理を素通りする。
4. 一回きりの**全件再アップ = 183k Class A**。当期(8/27〆)は既に 730,113/100万だったので期リセット後。

※ Range 要求は現状 worker が未対応(`BUCKET.get(key)` に range を渡していない)ので劣化にならない。

## 却下済みの別案

- **`.txt`(RSC)を出さない** = −2.99GB。クライアント遷移が全頁再読込に落ちる。2026-09-09 に既に「推さない」裁定済み。
- **孤児オブジェクト prune** = R2 91,632 html 対 ローカル 91,267 で差 365頁ぶん ≈ 40MB。誤差。
  → [[r2_orphan_pages_prune_missing]]

[[hosting_worker_r2_architecture]]
