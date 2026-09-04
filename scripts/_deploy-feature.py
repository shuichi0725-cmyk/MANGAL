#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""機能蒸留エンジン (= トリガー「機能蒸留して」= feature-distill skill。2026-07-28新設)

サイトを構成する面(ホーム/検索/AI書評コラム/コーナー/ジャンル面/一覧…)= **非漫画ページと
共有JSチャンクだけ**を本番R2へ反映する。漫画66k頁のHTML/データには一切触れない。
週次蒸留(フル~3h)に対し ~30分。差分蒸留(diff-deploy=データのみ)のちょうど対(=コードのみ)。

安全設計:
 1. ★データ凍結: ビルドは「本番公開済みの頁集合」(.cache/prod-pages-manifest.json の stem)だけを
    hardlink staging して行う。ローカルの本番待ち新規頁(本番化済みドラフト等)がホーム/ジャンル面に
    焼き込まれて404リンク化する事故を構造的に封鎖。
 2. ★漫画詳細スキップ: MANGAL_FEATURE_BUILD=1 → app/manga/[slug] は placeholder(_empty)のみ生成。
    これでビルドが 3h → 数十分。
 3. ★選択同期: out/ から manga/**・calendar/**・ルート索引・sitemap を除外した全ファイルを
    r2-manifest と sha256 差分で PUT。チャンクは content-hash 名 = 純粋追加なので、
    旧漫画頁は旧チャンクを参照し続けて無傷(--prune しない運用が前提)。
 4. ★索引は絶対に触らない: 旧漫画頁のJSが同名索引を読むため(形式変更=ファイル名バンプ規約)。
    ルート索引・calendar・sitemap は除外リストで恒久封鎖。
 5. ★コーナーJSONガード: out/data/*.json が参照する slug が本番manifestに無ければ
    そのJSONをskipして警告(未公開頁への404リンク防止)。
 6. manifest は増分更新のみ(全置換禁止=漫画キーが消える)。marker には feature_commit を記録し
    code_commit は触らない(= 漫画頁は旧コードのままなので diff-deploy のドリフトガードを誤解除しない)。
 7. edge cache purge: 変更したHTML/txt/JSONのパスを worker /api/purge で即時失効。

使い方:
  python scripts/_deploy-feature.py --dry          # staging+ビルド+同期計画まで(PUT/purgeしない)
  python scripts/_deploy-feature.py                # 本番反映(トリガー「機能蒸留して」時のみ)
  python scripts/_deploy-feature.py --skip-build   # 直前の featビルド out/ を再利用して同期のみ
  ※ビルドは長い(数十分)。呼び出し側は Start-Process デタッチ+ログ監視で(skill 参照)。
"""
import argparse
import glob as globmod
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _r2_manifest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
FEATDATA = os.path.join(ROOT, ".cache", "featdata")
MARKER = os.path.join(ROOT, ".cache", "prod-deploy-marker.json")
MANIFEST = os.path.join(ROOT, ".cache", "r2-manifest.json")
PAGES_PM = os.path.join(ROOT, ".cache", "prod-pages-manifest.json")
BUILD_LOG = os.path.join(ROOT, ".cache", "feature-build.log")
BUCKET = "mangal-site"
WORKER = "https://mangal-db.com"

# 同期から恒久除外(= データ世界。機能蒸留は絶対に触らない)
IDX = ("manga-list-index.json", "manga-catch-index.json",
       "manga-list-head.json", "manga-alt-index.json")
MASTERS = ("demographics.yml", "genres.yml", "magazines.yml", "publisher-aliases.yml",
           "publishers.yml", "slug-aliases.yml") + IDX
CT = {
    ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml", ".webp": "image/webp", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
    ".xml": "application/xml; charset=utf-8", ".txt": "text/plain; charset=utf-8",
    ".ico": "image/x-icon", ".webmanifest": "application/manifest+json",
}


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def excluded(key: str) -> bool:
    """データ世界のキーか(= 機能蒸留が絶対にPUTしないもの)"""
    if key.startswith(("manga/", "calendar/")):
        return True
    if key in IDX or key.startswith("sitemap"):
        return True
    return False


def collect_slugs(obj, found: set):
    """JSON内の "slug" キーの文字列値を再帰回収(コーナーJSONの参照先検証用)"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "slug" and isinstance(v, str):
                found.add(v)
            else:
                collect_slugs(v, found)
    elif isinstance(obj, list):
        for v in obj:
            collect_slugs(v, found)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="staging+build+計画のみ(PUT/purge/manifest更新なし)")
    ap.add_argument("--skip-build", action="store_true", help="既存out/(直前のfeatビルド)を再利用")
    ap.add_argument("--allow-dirty", action="store_true", help="コード未コミットでも続行(来歴が濁るので非推奨)")
    ap.add_argument("--skip-tests", action="store_true",
                    help="★非推奨: 検索スナップショット等の前検査を飛ばす(退行がそのまま本番に出る)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--no-indexnow", action="store_true", help="変更した面のURLを IndexNow へ送らない")
    a = ap.parse_args()

    # --- 0. 前提(fail-closed) ---
    for p, msg in ((MARKER, "marker無し(週次蒸留の直後に初期化される)"),
                   (PAGES_PM, "prod-pages-manifest無し(週次蒸留後に _init-pages-manifest.py)")):
        if not os.path.exists(p):
            print(f"★abort: {msg}: {p}")
            sys.exit(3)
    manifest, mstatus = _r2_manifest.load(MANIFEST, quarantine=False)
    if mstatus != "ok":
        print(f"★abort: r2-manifest が {mstatus} = 本番に何が在るか判定不能。「週次蒸留して」で復元。")
        sys.exit(3)
    mk = json.load(open(MARKER, encoding="utf-8"))
    # コード未コミット検査(来歴: 本番に出たコードはcommitに対応させる)
    r = sh(["git", "status", "--porcelain", "--", "app", "components", "lib", "public",
            "next.config.ts", "package.json", "tailwind.config.ts"], cwd=ROOT)
    dirty = [x for x in r.stdout.splitlines() if x.strip()]
    if dirty and not a.allow_dirty:
        print(f"★abort: コード面に未コミット変更 {len(dirty)}件(先に commit。強行= --allow-dirty):")
        for d in dirty[:8]:
            print("  ", d)
        sys.exit(3)

    # --- 0b. 前検査(2026-08-01): 型検査 + 全テスト。★検索スナップショットがここに含まれる ---
    #   このルートは「コードだけ本番へ」なので、検索や一覧が壊れていても頁のHTTP 200検査
    #   (Step7)は素通りする。実際に2026-07 の性能改修まで、検索の結果集合や表示順が
    #   変わっていないことを機械で確かめる手立てが無かった。
    #   lib/searchSnapshot.test.ts が実索引由来の固定コーパスで「件数・表示順・tier分布・
    #   ファセット件数」を記録と突合するので、意図しない変化はここで赤くなって止まる。
    #   意図した変更なら UPDATE_SEARCH_SNAPSHOT=1 で焼き直し、差分を git diff で見てから commit。
    if not a.skip_tests:
        for label, cmd in (("型検査", ["npx", "tsc", "--noEmit"]), ("テスト", ["npm", "test"])):
            print(f"前検査: {label} …", flush=True)
            r = subprocess.run(cmd, cwd=ROOT, shell=(os.name == "nt"),
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                print(f"★abort: {label} が失敗 = この状態を本番に出さない。")
                print((r.stdout or "")[-3000:])
                print((r.stderr or "")[-2000:])
                sys.exit(3)
        print("前検査: 型検査・テストとも green(検索スナップショット一致)", flush=True)

    # --- 1. staging(本番公開済み頁集合に凍結) ---
    if not a.skip_build:
        prod_stems = json.load(open(PAGES_PM, encoding="utf-8"))
        print(f"staging: 本番公開済み {len(prod_stems)} stem → {FEATDATA}", flush=True)
        if os.path.exists(FEATDATA):
            shutil.rmtree(FEATDATA)
        os.makedirs(os.path.join(FEATDATA, "manga"))
        for f in MASTERS:
            src = os.path.join(ROOT, "data", f)
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(FEATDATA, f))
        shutil.copytree(os.path.join(ROOT, "data", "seeds"), os.path.join(FEATDATA, "seeds"))
        # ★art-books は週次と同じ data/art-books(=公開済み状態)を使う。art-books.v2 は作業中の
        #   新規(検証未通過あり得る)が混ざる=データ凍結原則にも反する(2026-07-28実踏: 空kanaでZod落ち)。
        ab = os.path.join(ROOT, "data", "art-books")
        if not os.path.isdir(ab):
            ab = os.path.join(ROOT, "data", "art-books.v2")
        if os.path.isdir(ab):
            shutil.copytree(ab, os.path.join(FEATDATA, "art-books"))
        linked, missing_local = 0, 0
        for st in prod_stems:
            src = os.path.join(ROOT, "data", "manga.v2", f"{st}.yml")
            dst = os.path.join(FEATDATA, "manga", f"{st}.yml")
            if not os.path.exists(src):
                missing_local += 1  # 公開後にローカルでdropされた頁 = staging外(本番頁はそのまま残る)
                continue
            try:
                os.link(src, dst)  # 同一ボリューム=hardlinkで高速(読み取り専用利用)
            except OSError:
                shutil.copyfile(src, dst)
            linked += 1
        print(f"staging完了: 頁{linked} (ローカル欠={missing_local})", flush=True)

        # --- 2. ビルド(漫画詳細スキップ) ---
        print(f"機能ビルド開始(MANGAL_FEATURE_BUILD=1)… log={BUILD_LOG}", flush=True)
        benv = dict(os.environ, MANGAL_DATA_DIR=FEATDATA, MANGAL_FEATURE_BUILD="1")
        # ★Nodeヒープ上限(既定~4GB)ではコンパイル段でOOM死(2026-07-28実踏)。週次と同じ12GBを既定に。
        benv.setdefault("NODE_OPTIONS", "--max-old-space-size=12288")
        t0 = time.time()
        with open(BUILD_LOG, "w", encoding="utf-8") as lf:
            r = subprocess.run(["npx.cmd", "next", "build"], cwd=ROOT, env=benv,
                               stdout=lf, stderr=subprocess.STDOUT)
        if r.returncode != 0:
            print(f"★abort: build失敗(exit {r.returncode})。log末尾:")
            print(open(BUILD_LOG, encoding="utf-8", errors="replace").read()[-1500:])
            sys.exit(6)
        print(f"build OK ({(time.time()-t0)/60:.1f}分)", flush=True)

    # --- 3. 出力サニティ ---
    if not os.path.exists(os.path.join(OUT, "index.html")):
        print("★abort: out/index.html が無い(ビルド出力不全)")
        sys.exit(6)
    manga_html = globmod.glob(os.path.join(OUT, "manga", "*.html"))
    if len(manga_html) > 5:
        print(f"★abort: out/manga に {len(manga_html)}頁 = MANGAL_FEATURE_BUILD が効いていない"
              f"(このoutは同期しない。app/manga/[slug]/page.tsx のフラグを確認)")
        sys.exit(6)

    # --- 4. 同期対象の差分計算 ---
    to_put, skipped_excl = [], 0
    for root, _, files in os.walk(OUT):
        for name in files:
            p = os.path.join(root, name)
            key = os.path.relpath(p, OUT).replace("\\", "/")
            if excluded(key):
                skipped_excl += 1
                continue
            h = sha(p)
            if manifest.get(key) != h:
                to_put.append((key, p, h))
    # --- 5. コーナーJSONガード(未公開slug参照の検出) ---
    corner_skipped = []
    kept = []
    for key, p, h in to_put:
        if key.startswith("data/") and key.endswith(".json"):
            try:
                found: set = set()
                collect_slugs(json.load(open(p, encoding="utf-8")), found)
            except Exception as e:
                print(f"  ★{key}: JSON読解不能({e}) → skip")
                corner_skipped.append((key, ["<parse-error>"]))
                continue
            unknown = sorted(s for s in found
                             if f"manga/{s}.html" not in manifest and f"art-books/{s}.html" not in manifest)
            if unknown:
                corner_skipped.append((key, unknown))
                continue
        kept.append((key, p, h))
    to_put = kept
    if corner_skipped:
        print(f"★コーナーJSON {len(corner_skipped)}本を未公開slug参照でskip(週次で公開後に再実行):")
        for key, unknown in corner_skipped:
            print(f"  {key}: {unknown[:5]}{' …' if len(unknown) > 5 else ''} ({len(unknown)}件)")

    n_html = sum(1 for k, _, _ in to_put if k.endswith(".html"))
    n_txt = sum(1 for k, _, _ in to_put if k.endswith(".txt"))
    n_next = sum(1 for k, _, _ in to_put if k.startswith("_next/"))
    n_new_chunk = sum(1 for k, _, _ in to_put if k.startswith("_next/") and k not in manifest)
    n_other = len(to_put) - n_html - n_txt - n_next
    print(f"同期計画: PUT {len(to_put)} (頁{n_html}html+{n_txt}txt / チャンク{n_next}[新規{n_new_chunk}] / "
          f"その他{n_other}) / データ世界除外{skipped_excl}")
    # 既存チャンクの中身違い上書き = content-hash名の原則に反する異常 → 明示(通常0)
    overwritten_chunks = [k for k, _, _ in to_put if k.startswith("_next/") and k in manifest]
    if overwritten_chunks:
        print(f"  ★注意: 既存チャンク名の中身違い {len(overwritten_chunks)}件(通常0。固定名資産の可能性): "
              f"{overwritten_chunks[:3]}")
    if a.dry:
        for k, _, _ in sorted(to_put)[:40]:
            print("   ", k)
        if len(to_put) > 40:
            print(f"    … 他{len(to_put)-40}件")
        print("(--dry: PUT/purgeせず終了)")
        return

    if not to_put:
        print("差分なし(コード/面の変更が本番と同一)。")
        return

    # --- 6. PUT ---
    env = {}
    for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
        ln = ln.strip()
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip()
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                      aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"], region_name="auto",
                      config=Config(retries={"max_attempts": 5, "mode": "standard"},
                                    max_pool_connections=a.workers + 4))
    from concurrent.futures import ThreadPoolExecutor, as_completed
    errs, done = [], [0]

    def put(item):
        key, p, h = item
        ext = os.path.splitext(key)[1].lower()
        with open(p, "rb") as f:
            s3.put_object(Bucket=BUCKET, Key=key, Body=f.read(),
                          ContentType=CT.get(ext, "application/octet-stream"))
        done[0] += 1
        if done[0] % 200 == 0:
            print(f"  ...{done[0]}/{len(to_put)} put", flush=True)
        return key, h

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(put, it): it[0] for it in to_put}
        for fu in as_completed(futs):
            try:
                key, h = fu.result()
                manifest[key] = h
            except Exception as e:
                errs.append((futs[fu], str(e)))
    if errs:
        print(f"★PUT失敗 {len(errs)}件(manifestは成功分のみ更新済。再実行で残りを再試行):")
        for k, e in errs[:8]:
            print("  ", k, e)
        json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"))
        sys.exit(4)
    print(f"PUT {len(to_put)} 完了")
    try:
        import _r2_ops_ledger as _rl
        _rl.record(len(to_put), 0, "feature-distill")
        print(_rl.report())
    except Exception:
        pass

    # --- 7. manifest(増分) + marker(feature_commit) ---
    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"))
    mk["feature_commit"] = sh(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    json.dump(mk, open(MARKER, "w", encoding="utf-8"), indent=1)
    print(f"manifest増分更新 / marker feature_commit={mk['feature_commit'][:9]} (code_commitは意図的に非更新)")

    # --- 8. edge cache purge(変更した面のみ) ---
    token = env.get("R2_PURGE_TOKEN", "")
    page_urls = ["/" if k == "index.html" else "/" + k[:-5] for k, _, _ in to_put if k.endswith(".html")]
    purge_failed = set()   # ★purge できなかった面は IndexNow に流さない(旧HTMLを掴ませないため)
    if token:
        paths = []
        for key, _, _ in to_put:
            if key.endswith(".html"):
                paths.append("/" if key == "index.html" else "/" + key[:-5])
            elif key.endswith(".txt") or (key.startswith("data/") and key.endswith(".json")):
                paths.append("/" + key)
        purged, pfail = 0, 0
        for i in range(0, len(paths), 10):
            try:
                req = urllib.request.Request(f"{WORKER}/api/purge", method="POST",
                                             data=json.dumps({"paths": paths[i:i + 10], "token": token}).encode(),
                                             headers={"content-type": "application/json",
                                                      "User-Agent": "Mozilla/5.0"})
                purged += json.load(urllib.request.urlopen(req, timeout=60)).get("purged", 0)
            except Exception:
                pfail += 1
                purge_failed.update(paths[i:i + 10])
            time.sleep(0.3)
        print(f"cache purge: {len(paths)}パス / purged {purged} / 失敗batch {pfail}")
    else:
        print("purge token未設定 → 旧キャッシュは最長1日(HTML)/7日(JSON)残る")
        purge_failed.update(page_urls)

    # --- 9. 疎通(新しい面 + 旧漫画頁の生存) ---
    checks = [("/", "ホーム")]
    changed_pages = [k for k, _, _ in to_put if k.endswith(".html") and k != "index.html"]
    if changed_pages:
        checks.append(("/" + changed_pages[0][:-5], "変更面"))
    live_manga = next((k for k in manifest if k.startswith("manga/") and k.endswith(".html")), None)
    if live_manga:
        checks.append(("/" + live_manga[:-5], "旧漫画頁(無傷確認)"))
    ok = 0
    for path, label in checks:
        try:
            rq = urllib.request.Request(f"{WORKER}{path}?v=feat", headers={"User-Agent": "Mozilla/5.0"})
            code = urllib.request.urlopen(rq, timeout=20).status
            ok += (code == 200)
            print(f"  疎通 {label}: {code} {path}")
        except Exception as e:
            print(f"  疎通 {label}: FAIL {path} ({e})")
    print(f"疎通: {ok}/{len(checks)} OK")

    # --- 10. ★IndexNow (2026-09-04): 自前 purge 済みなので、変更した面のURLを積んで即送信 ---
    # ★積むのは pending_add_files = **本文が変わった面だけ**(案A-2)。 機能蒸留は定義上コード変更なので、
    #   ここの to_put(byte差分)には「チャンク名が変わっただけの面」が必ず全部入る = 素で積むと空振りになる。
    if not a.no_indexnow:
        try:
            import _indexnow
            print(_indexnow.pending_add_files([(k, p) for k, p, _ in to_put], [], "feature-distill"))
            # ★purge 失敗分は送らない / 疎通が全滅なら送らない(pending に残るので次の週次で送る)
            if ok == 0:
                print("IndexNow: 疎通が 0 → 送信見送り(pending に保持)")
            else:
                print(_indexnow.drain(exclude=purge_failed))
        except Exception as _e:
            print(f"(IndexNow skip: {_e}) → 手動: python scripts/_indexnow.py --drain")
    print("=== 機能蒸留 完了 ===")


if __name__ == "__main__":
    main()
