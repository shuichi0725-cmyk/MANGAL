---
name: indexnow-self-submit
description: IndexNow 自前送信=scripts/_indexnow.py(2026-09-04 稼働開始・鍵200・初回送信済)。r2-sync→pending→finalize(purge後)drain / feature・diff-deploy は即drain。鍵=public/efa08…txt。★欠陥3件は 2026-09-04 に修正済(本文ハッシュ層/公開slug/purge失敗で送らない)
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
- 記録: `.cache/indexnow-pending.json` / `.cache/indexnow-content.json`(本文ハッシュ台帳) / `.cache/indexnow-log.jsonl`。
  手動 `--status` / `--drain [--dry] [--purge] [--max N]` / `--urls` / `--add-keys-file` / `--clear` / `--selftest`。

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

## 現在の状態(2026-09-04 夜 = 稼働開始)

- ★**鍵ファイルを本番R2へ単独PUT済み**(ユーザ裁定「1で」)。`https://mangal-db.com/efa08a89….txt` = **200**、
  `--status` の「本番配信」= OK。 ★`_r2-sync.py` は使っていない(当時の `out/` は機能ビルドの残骸で
  **漫画66k頁が無く**、フル同期すると本番を壊すため boto3 で1オブジェクトだけ PUT した)。
  ★`.cache/r2-manifest.json` には入れていない = 次の週次でもう一度PUTされる(1 Class A・無害)。
- ★**初回送信 実施済み**: `/about` と `/` を送信 → **HTTP 202 と 200**(200=鍵検証も通った証拠)。
  = 鍵設置から送信までの配管が実地で通ることを確認。
- ★同時に踏んだ罠: Git Bash が引数 `/` を `C:/Program Files/Git/` に化かし、
  **トップの代わりに存在しないURLを1件送った**。 恒久対策として `sanitize_urls()` を submit の一点に置き、
  パス以外(空白・`:`・`\`・`//`)は送らず破棄+警告するようにした([[bash_tool_heredoc_quote_pitfall]])。
- Cloudflare Crawler Hints = **有効化済み**(無害なので残す。当てにはしない)。
- Bing Webmaster Tools = **登録済み + sitemap 送信済み**(`https://mangal-db.com/sitemap.xml`)。
  ★BWT のキー生成ボタンは**ブラウザ内のUUID生成**で、鍵の自己ホストは依然必須。BWT の IndexNow 機能は Insights(レポート)。

## ★欠陥3件 = 2026-09-04 修正済 (commit 8d5726526 / aa362800a)

### 1【高】無変更の頁まで全部送る → **本文ハッシュ層(案A-2)** で解決
全頁HTMLにハッシュ付きチャンク名(`main-app-<hash>.js`)が埋まるため、コードを1行直すと
**全頁の sha256 が変わり** to_put に入る。実測= 送信対象 90,281頁 に対し本当に内容が変わったのは
**4,067頁(有効4.5%)**。 ★採用= **案A-2「クローラが読む部分だけをハッシュ」**:
`<script>`(RSC flight `self.__next_f` 含む)/ローダ`<link>`(preload・stylesheet・icon)を落とし、
title/meta/JSON-LD/本文マークアップだけを sha256 → `.cache/indexnow-content.json` に台帳。
- ★案A-1(チャンク名だけマスク)を捨てた理由 = RSC flight の参照番号(`$L9`→`$Ld`)が木の変化で
  総振り直しになり空振りが残る。 live↔local 実測で **A-1=残差60ブロック / A-2=4ブロック(全部が本物の変更)**。
- 入口= `_indexnow.pending_add_files(put_pairs=[(R2キー, path)], dels, seed_pairs)`。
  r2-sync と feature-distill を結線。 ETag照合でPUTを省いたキーは seed_pairs で台帳にだけ記録。
- ★**台帳が空(初回/消失)は「台帳作成のみ・通知ゼロ」**に倒す = いきなり9万URL送る事故を構造で封じる。
  帰結: **次の週次は変更通知が0件**(削除は通知される)。 その回の分を出したい時だけ手動
  `--add-keys-file <R2キー一覧>` → `--drain`。
- 速度 128MB/s・byte変化した .html だけに掛けるので、コード無変更の週はほぼ0秒。
- backstop(案B)= `drain(max_urls=10000)`。 本当に全頁の内容が変わった時だけ効く。 超過分は pending に
  残し**残数を必ず表示**(黙って切り捨てない)。

### 2【中】削除通知のURLが公開slugでなくSRC stem → **resolve_pub_slug** で解決
PUT は公開slug なのに DELETE/purge/IndexNow だけ stem。 stem≠slug は **1,759頁/69,223頁** で、
消すと **R2に本物が残り(孤児頁)存在しないURLをpurge/通知**していた(IndexNow だけの話ではなかった)。
解決順= `.cache/prod-page-slugs.json`(週次 `_init-pages-manifest.py` が生成)→
`data/seeds/slug-overrides.yml`(★頁を消しても残る恒久記録。**flat 142件 と `overrides:` 配下 1,788件の2形が同居**
= 片方だけ読むと静かに取り逃す)→ 本番manifestの実在で検算 → stem。
実測: 次の差分反映で消える51頁中 **4頁**が旧実装では消し損ね。新実装は51/51が本番実在キーに解決。

### 3【中】purge失敗・疎通FAILでも無条件に送る → **送らない**に是正
`drain(exclude=…)` を追加。 diff-deploy / feature-distill は purge 失敗URL(トークン未設定なら全件)を除外し、
疎通0なら送信自体を見送る(pending に残り次の週次で送る)。
★併せて発覚: **finalize の purge は索引/JSON/sitemap だけで、変更した漫画頁を落としていなかった**
(HTML は `s-maxage=86400`)。 → `drain(purge=True)` を新設し finalize が使用 = **送るURL自身を先に purge**。
共通化した `_indexnow.purge_urls()`(batch=10 は worker CPU 上限に合わせた実測値)で実 purge 確認済み。

### 4【中】鍵未配信の間 pending が単調増加 → 1の解決で自然消滅
積まれるのが「本文が変わった頁」だけになったので、週あたり数千で頭打ち。上限10,000/回で分割送信。

**先行修正**: `drain()` の消し込み取り違え(commit f7d99af1a)。submit の戻りを件数から**受理URLのlist**へ。
非429の失敗では break しないため件数の前方一致削除は「失敗URLを消して成功URLを残す」取り違えになる(再現テストで実証)。
併せて 403/429 は残チャンクを投げず中断。

**How to apply:** デプロイ後に `python scripts/_indexnow.py --status` で pending / 鍵OK / **本文ハッシュ台帳の件数**を見る。
台帳0なら次回は通知0(=想定挙動)。 手動送信は `--drain [--purge] [--max N]`。
関連: [[crawler_hints_ineffective_on_workers_r2]] [[hosting_worker_r2_architecture]] [[deploy_environments_state]]
[[repo_is_public_github]] [[pubslug_src_stem_generator_trap]] [[r2_orphan_pages_prune_missing]] [[deploy_cache_swr_hid_the_fix]]
