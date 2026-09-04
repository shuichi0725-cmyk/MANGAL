---
name: indexnow-self-submit
description: IndexNow 自前送信(2026-09-04 ユーザ裁定)=scripts/_indexnow.py。r2-sync→pending→finalize(purge後)drain / feature・diff-deploy は即drain。鍵=public/efa08…txt。★未修正の欠陥3件あり(無変更66k頁の大量送信ほか)・鍵は本番未配信で未送信
metadata: 
  node_type: memory
  type: project
  originSessionId: b13171da-074b-4da8-a8b5-905f74606a97
  modified: 2026-09-04T11:06:29.333Z
---

ユーザ裁定(2026-09-04): 「IndexNow を自前で直接叩く。鍵ファイルを `https://mangal-db.com/<key>.txt` に設置し、
デプロイスクリプトが実際に変更されたURLを IndexNow API へ POST する」。
動機= Cloudflare Crawler Hints が **Worker+R2 配信では発火しない公算が高い**([[crawler_hints_ineffective_on_workers_r2]] に一次情報)。

## 実体(Fable 5.1 が実装・commit dbed07ec3)

- ヘルパー `scripts/_indexnow.py`(鍵発見・キー→URL写像・pending・送信・記録)。
- 鍵 = `public/efa08a89a5e7a14dc0bde143738fae20.txt`(ファイル名=中身)。**ユーザ裁定「おいて問題ない」**。
- 連鎖(全て try/except・失敗でデプロイは止めない・各 `--no-indexnow` で抑止・`--dry` は到達しない):
  `_r2-sync.py`(週次)→ pending に積むだけ / `_weekly-finalize.py` → edge purge 後に drain /
  `_deploy-feature.py`・`_deploy-differential.py` → purge後に積んで即 drain。
- 写像 `key_to_url`: `.html` のみ(RSC `.txt`/`_next/`/JSON/sitemap/`_empty`/404/開発面 除外)。selftest あり。
- 記録: `.cache/indexnow-pending.json` / `.cache/indexnow-log.jsonl`。手動 `--status` / `--drain [--dry]` / `--urls` / `--clear`。

## ★鍵の性質(一次情報。 旧記述「秘密ではない」は不正確だったので訂正)

- 仕様は**公開設置を必須**とする一方(「without login, firewall, or IP restrictions」)、
  同じ文書に「**Only you and the search engines should know the key and your file key location**」とも書いてある。
  ファイル名がキーそのものなので機密性要求としては自己矛盾しており、**実際の安全性の根拠は推測困難性(8〜128文字)だけ**。
- 鍵を知る第三者にできること = **自ホストのURLを送るノイズだけ**。実測で確認:
  他ホストURLを混ぜると **HTTP 422** で拒否(api.indexnow.org に実POSTして確認)。
  404の大量送信は攻撃にならない(仕様が404/410送信を推奨動作として明記)。インデックス削除・順位操作は不可。
  実害は **送信枠の消費(429で自分の送信が弾かれる)** と **クロール枠の浪費** の2つだけで、いずれも影響小。
- 漏洩時は**新しいファイルを置いて新キーで送り始めるだけ**(ダウンタイム無し・再検証は自動)。
- 応答: 200/202=受理(202はキー検証が非同期=API応答でキー有効性は判定できない)、400/403/422/429。1POST ≤ 10,000 URL。
- **Google は IndexNow 不参加**。Google 向けは sitemap + 内部リンクのまま([[seo_structure_gaps_2026_09_04]])。

## 現在の状態(2026-09-04)

- **まだ一度も送信していない**。`public/<key>.txt` は本番で **404**(次の機能蒸留/週次で R2 に上がる)。
  それまで送信は `key_file_live` で止まり pending に溜まる設計。
- Cloudflare Crawler Hints = **有効化済み**(無害なので残す。当てにはしない)。
- Bing Webmaster Tools = **登録済み + sitemap 送信済み**(`https://mangal-db.com/sitemap.xml`)。
  ★BWT のキー生成ボタンは**ブラウザ内のUUID生成**で、鍵の自己ホストは依然必須。BWT の IndexNow 機能は Insights(レポート)。

## ★未修正の欠陥(2026-09-04 レビューで確定。 初回送信の前に直すこと)

1. **【高】週次で内容が変わっていない頁まで全部送る** — 全頁HTMLがハッシュ付きチャンク名
   (`main-app-<hash>.js` 等)を埋め込むため、コード変更で**全66k頁のsha256が変わり** `to_put` に入る。
   IndexNow FAQ は「内容変化が無いURLの再送信はクロール枠の浪費」と明記。
   修正案A(推奨)= HTMLからチャンクのハッシュ付きファイル名を伏せてハッシュし、実質無変更の頁は通知しない。修正案B= 送信上限。**未決**。
2. **【中】削除通知のURLが公開slugでなくSRC stem** — `_deploy-differential.py` の `dropped` は SRC stem。
   stem≠slug が **1,759頁/69,223頁** あり、存在しないURLを送り本物を送らない。既存の purge 経路も同じ(元からの不整合)。
3. **【中】purge失敗・疎通FAILでも無条件に送る** — `pfail` を数えて print するだけで中断しない。
   purgeトークン未設定時は「旧HTMLが最長1日残る」と表示しつつクローラを呼ぶ = 設計意図と矛盾。
4. **【中】鍵未配信の間 pending が単調増加** — 1と重なると初回 drain が巨大化する。

**修正済み**: `drain()` の消し込み取り違え(commit f7d99af1a)。submit の戻りを件数から**受理URLのlist**へ。
非429の失敗では break しないため件数の前方一致削除は「失敗URLを消して成功URLを残す」取り違えになる(再現テストで実証)。
併せて 403/429 は残チャンクを投げず中断。

**How to apply:** デプロイ後に `python scripts/_indexnow.py --status` で pending と鍵OKを見る。
関連: [[crawler_hints_ineffective_on_workers_r2]] [[hosting_worker_r2_architecture]] [[deploy_environments_state]] [[repo_is_public_github]]
