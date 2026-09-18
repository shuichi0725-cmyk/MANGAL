#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""週次 手順3.5 = ビルド後・R2同期前にやること一式(2026-09-18 新設)。

  python scripts/_weekly-postbuild.py        # sitemap生成 → 配信HTMLの中身ゲート
  python scripts/_weekly-postbuild.py --no-gate   # ゲートを飛ばす(緊急時のみ・理由を残すこと)

★なぜ1本にまとめたか(2026-09-18 実地で判明した穴):
  `_check-ssr-content.py`(配信HTMLの中身ゲート)は docstring に「週次preflightで回す」と
  書いてありながら、実際に呼んでいるのは `_monthly-distill.py` の DETECTORS **だけ**だった。
  = **本番へ出す唯一の定期ルートである週次を、この番人は一度も通っていなかった**。
  実害: /tokushu ほか4コーナーが「読み込み中…」だけの空HTMLで公開され続けた。

★なぜ preflight ではなく「ここ」なのか:
  preflight は**ビルドの前**に走るので、out/ は前回のビルド = 今から直す物を見て止めてしまう。
  ここ(build後・sync前)なら **これから配信する実物**を見られて、かつ**まだ上げていない**。
  ([[shell_wiring_gates]] の検査4が WARN 止まりなのと同じ理由で、preflight には置けない)

★順序の理由: sitemap を**先**に作る。ゲートで落ちても sitemap の生成やり直しは不要にしておく
  (落ちた時にやることは「頁を直して再ビルド」であって、sitemap の作り直しではない)。

★機能ビルド(MANGAL_FEATURE_BUILD=1)の out/ に対しては使わない。
  out/author が placeholder だけになるため /authors が偽陽性で落ちる(2026-09-18 実測)。
  機能蒸留は `_deploy-feature.py` 側の検査に任せる。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")


def run(script: str, *args: str) -> int:
    print(f"\n=== {script} {' '.join(args)} ===", flush=True)
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), *args]).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-gate", action="store_true", help="中身ゲートを飛ばす(緊急時のみ)")
    a = ap.parse_args()

    if not os.path.isdir(OUT):
        print("★abort: out/ が無い = ビルドしていない。手順3(next build)の後に回す")
        return 2

    # 1. sitemap(先に作る = ゲートで落ちても作り直し不要)
    if run("_gen-sitemap.py") != 0:
        print("\n★abort: sitemap生成に失敗。R2同期に進まないこと")
        return 2

    if a.no_gate:
        print("\n※ --no-gate: 配信HTMLの中身ゲートを飛ばした(理由を作業ログに残すこと)")
        return 0

    # 2. 配信HTMLの中身ゲート(= これから上げる実物を見る最後の機会)
    rc = run("_check-ssr-content.py", "--list")
    if rc != 0:
        print("\n" + "=" * 72)
        print("★中身が空の頁がある = このまま R2 同期すると『Googleに空』の頁を配信する。")
        print("  直し方: その頁がクライアント専用描画になっていないか見る。")
        print("  典型 = client側で日付/乱数/localStorage/useSearchParams を使っており、")
        print("        サーバー描画が fallback(『読み込み中…』)のままHTMLになっている。")
        print("  先例 = /tokushu ほか4コーナー(2026-09-18 是正。lib/cornerData.ts の作法を参照)。")
        print("  直して手順3(next build)からやり直す。sitemapは作成済みなので再生成は不要。")
        print("=" * 72)
        return 1

    print("\n手順3.5 OK = sitemap生成済み・配信HTMLの中身ゲート通過。手順4(R2同期)へ進んでよい")
    return 0


if __name__ == "__main__":
    sys.exit(main())
