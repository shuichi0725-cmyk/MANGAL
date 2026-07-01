"""R2 一括/差分アップロード(S3互換API・並列)。 [[hosting_worker_r2_architecture]]

out/(next export 出力)を R2 バケットへ同期する。
- ★初回フル(~14万ファイル)も増分(月次蒸留=数百ファイル)も同じ経路。並列なので per-file wrangler より桁違いに速い。
- 各ファイルの sha256 を manifest(.cache/r2-manifest.json)と比較し、変更/新規のみ PUT。
- Content-Type を拡張子から付与(配信WorkerもCT再設定するが倉庫側も正しく持つ)。
- --prune でローカルに無いキーを R2 から削除。 --create-bucket で無ければバケット作成。

認証(env、Cloudflare ダッシュボード R2 → "Manage R2 API Tokens" で発行):
  R2_ACCOUNT_ID         = 774e95ed884a48e76ffb5aa78ae7e037
  R2_ACCESS_KEY_ID      = <R2 Access Key ID>
  R2_SECRET_ACCESS_KEY  = <R2 Secret Access Key>

使い方:
  python scripts/_r2-sync.py --bucket mangal-site --create-bucket   # 初回(バケット作成+全PUT)
  python scripts/_r2-sync.py --bucket mangal-site                   # 増分(差分PUTのみ)
  python scripts/_r2-sync.py --bucket mangal-site --prune           # 差分PUT + 不要キー削除
  python scripts/_r2-sync.py --dry                                  # 計算だけ(PUTしない)
"""
import os, sys, json, hashlib, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.getcwd()
OUT = os.path.join(ROOT, "out")
MANIFEST = os.path.join(ROOT, ".cache", "r2-manifest.json")

CT = {
    ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml", ".webp": "image/webp", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
    ".xml": "application/xml; charset=utf-8", ".txt": "text/plain; charset=utf-8",
    ".ico": "image/x-icon", ".webmanifest": "application/manifest+json",
}

def content_type(key):
    _, ext = os.path.splitext(key)
    return CT.get(ext.lower(), "application/octet-stream")

def walk(d):
    for root, _, files in os.walk(d):
        for name in files:
            yield os.path.join(root, name)

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", default="mangal-site")
    ap.add_argument("--create-bucket", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()

    if not os.path.isdir(OUT):
        print("out/ が無い。 先に next build(static export)。"); sys.exit(1)

    # --- ★本番索引 overlay (= 構造欠陥の恒久対策 2026-07-02) ---
    # public/ の索引は **preview専用(1400件subset)** で、next export が out/ にそのまま継承する。
    # 上書きせず R2 同期すると本番の一覧/検索が 1400件になる。ここで data/ の本番索引で必ず上書きする。
    import shutil
    _IDX = ("manga-list-index.json", "manga-search-index.json", "manga-catch-index.json")
    for name in _IDX:
        src = os.path.join(ROOT, "data", name)
        dst = os.path.join(OUT, name)
        if not os.path.exists(src):
            print(f"★abort: 本番索引が無い data/{name} (= _build-list-index.py data/manga.v2 data を先に)"); sys.exit(3)
        shutil.copyfile(src, dst)
        print(f"  本番索引 overlay: {name} ({os.path.getsize(src)/1048576:.1f}MB)")
    # guard: 一覧索引が小さすぎる(<5MB)= preview subset を焼こうとしている
    if os.path.getsize(os.path.join(OUT, "manga-list-index.json")) < 5 * 1048576:
        print("★abort: manga-list-index.json が 5MB 未満 = preview subset 疑い。data/ の生成元を確認。"); sys.exit(3)

    acct = os.environ.get("R2_ACCOUNT_ID")
    akid = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not a.dry and not (acct and akid and secret):
        print("認証 env が無い: R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY を設定。 (--dry なら不要)")
        sys.exit(2)

    # --- 差分計算 ---
    prev = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}
    nextm, to_put = {}, []
    for p in walk(OUT):
        key = os.path.relpath(p, OUT).replace("\\", "/")
        h = sha(p)
        nextm[key] = h
        if prev.get(key) != h:
            to_put.append((key, p))
    to_del = [k for k in prev if k not in nextm]
    print(f"ローカル {len(nextm)} files / 変更 {len(to_put)} / 削除候補 {len(to_del)}")

    if a.dry:
        print("(--dry: アップロードせず終了)"); return

    import boto3
    from botocore.config import Config
    s3 = boto3.client(
        "s3", endpoint_url=f"https://{acct}.r2.cloudflarestorage.com",
        aws_access_key_id=akid, aws_secret_access_key=secret, region_name="auto",
        config=Config(retries={"max_attempts": 5, "mode": "standard"}, max_pool_connections=a.workers + 4),
    )

    if a.create_bucket:
        try:
            s3.head_bucket(Bucket=a.bucket); print(f"バケット {a.bucket} 既存")
        except Exception:
            s3.create_bucket(Bucket=a.bucket); print(f"バケット {a.bucket} 作成")

    done = [0]
    def put(item):
        key, p = item
        with open(p, "rb") as f:
            s3.put_object(Bucket=a.bucket, Key=key, Body=f.read(), ContentType=content_type(key))
        done[0] += 1
        if done[0] % 500 == 0:
            print(f"  ...{done[0]}/{len(to_put)} put")
        return key

    errs = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(put, it): it[0] for it in to_put}
        for fu in as_completed(futs):
            try:
                fu.result()
            except Exception as e:
                errs.append((futs[fu], str(e)))

    if a.prune and to_del:
        for i in range(0, len(to_del), 1000):
            batch = to_del[i:i + 1000]
            s3.delete_objects(Bucket=a.bucket, Delete={"Objects": [{"Key": k} for k in batch]})
        print(f"prune: {len(to_del)} 削除")

    if errs:
        print(f"★失敗 {len(errs)} 件(manifest更新せず再実行で再試行):")
        for k, e in errs[:10]:
            print(f"  {k}: {e}")
        sys.exit(3)

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump(nextm, open(MANIFEST, "w", encoding="utf-8"))
    print(f"完了: put {len(to_put)} / manifest更新 {MANIFEST}")

if __name__ == "__main__":
    main()
