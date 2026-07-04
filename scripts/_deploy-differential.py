#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""差分ビルドエンジン (= トリガー「差分反映して」= diff-deploy skill。 2026-07-04新設)

変更ページだけを部分ビルドして本番R2へ選択PUTする。フル(週次蒸留~3h)に対し数分。

安全設計(慎重):
 1. ★コードドリフトガード: 前回フルビルド以降に「漫画頁に効くコード」
    (app/manga, app/layout.tsx, components/, lib/, next.config.ts, package.json)が
    変わっていたら abort → 週次蒸留を要求。部分ビルドHTMLが参照するチャンクが
    本番に無い事故を構造的に封鎖(buildId固定 "mangal-static" が前提)。
 2. 対象自動検出: marker(前回本番反映commit) → HEAD の data/manga.v2 差分。
 3. 部分ビルド: 対象slugだけの一時データdir(D:\\mangal-cache\\diffdata)で next build。
 4. ★選択同期: 対象頁ファイル(out/manga/<内部slug>.html/.txt) + 本番索引3本(ルートキー)のみPUT。
    部分ビルドのホーム/一覧等は subset データで焼かれた汚染物 = **絶対に同期しない**。
 5. 削除: marker比で消えた yml は R2 の該当頁を DELETE。
 6. edge cache purge: worker /api/purge (token認証) で対象URLの旧キャッシュを即時解消。
 7. manifest(.cache/r2-manifest.json) と marker(.cache/prod-deploy-marker.json) を更新。

使い方:
  python scripts/_deploy-differential.py                 # marker→HEAD 自動検出
  python scripts/_deploy-differential.py --only a,b,c    # 明示指定(SRC stem)
  python scripts/_deploy-differential.py --dry           # 検出と計画のみ
marker 初期化/更新は本スクリプトが成功時に自動。週次蒸留後は weekly 側が更新する。
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
DIFFDATA = r"D:\mangal-cache\diffdata"
MARKER = os.path.join(ROOT, ".cache", "prod-deploy-marker.json")
MANIFEST = os.path.join(ROOT, ".cache", "r2-manifest.json")
BUCKET = "mangal-site"
WORKER = "https://mangal-r2.shuichi0725.workers.dev"
# 漫画頁のHTML/チャンクに影響するコード面(ここが動いたら部分ビルド禁止)
CODE_SCOPE = ["app/manga", "app/layout.tsx", "app/globals.css", "components", "lib",
              "next.config.ts", "package.json", "tailwind.config.ts"]
IDX = ("manga-list-index.json", "manga-search-index.json", "manga-catch-index.json")
MASTERS = ("demographics.yml", "genres.yml", "magazines.yml", "publisher-aliases.yml",
           "publishers.yml", "slug-aliases.yml") + IDX


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def git_head():
    return sh(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()


def load_env():
    env = {}
    for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
        ln = ln.strip()
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def s3_client(env):
    import boto3
    return boto3.client("s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"])


CT = {".html": "text/html; charset=utf-8", ".txt": "text/plain; charset=utf-8",
      ".json": "application/json"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="SRC stemカンマ区切り(省略=markerから自動検出)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(MARKER):
        print("★abort: marker無し(.cache/prod-deploy-marker.json)。週次蒸留の直後に初期化される。")
        print("  手動初期化: 前回フルビルド時のcommitで {\"code_commit\":..., \"data_commit\":...} を作る。")
        sys.exit(3)
    mk = json.load(open(MARKER, encoding="utf-8"))

    # --- 1. コードドリフトガード ---
    r = sh(["git", "diff", "--name-only", f"{mk['code_commit']}..HEAD", "--", *CODE_SCOPE], cwd=ROOT)
    drift = [x for x in r.stdout.splitlines() if x.strip()]
    if drift:
        print("★abort: 前回フルビルド以降に漫画頁へ効くコードが変更されている → 「週次蒸留して」が必要:")
        for d in drift[:10]:
            print("  ", d)
        sys.exit(4)
    print(f"コードドリフト: なし (marker {mk['code_commit'][:9]})")

    # --- 2. 対象検出 ---
    dropped = []
    if a.only:
        stems = [s.strip() for s in a.only.split(",") if s.strip()]
    else:
        # ★manga.v2はgit外(再生成物・.gitignore /data/manga.v2/)なのでgit diff検出は不可(2026-07-04発覚)。
        #   検出 = 前回デプロイ時のymlハッシュmanifest(.cache/prod-pages-manifest.json)との比較。
        import glob as _g
        pm_path = os.path.join(ROOT, ".cache", "prod-pages-manifest.json")
        if not os.path.exists(pm_path):
            print("★abort: prod-pages-manifest無し。週次蒸留後に scripts/_init-pages-manifest.py で初期化。")
            sys.exit(3)
        prev_pm = json.load(open(pm_path, encoding="utf-8"))
        cur = {}
        for p in _g.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
            st = os.path.basename(p)[:-4]
            cur[st] = hashlib.sha1(open(p, "rb").read()).hexdigest()[:16]
        stems = [st for st, h in sorted(cur.items()) if prev_pm.get(st) != h]
        dropped = [st for st in sorted(prev_pm) if st not in cur]
        globals()["_CUR_PM"] = cur
    if not stems and not dropped:
        print("差分なし(marker以降 data/manga.v2 に変更がない)。")
        return
    print(f"対象: 更新{len(stems)} / 削除{len(dropped)}")
    if a.dry:
        print(" 更新:", ",".join(stems[:30]), "..." if len(stems) > 30 else "")
        print(" 削除:", ",".join(dropped[:10]))
        return
    if len(stems) > 3000:
        print("★abort: 対象3000頁超はフル(週次蒸留)の方が安全・速い。"); sys.exit(5)

    env = load_env()
    s3 = s3_client(env)

    # --- 3. 部分ビルド用ステージング ---
    if os.path.exists(DIFFDATA):
        shutil.rmtree(DIFFDATA)
    os.makedirs(os.path.join(DIFFDATA, "manga"))
    # masters+索引 = 本番data/からコピー / seeds・art-books = 実体参照(junction相当のコピーで安全に)
    for f in MASTERS:
        shutil.copyfile(os.path.join(ROOT, "data", f), os.path.join(DIFFDATA, f))
    shutil.copytree(os.path.join(ROOT, "data", "seeds"), os.path.join(DIFFDATA, "seeds"))
    ab = os.path.join(ROOT, "data", "art-books.v2")
    if os.path.isdir(ab):
        shutil.copytree(ab, os.path.join(DIFFDATA, "art-books"))
    inner = {}
    for st in stems:
        src = os.path.join(ROOT, "data", "manga.v2", f"{st}.yml")
        if not os.path.exists(src):
            print(f"  skip(実体なし): {st}")
            continue
        shutil.copyfile(src, os.path.join(DIFFDATA, "manga", f"{st}.yml"))
        d = yaml.safe_load(open(src, encoding="utf-8"))
        inner[st] = d.get("slug") or st
    if not inner and not dropped:
        print("実体のある対象なし。"); return
    print(f"ステージング {len(inner)}頁 → {DIFFDATA}")

    # --- 4. 部分ビルド ---
    print("部分ビルド開始(対象頁のみ)…", flush=True)
    benv = dict(os.environ, MANGAL_DATA_DIR=DIFFDATA)
    r = subprocess.run(["npx.cmd", "next", "build"], cwd=ROOT, env=benv,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("★abort: build失敗"); print((r.stdout or "")[-1500:]); print((r.stderr or "")[-800:]); sys.exit(6)
    print("build OK")

    # --- 5. 選択同期(対象頁 + 索引3本のみ。他は絶対PUTしない) ---
    manifest = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}
    puts, misses = [], []
    for st, slug in inner.items():
        for ext in (".html", ".txt"):
            lp = os.path.join(OUT, "manga", f"{slug}{ext}")
            if os.path.exists(lp):
                puts.append((f"manga/{slug}{ext}", lp))
            elif ext == ".html":
                misses.append(slug)
    if misses:
        print(f"★abort: ビルド出力に無い頁 {len(misses)}: {misses[:5]} (= schema検証落ち等。先に修正)"); sys.exit(7)
    for name in IDX:
        src = os.path.join(ROOT, "data", name)
        if os.path.getsize(src) < 5 * 1048576 and name == "manga-list-index.json":
            print("★abort: 一覧索引<5MB = subset疑い"); sys.exit(3)
        puts.append((name, src))
    for key, lp in puts:
        ext = os.path.splitext(key)[1]
        body = open(lp, "rb").read()
        s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType=CT.get(ext, "application/octet-stream"))
        manifest[key] = hashlib.sha256(body).hexdigest()[:20]
    print(f"PUT {len(puts)} (頁{len(inner)}×2 + 索引3)")
    del_keys = []
    for st in dropped:
        for ext in (".html", ".txt"):
            del_keys.append(f"manga/{st}{ext}")
    if del_keys:
        s3.delete_objects(Bucket=BUCKET, Delete={"Objects": [{"Key": k} for k in del_keys]})
        for k in del_keys:
            manifest.pop(k, None)
        print(f"DELETE {len(del_keys)}")

    # --- 6. edge cache purge ---
    token = env.get("R2_PURGE_TOKEN", "")
    if token:
        paths = [f"/manga/{s}" for s in inner.values()] + [f"/manga/{s}" for s in dropped] + \
                [f"/{n}" for n in IDX]
        try:
            req = urllib.request.Request(f"{WORKER}/api/purge", method="POST",
                                         data=json.dumps({"paths": paths, "token": token}).encode(),
                                         headers={"content-type": "application/json"})
            res = json.load(urllib.request.urlopen(req, timeout=30))
            print(f"cache purge: {res}")
        except Exception as e:
            print(f"purge失敗(致命でない・最長1日で自然失効): {e}")
    else:
        print("purge token未設定 → 旧キャッシュは最長1日残る")

    # --- 7. manifest + marker 更新 ---
    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"))
    mk["data_commit"] = git_head()
    json.dump(mk, open(MARKER, "w", encoding="utf-8"), indent=1)
    print(f"marker更新 data_commit={mk['data_commit'][:9]}")
    # ★pages-manifest更新(検出の基準点)。--auto=全snapshot / --only=対象stemだけ差し替え
    pm_path = os.path.join(ROOT, ".cache", "prod-pages-manifest.json")
    if "_CUR_PM" in globals():
        json.dump(globals()["_CUR_PM"], open(pm_path, "w"))
        print("pages-manifest全更新")
    elif os.path.exists(pm_path):
        pm = json.load(open(pm_path, encoding="utf-8"))
        for st in inner:
            fp = os.path.join(ROOT, "data", "manga.v2", f"{st}.yml")
            if os.path.exists(fp):
                pm[st] = hashlib.sha1(open(fp, "rb").read()).hexdigest()[:16]
        for st in dropped:
            pm.pop(st, None)
        json.dump(pm, open(pm_path, "w"))
        print("pages-manifest部分更新")

    # --- 8. 疎通 ---
    ok = 0
    for slug in list(inner.values())[:3]:
        try:
            _rq = urllib.request.Request(f"{WORKER}/manga/{slug}?v=diff", headers={"User-Agent": "Mozilla/5.0"})
            code = urllib.request.urlopen(_rq, timeout=20).status
            ok += (code == 200)
        except Exception:
            pass
    print(f"疎通: {ok}/{min(3, len(inner))} OK")
    print("=== 差分反映 完了 ===")


if __name__ == "__main__":
    main()
