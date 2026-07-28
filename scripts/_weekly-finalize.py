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
    # ★PowerShell の Out-File は既定で **UTF-16LE(BOM付き)** を書く(PS 5.1)。
    #   utf-8固定で読むと本文が「?」だらけになり「✓ Exporting」が見つからず、
    #   ★**ビルドは成功しているのに finalize が abort する**(2026-07-27 実害)。
    #   BOM を見て復号を切り替える(utf-16 → utf-8-sig → utf-8 の順)。
    _raw = open(LOG, "rb").read()
    for _enc in ("utf-16", "utf-8-sig", "utf-8"):
        if _enc == "utf-16" and not _raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            continue
        try:
            log = _raw.decode(_enc, errors="replace")
            break
        except Exception:
            continue
    else:
        log = _raw.decode("utf-8", errors="replace")
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

    # 1.5 ★索引⊆生成頁の実測照合(2026-07-29 ユーザ発見「作品数がズレてる」の恒久ゲート):
    #   一覧索引に載るslugのHTMLが out/manga に無い=「検索に出るのに404」。過去3回再発した型
    #   ([[search_404_build_skip_validation]])なので、件数でなく集合差そのものをFAIL条件にする。
    _idx_p = os.path.join(ROOT, "data", "manga-list-index.json")
    _idx = json.load(open(_idx_p, encoding="utf-8"))
    _si = _idx["f"].index("slug")
    _out_slugs = {f[:-5] for f in os.listdir(out_manga) if f.endswith(".html")}
    _missing = sorted({str(r[_si]) for r in _idx["d"]} - _out_slugs)
    if _missing:
        die(f"索引に居るのに未生成 {len(_missing)}頁(=検索に出るのに404): {_missing[:8]}"
            f"{' …' if len(_missing) > 8 else ''}(ビルドskipと索引ガードの不整合。両方を揃えてから再実行)")
    print(f"  OK   索引⊆生成頁(索引 {len(_idx['d']):,} 行すべてHTMLあり)")

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
