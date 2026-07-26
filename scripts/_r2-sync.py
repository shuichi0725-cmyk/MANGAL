"""R2 一括/差分アップロード(S3互換API・並列)。 [[hosting_worker_r2_architecture]]

out/(next export 出力)を R2 バケットへ同期する。
- ★初回フル(~14万ファイル)も増分(月次蒸留=数百ファイル)も同じ経路。並列なので per-file wrangler より桁違いに速い。
- 各ファイルの sha256 を manifest(.cache/r2-manifest.json)と比較し、変更/新規のみ PUT。
- ★manifest が壊れた/キーが欠けた時は、R2 の ETag(単一partは=MD5)と照合して「本番と中身が同一」の
  キーを PUT 省略し、manifest を書き戻して復元する(= 全件上げ直しを避ける。--no-reconcile で無効化)。
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
import os, sys, json, time, hashlib, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _r2_manifest

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

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", default="mangal-site")
    ap.add_argument("--create-bucket", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--prune-max", type=int, default=3000,
                    help="prune の削除上限(既定3000)。 超えたら削除せず報告のみ = ビルド事故の全消し防止")
    ap.add_argument("--prune-floor", type=float, default=0.9,
                    help="prune を許す最低ビルド率(既定0.9)。 out/ の manga頁数 < 前回×これ なら削除中止")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-reconcile", action="store_true",
                    help="manifest 欠損キーの ETag 照合補完をしない(= 欠損は全て PUT し直す)")
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()

    if not os.path.isdir(OUT):
        print("out/ が無い。 先に next build(static export)。"); sys.exit(1)

    # --- ★本番索引 overlay (= 構造欠陥の恒久対策 2026-07-02) ---
    # public/ の索引は **preview専用(1400件subset)** で、next export が out/ にそのまま継承する。
    # 上書きせず R2 同期すると本番の一覧/検索が 1400件になる。ここで data/ の本番索引で必ず上書きする。
    import shutil
    _IDX = ("manga-list-index.json", "manga-search-index.json", "manga-catch-index.json",
            "manga-list-head.json", "manga-alt-index.json")
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
    # --- ★本番カレンダー overlay (2026-07-06 索引と同型: public/=preview実在フィルタ版のため本番はdata/calendarのフル版で上書き) ---
    _CAL = os.path.join(ROOT, "data", "calendar")
    if os.path.isdir(_CAL):
        import shutil as _sh
        _dst = os.path.join(OUT, "calendar")
        if os.path.isdir(_dst):
            _sh.rmtree(_dst)
        _sh.copytree(_CAL, _dst)
        print(f"  本番カレンダー overlay: data/calendar → out/calendar")

    # ★.env.local から R2_* を自動読込(CR/空白strip。 bash export経由のCRLF事故 2026-07-03 の恒久対策)
    envp = os.path.join(ROOT, ".env.local")
    if os.path.exists(envp) and not os.environ.get("R2_ACCOUNT_ID"):
        for ln in open(envp, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("R2_") and "=" in ln:
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    acct = os.environ.get("R2_ACCOUNT_ID")
    akid = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not a.dry and not (acct and akid and secret):
        print("認証 env が無い: R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY を設定。 (--dry なら不要)")
        sys.exit(2)

    # --- 差分計算 ---
    prev, mstatus = _r2_manifest.load(MANIFEST)   # 破損は退避され {} (= 全キー欠損)で返る
    nextm, to_put = {}, []
    for p in walk(OUT):
        key = os.path.relpath(p, OUT).replace("\\", "/")
        h = sha(p)
        nextm[key] = h
        if prev.get(key) != h:
            to_put.append((key, p))
    to_del = [k for k in prev if k not in nextm]
    print(f"ローカル {len(nextm)} files / 変更 {len(to_put)} / 削除候補 {len(to_del)}")

    # ★prune の安全弁 (2026-07-26 導入)。
    #   背景: prune 無しで運用してきたため、非掲載判定でローカルから消した頁の HTML が R2 に残り続け、
    #   **孤児 1,041頁が本番で200のまま**だった([[r2_orphan_pages_prune_missing]])。
    #   一方 prune は「out/ に無いキーを全消し」なので、ビルドが途中で失敗した回に走ると本番が消し飛ぶ。
    #   そこで **消さない方向に倒す**ガードを置く(判定は --dry でも表示される)。
    _lo = sum(1 for k in nextm if k.startswith("manga/") and k.endswith(".html"))
    _pr = sum(1 for k in prev if k.startswith("manga/") and k.endswith(".html"))
    prune_block = None
    if _pr and _lo < _pr * a.prune_floor:
        prune_block = (f"ビルド不足の疑い: out/ の manga頁 {_lo:,} < 前回 {_pr:,} × {a.prune_floor} "
                       f"= {int(_pr * a.prune_floor):,}。 next build が途中で落ちた可能性")
    elif len(to_del) > a.prune_max:
        prune_block = f"削除候補 {len(to_del):,} > --prune-max {a.prune_max:,}"
    if a.prune:
        print(f"  prune判定: manga頁 前回{_pr:,} → 今回{_lo:,} / "
              + (f"★中止({prune_block})" if prune_block else f"実行可(削除 {len(to_del):,})"))

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

    # --- ★manifest 欠損キーの補完 (2026-07-17) ---
    # manifest 破損/欠落で「前回何を上げたか」を失うと、中身が同じでも全件 PUT し直しになる。
    # R2 の ETag(単一part upload では = 内容の MD5)と ローカルの MD5 を突き合わせ、
    # 同一のキーは PUT を省く(manifest 自体は末尾の json.dump(nextm) が全キー書き戻して復元する)。
    # ★対象は manifest に記録の無いキーだけ。記録が在るキーの差分判定(sha256)には触らない。
    # ★一致が保証するのは内容だけ。Content-Type は前回この同じスクリプトが PUT 時に付けている前提。
    missing = [(k, p) for (k, p) in to_put if k not in prev]
    if missing and not a.no_reconcile:
        print(f"manifest 欠損 {len(missing)} キー(manifest={mstatus}) → R2 の ETag と照合して補完")
        etags = {}
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=a.bucket):
            for o in page.get("Contents", []):
                et = o["ETag"].strip('"')
                if "-" not in et:   # multipart の ETag は MD5 でない = 照合不可 → PUT 対象のまま残す
                    etags[o["Key"]] = et
        skip = {k for k, p in missing if etags.get(k) == md5(p)}
        to_put = [it for it in to_put if it[0] not in skip]
        print(f"  補完 {len(skip)} キー(本番と同一 = PUT 省略) / 要PUT {len(missing) - len(skip)}")

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
        _blocked = prune_block
        # ★削除キーは必ず先にログへ(消した後で「何を消したか」を辿れるように。 再生成は build で可能)
        _log = os.path.join(ROOT, ".cache", f"r2-pruned-{time.strftime('%Y%m%d-%H%M%S')}.txt")
        os.makedirs(os.path.dirname(_log), exist_ok=True)
        with open(_log, "w", encoding="utf-8") as f:
            f.write("\n".join(to_del))
        if _blocked:
            print(f"★prune 中止({_blocked})。 削除は行わず PUT のみ完了。")
            print(f"  意図した削除なら内容を確認のうえ再実行: --prune --prune-max {len(to_del) + 100}")
            print(f"  削除候補一覧 → {_log}")
        else:
            for i in range(0, len(to_del), 1000):
                batch = to_del[i:i + 1000]
                s3.delete_objects(Bucket=a.bucket, Delete={"Objects": [{"Key": k} for k in batch]})
            print(f"prune: {len(to_del):,} 削除 (一覧 → {_log})")

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
