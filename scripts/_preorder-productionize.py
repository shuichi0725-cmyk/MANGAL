#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「本番化して」= 確認済み予約ドラフトを本番化(preorder-pages恒久)+preview解放(2026-07-09)。

目的(ユーザ): 日次蒸留で溜めた確認済みドラフトを、週次蒸留で本番公開される状態にする。
  ・preorder-pages(git恒久保管庫)へ入れる → フルpromoteが合流読み込み=週次で本番に載る。
  ・data/manga.v2 にも即時データとして書く + 本番索引を増分更新。
  ・**previewから除去してテスト環境を解放**(次の日次蒸留/別作業のため。ユーザ要望)。
  ・増加分ゲートがpreorder-pages題を除外するので、次の日次蒸留で再カウントされない。

流れ: promote-drafts → 本番索引 --update → previewから除去 → preview索引再構築 → (呼出側でcommit+push)
実際のR2ライブ公開は「週次蒸留して」(フルpromote+R2 sync)が担う=ここではしない。

使い方:
  python scripts/_preorder-productionize.py            # preview上の全予約ドラフトを本番化
  python scripts/_preorder-productionize.py --slugs a,b # 指定分のみ
  python scripts/_preorder-productionize.py --keep-preview  # previewに残す(解放しない)
"""
import argparse, glob, json, os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PV = os.path.join(ROOT, ".preview-data", "manga")
PY = sys.executable


def run(cmd):
    print("  $", " ".join(str(c) for c in cmd[2:] if not str(c).startswith(ROOT))[:120])
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", help="対象slug(カンマ区切り)。既定=preview上の全予約ドラフト")
    ap.add_argument("--keep-preview", action="store_true", help="本番化後もpreviewに残す")
    a = ap.parse_args()

    # 1. 対象slug収集(既定=preview上の_preorder_draft付き全部)
    if a.slugs:
        targets = [s.strip() for s in a.slugs.split(",") if s.strip()]
    else:
        targets = []
        for p in sorted(glob.glob(os.path.join(PV, "*.yml"))):
            d = yaml.safe_load(open(p, encoding="utf-8"))
            if d.get("_preorder_draft"):
                targets.append(os.path.basename(p)[:-4])
    if not targets:
        print("本番化対象の予約ドラフトが preview に無い。終了。"); return
    print(f"本番化対象: {len(targets)}件")

    # 2. promote-drafts(preorder-pages + manga.v2 + _preorder_draft除去)
    #    ★slugはファイル渡し(1,000件級でWindowsコマンドライン長制限WinError206になるため 2026-07-14)
    tf = os.path.join(ROOT, ".cache", "preorders", "productionize-targets.txt")
    open(tf, "w", encoding="utf-8").write("\n".join(targets))
    run([PY, os.path.join(ROOT, "scripts", "_preorder-promote-drafts.py"), "--slugs-file", tf])
    promoted = json.load(open(os.path.join(ROOT, ".cache", "preorders", "last-promoted.json"), encoding="utf-8"))
    if not promoted:
        print("promote 0件(衝突/欠落)。終了。"); return
    print(f"promote済み: {len(promoted)}件")

    # 3. 本番索引を増分更新(manga.v2 → data/*-index.json)
    pf = os.path.join(ROOT, ".cache", "preorders", "productionize-promoted.txt")
    open(pf, "w", encoding="utf-8").write("\n".join(promoted))
    run([PY, os.path.join(ROOT, "scripts", "_build-list-index.py"), "data/manga.v2", "data", "--update-file", pf])

    # 4. previewから除去(テスト環境解放) + preview索引再構築
    if not a.keep_preview:
        removed = 0
        for slug in promoted:
            fp = os.path.join(PV, f"{slug}.yml")
            if os.path.exists(fp):
                os.remove(fp); removed += 1
        print(f"previewから除去(解放): {removed}件")
        run([PY, os.path.join(ROOT, "scripts", "_build-list-index.py"), ".preview-data/manga", ".preview-data"])

    print("\n=== 本番化完了 ===")
    print(f"  preorder-pages(恒久): +{len(promoted)}  → 次の『週次蒸留して』で本番R2に公開")
    print(f"  data/manga.v2 + 本番索引: 更新済み")
    print(f"  preview: {'解放(除去)' if not a.keep_preview else '据え置き'}")
    print("  ★次: git add data/seeds/preorder-pages data/manga.v2 data .preview-data && commit && push")
    print(f"  promoted slugs: {','.join(promoted[:12])}{'...' if len(promoted)>12 else ''}")


if __name__ == "__main__":
    main()
