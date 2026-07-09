#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週次蒸留 finalize (2026-07-10 弱モデル耐性): R2同期後の締めを1本化+ゲート連鎖。

  python scripts/_weekly-finalize.py            # 完了判定→疎通→marker→manifest
  python scripts/_weekly-finalize.py --no-post  # 疎通のcontact POSTをskip

ゲート連鎖(前段greenでないと次に進まない=「できたつもり」防止):
  1. ビルド完了判定: weekly-build.log に「✓ Exporting」+ out/manga ファイル数 ≥ 120,000(≈頁数×2)
  2. sitemap: out/sitemap.xml 存在(手順3.5忘れ検出=WARN)
  3. 疎通確認: _prod-smoke.py 全PASS(FAILなら marker を書かずabort)
  4. marker更新: .cache/prod-deploy-marker.json(diff-deployの基準点)
  5. pages-manifest初期化: _init-pages-manifest.py
markerは1-3が全部通った時だけ書く。途中失敗=markerは前回のまま(diff-deployが安全側に倒れる)。
"""
import json, os, sys, subprocess

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, ".cache", "weekly-build.log")
MARKER = os.path.join(ROOT, ".cache", "prod-deploy-marker.json")
MIN_PAGES = 120_000


def die(msg):
    print(f"★abort: {msg}(markerは書かない=diff-deployは前回基準のまま安全側)")
    sys.exit(1)


def main():
    os.chdir(ROOT)
    # 1. ビルド完了判定
    if not os.path.exists(LOG):
        die(f"{os.path.relpath(LOG, ROOT)} が無い(ビルドを回していない?)")
    log = open(LOG, encoding="utf-8", errors="replace").read()
    if "Export encountered" in log or "Build error" in log:
        die("build logにエラー(Export encountered/Build error)。ログを調査")
    if "Exporting" not in log:
        die("build logに『✓ Exporting』が無い=ビルド未完了")
    out_manga = os.path.join(ROOT, "out", "manga")
    if not os.path.isdir(out_manga):
        die("out/manga が無い")
    n = sum(1 for _ in os.scandir(out_manga))
    if n < MIN_PAGES:
        die(f"out/manga = {n:,} < {MIN_PAGES:,}(欠損ビルド疑い。頁数×2≈132kが正常)")
    print(f"  OK   ビルド完了(out/manga {n:,} files・log正常)")

    # 2. sitemap
    if os.path.exists(os.path.join(ROOT, "out", "sitemap.xml")):
        print("  OK   sitemap.xml あり")
    else:
        print("  WARN sitemap.xml が無い(手順3.5 _gen-sitemap.py を忘れていないか)")

    # 3. 疎通(全PASSでないと先に進まない)
    args = [sys.executable, os.path.join(ROOT, "scripts", "_prod-smoke.py")]
    if "--no-post" in sys.argv:
        args.append("--no-post")
    r = subprocess.run(args)
    if r.returncode != 0:
        die("疎通確認にFAILあり")

    # 4. marker
    h = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if not h:
        die("git rev-parse HEAD 失敗")
    json.dump({"code_commit": h, "data_commit": h, "note": "週次蒸留"}, open(MARKER, "w"), indent=1)
    print(f"  OK   marker更新: {h[:12]}")

    # 5. pages-manifest
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_init-pages-manifest.py")])
    if r.returncode != 0:
        die("_init-pages-manifest.py 失敗(markerは書いたがmanifest欠け=diff-deployが過剰検出する。再実行を)")
    print("  OK   pages-manifest初期化")
    print("\n→ 週次蒸留finalize完了(marker+manifest確定。以後の差分反映はこの時点が基準)")


if __name__ == "__main__":
    main()
