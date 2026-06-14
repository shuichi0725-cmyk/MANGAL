# R2 配信デプロイ手順書（本番 mangal Worker → R2）

全 66k ページ ≈ 14万ファイルは Cloudflare Pages のファイル数上限を超えるため、
**Worker（配信）+ R2（HTML倉庫）** 構成で本番化する。Pages（`mangal-preview`）は見た目テスト用に常設のまま。
背景・料金・設計判断は memory `hosting_worker_r2_architecture` を参照。

## 構成物（リポジトリ同梱・ドラフト済み）

| ファイル | 役割 |
|---|---|
| `workers/r2-serve.js` | 配信 Worker。R2 fetch + エッジキャッシュ + 301リダイレクト + geo(adult_us) |
| `wrangler-r2.jsonc` | R2 Worker 用 wrangler 設定（`BUCKET` バインディング = `mangal-site`） |
| `scripts/_r2-sync.py` | S3互換APIで out/ を R2 へ**並列・差分**同期（初回フルも増分も同経路） |
| `scripts/_r2-upload.mjs` | wrangler ベースの差分アップロード（boto3 が使えない環境のフォールバック） |

## 必要な認証（2系統）

R2 は「データ面（S3 API）」と「Worker デプロイ面」で別の資格情報を使う。

### A. R2 データ面（バケット作成 + オブジェクト PUT）= S3 API トークン
Cloudflare ダッシュボード → R2 → **Manage R2 API Tokens** → Create（権限 = Object Read & Write）。
発行される **Access Key ID / Secret Access Key** を env に：

```
R2_ACCOUNT_ID=774e95ed884a48e76ffb5aa78ae7e037
R2_ACCESS_KEY_ID=<発行値>
R2_SECRET_ACCESS_KEY=<発行値>
```

### B. Worker デプロイ面 = Cloudflare API トークン or `wrangler login`
`wrangler deploy -c wrangler-r2.jsonc` には **Workers Scripts:Edit** 権限が要る。
- 対話可なら `wrangler login`（ブラウザOAuth）。
- 非対話/CIなら API トークン（既存「mangal deploy」に Workers Scripts:Edit を追加 or 新規）を `CLOUDFLARE_API_TOKEN` に。

## 手順

```bash
# 1. R2 認証 env をセット（上記 A）
export R2_ACCOUNT_ID=...  R2_ACCESS_KEY_ID=...  R2_SECRET_ACCESS_KEY=...

# 2. 本番データでフルビルド（static export → out/）
#    ※トップが全DBを送る構造課題が未解決なら先にそれを解消（軽量索引の別ファイル化）
MANGAL_DATA_DIR=data npm run build

# 3. R2 バケット作成 + 全ファイル並列アップロード（初回のみ --create-bucket）
python scripts/_r2-sync.py --bucket mangal-site --create-bucket

# 4. 配信 Worker をデプロイ（Bの認証）
npx wrangler deploy -c wrangler-r2.jsonc

# 5. 確認: https://mangal.shuichi0725.workers.dev/ と深いページ（/manga/<slug>）が R2 から出る
```

## 月次蒸留での増分更新

```bash
MANGAL_DATA_DIR=data npm run build
python scripts/_r2-sync.py --bucket mangal-site --prune   # 変更分のみ PUT + 不要キー削除
```
差分は manifest（`.cache/r2-manifest.json`）の sha256 比較で決まる。蒸留差分は通常数百ファイル＝無料枠内。

## 掃除

R2 化までの間、native Workers Builds（Git連携）が 66k を Workers Assets にビルドしようとして
ファイル数上限で失敗し続ける → Cloudflare → mangal → Settings → Builds を**停止**推奨（失敗メール抑制）。

## 未解決の前提（R2 とは別レイヤ）

- ★トップページが全DB（66k）を props で送る → 数十MBで重い。**軽量検索索引の別ファイル化＋遅延ロード**が要。
- 検索 matchText が O(n) 全件線形。
- フル 66k ビルド自体の所要・安定性は未検証（プレビューは 600 件サブセットのみ）。
