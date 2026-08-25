# -*- coding: utf-8 -*-
"""月次蒸留 postflight = ★成功判定の機械化 (2026-08-26 新設。Phase0と対になる完了側)。

旧: skillの「成功判定」は全部AIの自己申告(散文)=忘れると死ぬ。以後この script の
exit 0 + 出力数値の引用が完了主張の条件(弱モデル耐性=_monthly-phase0.py と同思想)。

検査(FAILが1つでも exit 1 = 完了していない):
  1. seed lint (_check-seeds.py: parse死/台帳減少/種4フィールド)
  2. manga.v2 頁数 ≥ 66,000 (激減=事故)
  3. ISBN消失監視 (_audit-isbn-loss.py: 理由なし消失0)
  4. 種4-auto台帳 ≥ baseline (全消し/誤退役)
  5. publisher (unknown) ≤ baseline (clean差し替え漏れの下流症状)
  6. solo-truncated: 頁化した月(genpages-last.json が14日以内)は新規頁の途中巻断片=0

  python scripts/_monthly-postflight.py
"""
import glob
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
fails = []


def ok(msg):
    print(f"  OK   {msg}")


def fail(msg, hint=""):
    fails.append(msg)
    print(f"  FAIL {msg}")
    if hint:
        print(f"       → {hint}")


def main() -> None:
    os.chdir(ROOT)
    # 1. seed lint
    r = subprocess.run([PY, "scripts/_check-seeds.py"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode == 0:
        ok("seed lint (parse/台帳減少/種4フィールド)")
    else:
        fail("seed lint NG", (r.stdout or "").strip().splitlines()[-1] if r.stdout else "")

    # 2. manga.v2 頁数
    n = len(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")))
    if n >= 66_000:
        ok(f"manga.v2 = {n:,} 頁 (≥66k)")
    else:
        fail(f"manga.v2 = {n:,} 頁 < 66,000 (激減=promote事故疑い)")

    # 3. ISBN消失
    r = subprocess.run([PY, "scripts/_audit-isbn-loss.py"], capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "").strip().splitlines()
    if r.returncode == 0:
        ok(f"ISBN消失監視 ({out[0] if out else 'ok'})")
    else:
        fail("ISBN消失: 理由なし消失あり(実在する巻を黙って消した疑い)",
             "docs/production-diagnostics/isbn-loss.tsv を1件ずつ裁定(復活 or 台帳に理由)")

    # 4/5. baseline 比較
    bp = os.path.join(ROOT, "data", "seeds", "preflight-baselines.json")
    base = json.load(io.open(bp, encoding="utf-8")) if os.path.exists(bp) else {}
    import yaml
    try:
        s4 = len((yaml.safe_load(io.open(os.path.join(ROOT, "data", "seeds",
                  "volumes-supplement-auto.yml"), encoding="utf-8")) or {}).get("volumes") or [])
    except Exception:
        s4 = -1
    b4 = base.get("seed4_auto_volumes")
    if s4 < 0:
        fail("種4-auto が読めない(parse死)")
    elif b4 is not None and s4 < b4:
        fail(f"種4-auto台帳が減少 {b4} → {s4} (全消し/誤退役の疑い)")
    else:
        ok(f"種4-auto = {s4} 巻 (基準 {b4})")

    unk = 0
    for f in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        for ln in open(f, encoding="utf-8"):
            if ln.startswith("publisher:"):
                if "(unknown)" in ln:
                    unk += 1
                break
    bu = base.get("publisher_unknown")
    if bu is not None and unk > bu:
        fail(f"publisher (unknown) 増加 {bu} → {unk}", "cleanの正規パス差し替え漏れを疑う(月次skill罠)")
    else:
        ok(f"publisher (unknown) = {unk} (基準 {bu})")

    # 6. solo-truncated (頁化した月のみブロッキング)
    r = subprocess.run([PY, "scripts/_audit-solo-truncated.py"], capture_output=True, text=True, encoding="utf-8")
    tsv = os.path.join(ROOT, "docs", "production-diagnostics", "solo-truncated.tsv")
    tsv_slugs = set()
    if os.path.exists(tsv):
        for i, ln in enumerate(io.open(tsv, encoding="utf-8")):
            if i and ln.strip():
                parts = ln.split("\t")
                if len(parts) > 1:
                    tsv_slugs.add(parts[1])
    gp = os.path.join(ROOT, ".cache", "torikoboshi", "genpages-last.json")
    if os.path.exists(gp) and time.time() - os.path.getmtime(gp) < 14 * 86400:
        made = set((json.load(io.open(gp, encoding="utf-8")) or {}).get("made") or [])
        hit = sorted(made & tsv_slugs)
        if hit:
            fail(f"新規頁に途中巻断片 {len(hit)} 頁: {', '.join(hit[:6])}",
             "skill monthly-distill 6b の裁定に戻る(彼岸島型/分裂/コンビニ断片)")
        else:
            ok(f"新規頁の途中巻断片 0 (頁化 {len(made)} 頁 / 全体flag {len(tsv_slugs)})")
    else:
        ok(f"solo-truncated 全体flag {len(tsv_slugs)} (今月は頁化なし=情報のみ)")

    print(f"\n結果: FAIL {len(fails)}")
    if fails:
        print("★月次蒸留は完了していない。上のFAILを直す(成功判定=このscriptの exit 0)。")
        sys.exit(1)
    print("→ postflight全通過。skillの報告に上の数値を引用して完了主張してよい。")


if __name__ == "__main__":
    main()
