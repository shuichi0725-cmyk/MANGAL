#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月次蒸留 Phase0 前提確認 (2026-07-10 弱モデル耐性: 散文チェックリストの機械化)。

CLAUDE.md「月次蒸留 protocol」Phase0 の実体。1つでも欠け= exit 1 =「対象Xが無いので
蒸留できない」とユーザ報告して終了(自動fallback/自動作成はしない)。

  python scripts/_monthly-phase0.py
"""
import os, sys, subprocess

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = [
    (".cache/madb-last-release.txt", "前回取込 MADB release tag"),
    (".cache/db-v2.sqlite", "種2 現行DB"),
    ("data/seeds/series-supplement-v2.yml", "種3 現行(AI fill蓄積)"),
    (".cache/madb/metadata101.json", "種1 raw(MADB dump。CLAUDE.md表記cm101.csvの実体はこれ)"),
    ("data/seed/mangaka.csv", "漫画家マスター"),
    ("scripts/clean-madb-seed.ts", "パイプライン(1)"),
    ("scripts/_build-series-v2.py", "パイプライン(2)"),
    ("scripts/_populate-v2.py", "パイプライン(3)"),
    ("scripts/_distill-incremental-merge.py", "パイプライン(4)=安全純粋追加"),
    ("scripts/intake.py", "派生層+matcher+promote runner"),
]


def main():
    os.chdir(ROOT)
    missing = []
    for rel, desc in REQUIRED:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            extra = ""
            if rel.endswith("madb-last-release.txt"):
                extra = f" [{open(p, encoding='utf-8').read().strip()[:40]}]"
            print(f"  OK   {rel} ({desc}){extra}")
        else:
            missing.append((rel, desc))
            print(f"  FAIL {rel} ({desc}) が無い")

    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8")
    dirty = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if dirty:
        missing.append(("git clean", f"dirty {len(dirty)} 件"))
        print(f"  FAIL git dirty {len(dirty)} 件(Phase0はclean必須): " + " / ".join(l.strip() for l in dirty[:5]))
    else:
        print("  OK   git clean")

    if missing:
        print(f"\n★Phase0 不成立({len(missing)}件欠け)。蒸留できない=ユーザ報告して終了(自動fallback禁止):")
        for rel, desc in missing:
            print(f"  - {rel}: {desc}")
        sys.exit(1)
    print("\n→ Phase0 全通過。次=Phase1 差分report(MADB latest release比較)→ユーザGoサイン待ち。")


if __name__ == "__main__":
    main()
