#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""索引の「事前圧縮版」(brotli 最高品質)を R2 に置く (2026-11-17)。 配る側 = workers/br-index.js。

背景: 索引は R2 に素のまま置き、Cloudflare がその場で圧縮して配っている(速さ優先の低い品質)。
  一覧索引(列形式 22MB)= その場の zstd 4.81MB → brotli 最高品質 3.45MB(−28%・2026-11-17 本番の実物で実測)。

仕組み:
  元の索引の隣に <元のキー>.<元の中身のMD5>.br を置くだけ(元は今までどおり)。
  Worker は「いま配っている元」の MD5 の名前の事前圧縮版が在る時だけそれを返す。
  ★名前に元の MD5 が入る = 元だけ更新されて事前圧縮版が古い、が起きない(名前が合わない = 従来の配り方に戻る)。
  ★ここは R2 の元の ETag と手元の MD5 が同じ時だけ置く(違う = 手元が本番と違う中身 = 置いても使われない)。

配信経路からの呼び方(元を PUT した後に呼ぶ):
  from _index_br import sync_br
  print(sync_br(s3, bucket, {"manga-list-cols.v1.json": "<手元のパス>", ...}))
  = r2-sync(週次)/ 差分反映 / 機能蒸留(羅針盤の隠し要素)。 失敗しても配信は止めない(従来の配り方に戻るだけ)。

単独で:
  python scripts/_index_br.py            # 4本を本番 R2 と突き合わせ、足りない事前圧縮版を置き、古いのを消す
  python scripts/_index_br.py --dry      # 何をするかだけ(R2 は読むだけ)
  python scripts/_index_br.py --status   # 本番の今の状態(元の MD5・事前圧縮版の有無・大きさ)

止め方: R2 から *.br を消す(`--remove-all`)。 Worker は自動で従来の配り方に戻る。
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, ".cache", "index-br")

# ★R2 のキー → 手元の正本。 workers/br-index.js の BR_KEYS と必ず同じにする(workers/br-index.test.js が突合)。
BR_SOURCES = {
    "manga-list-cols.v1.json": "data/manga-list-cols.v1.json",
    "manga-catch-index.json": "data/manga-catch-index.json",
    "manga-alt-index.json": "data/manga-alt-index.json",
    "data/compass-hidden.v1.json": "public/data/compass-hidden.v1.json",
}

# brotli 最高品質・窓 16MB(lgwin 24 = HTTP の br で許される最大)。 Python に brotli が無いので Node の zlib で作る。
_NODE = r"""
const z = require("zlib"), fs = require("fs");
const [src, dst] = process.argv.slice(1);
const raw = fs.readFileSync(src);
const out = z.brotliCompressSync(raw, { params: {
  [z.constants.BROTLI_PARAM_QUALITY]: 11,
  [z.constants.BROTLI_PARAM_LGWIN]: 24,
  [z.constants.BROTLI_PARAM_MODE]: z.constants.BROTLI_MODE_TEXT,
  [z.constants.BROTLI_PARAM_SIZE_HINT]: raw.length,
} });
if (!z.brotliDecompressSync(out).equals(raw)) { console.error("roundtrip mismatch"); process.exit(3); }
fs.writeFileSync(dst + ".tmp", out);
fs.renameSync(dst + ".tmp", dst);
"""


def md5_file(p: str) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def br_key(key: str, md5: str) -> str:
    return f"{key}.{md5}.br"


def compress(local: str, md5: str) -> str:
    """手元の索引を brotli 最高品質で圧縮した file のパス(同じ中身は作り直さない)。 解いて元と一致を確かめてから置く。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    dst = os.path.join(CACHE_DIR, f"{os.path.basename(local)}.{md5}.br")
    if not os.path.exists(dst):
        r = subprocess.run(["node", "-e", _NODE, local, dst], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"brotli 圧縮に失敗 {local}: {r.stderr.strip()[:300]}")
    return dst


def _etag(s3, bucket: str, key: str):
    try:
        return s3.head_object(Bucket=bucket, Key=key)["ETag"].strip('"')
    except Exception as e:  # 404 等
        if "404" in str(e) or "Not Found" in str(e) or "NoSuchKey" in str(e):
            return None
        raise


def _stale(s3, bucket: str, key: str, keep: str):
    pat = re.compile(re.escape(key) + r"\.[0-9a-f]{32}\.br$")
    out = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=key + "."):
        for o in page.get("Contents", []):
            if pat.fullmatch(o["Key"]) and o["Key"] != keep:
                out.append(o["Key"])
    return out


def sync_br(s3, bucket: str, files: dict, dry: bool = False) -> str:
    """files = {R2キー: 手元のパス}。 BR_SOURCES に無いキーは無視。 戻り値 = 1行の報告。 例外は投げない。"""
    lines, n_put, n_del, n_list = [], 0, 0, 0
    for key, local in files.items():
        if key not in BR_SOURCES:
            continue
        try:
            if not os.path.exists(local):
                lines.append(f"{key}: 手元に無い → skip")
                continue
            md5 = md5_file(local)
            remote = _etag(s3, bucket, key)
            if remote != md5:
                lines.append(f"{key}: R2 の元({remote or '無し'})と手元({md5[:8]})が違う → 置かない(従来の配り方のまま)")
                continue
            name = br_key(key, md5)
            if _etag(s3, bucket, name):
                state = "在る"
            else:
                bp = compress(local, md5)
                sz = os.path.getsize(bp)
                state = f"置く {os.path.getsize(local)/1e6:.2f}MB → {sz/1e6:.2f}MB"
                if not dry:
                    with open(bp, "rb") as f:
                        s3.put_object(Bucket=bucket, Key=name, Body=f.read(), ContentType="application/octet-stream")
                    n_put += 1
            old = _stale(s3, bucket, key, name)
            n_list += 1
            if old and not dry:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in old]})
                n_del += len(old)
            lines.append(f"{key}: {state}" + (f" / 古い版 {len(old)} 消す" if old else ""))
        except Exception as e:
            lines.append(f"{key}: ★失敗(配信は従来の配り方のまま): {str(e)[:200]}")
    if n_put or n_list:
        try:
            import _r2_ops_ledger as _rl
            _rl.record(n_put, n_list, "index-br")
        except Exception:
            pass
    head = "事前圧縮版(br)" + ("[--dry]" if dry else "") + f": PUT {n_put} / 削除 {n_del}"
    return head + "".join(f"\n  {s}" for s in lines)


def make_s3():
    env = {}
    for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
        ln = ln.strip()
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip()
    import boto3
    import _r2_manifest
    _r2_manifest.ensure_ca_bundle()
    return boto3.client("s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"], region_name="auto")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", default="mangal-site")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--remove-all", action="store_true", help="事前圧縮版を全部消す(= 従来の配り方に戻す)")
    a = ap.parse_args()
    s3 = make_s3()
    if a.status or a.remove_all:
        gone = []
        for key in BR_SOURCES:
            et = _etag(s3, a.bucket, key)
            brs = []
            for page in s3.get_paginator("list_objects_v2").paginate(Bucket=a.bucket, Prefix=key + "."):
                brs += [(o["Key"], o["Size"]) for o in page.get("Contents", []) if o["Key"].endswith(".br")]
            cur = [s for k, s in brs if et and k == br_key(key, et)]
            print(f"{key}: 元 {et} / 事前圧縮版 " + (f"使用中 {cur[0]/1e6:.2f}MB" if cur else "★無し(従来の配り方)")
                  + (f" / ほか {len(brs) - len(cur)} 本" if len(brs) > len(cur) else ""))
            gone += [k for k, _ in brs]
        if a.remove_all and gone:
            s3.delete_objects(Bucket=a.bucket, Delete={"Objects": [{"Key": k} for k in gone]})
            print(f"削除 {len(gone)} 本(Worker は従来の配り方に戻る。 エッジに焼いた分は元の中身が変わるまで残る)")
        return
    print(sync_br(s3, a.bucket, {k: os.path.join(ROOT, p) for k, p in BR_SOURCES.items()}, dry=a.dry))


if __name__ == "__main__":
    main()
