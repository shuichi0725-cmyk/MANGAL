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
    (".cache/madb/metadata101-clean.json", "種1 clean(promoteのpublisher導出が読む正規パス)"),
    (".cache/madb/metadata104.json", "シリーズmaster(2024-11凍結=再DL不要だが build-series が読む)"),
    (".cache/madb/metadata504.json", "作者master(build-series/promote が読む。月次で差替)"),
    ("node_modules/tsx/dist/cli.mjs", "clean-madb-seed.ts の実行系(npm install 済か)"),
    ("scripts/_monthly-distill.py", "オーケストレータ(status/phase1/phase2/run)"),
    ("data/madb-intake-state.yml", "取込マーカーのgit追跡バックアップ"),
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

    # ★clean鮮度 (2026-08 実害: cleanが旧releaseのままpromote→新刊全部publisher (unknown) 1,182頁):
    #   clean(正規パス)が raw より古い = 差し替え漏れ。Phase0時点(=新DL前)は同世代のはず。
    raw_p = os.path.join(ROOT, ".cache/madb/metadata101.json")
    clean_p = os.path.join(ROOT, ".cache/madb/metadata101-clean.json")
    if os.path.exists(raw_p) and os.path.exists(clean_p):
        if os.path.getmtime(clean_p) < os.path.getmtime(raw_p):
            missing.append(("metadata101-clean.json", "raw より古い=clean差し替え漏れ(publisher unknown事故の入口)"))
            print("  FAIL metadata101-clean.json が metadata101.json より古い(clean差し替え漏れ)")
        else:
            print("  OK   metadata101-clean.json 鮮度(raw以上)")

    # ★マーカー整合 (2026-09-02): .cache は消える → git追跡の data/madb-intake-state.yml と食い違えば止める
    #   (.cache 消失後に古い yml(1.2.16)を信じて再取込→大量churn、の入口を塞ぐ。両方 phase2 が書く)
    import re as _re
    mk_p = os.path.join(ROOT, ".cache/madb-last-release.txt")
    st_p = os.path.join(ROOT, "data/madb-intake-state.yml")
    if os.path.exists(mk_p) and os.path.exists(st_p):
        mk = open(mk_p, encoding="utf-8").read().strip()
        m = _re.search(r'^\s*release_tag:\s*"?([0-9][0-9.]*)"?', open(st_p, encoding="utf-8").read(), _re.M)
        st = m.group(1) if m else None
        if st != mk:
            missing.append(("マーカー不一致", f".cache={mk} / data/madb-intake-state.yml={st}(台帳 data/madb-distill-ledger.jsonl で正を確認)"))
            print(f"  FAIL マーカー不一致: .cache/madb-last-release.txt={mk} ≠ data/madb-intake-state.yml={st}")
        else:
            print(f"  OK   マーカー整合 (.cache = intake-state.yml = {mk})")

    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8")
    _lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    dirty = [l for l in _lines if not l.startswith("??")]      # tracked の変更/stage = abort
    untracked = [l for l in _lines if l.startswith("??")]      # untracked = 警告のみ(git add -A 禁止)
    if dirty:
        missing.append(("git clean", f"dirty {len(dirty)} 件"))
        print(f"  FAIL git dirty {len(dirty)} 件(Phase0はclean必須): " + " / ".join(l.strip() for l in dirty[:5]))
    else:
        print("  OK   git clean (tracked)")
    if untracked:
        print(f"  WARN untracked {len(untracked)} 件(混ぜない= git add -A を使わない): " + " / ".join(l.strip() for l in untracked[:5]))

    if missing:
        print(f"\n★Phase0 不成立({len(missing)}件欠け)。蒸留できない=ユーザ報告して終了(自動fallback禁止):")
        for rel, desc in missing:
            print(f"  - {rel}: {desc}")
        sys.exit(1)
    print("\n→ Phase0 全通過。次=Phase1 差分report(MADB latest release比較)→ユーザGoサイン待ち。")


if __name__ == "__main__":
    main()
