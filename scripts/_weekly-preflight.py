#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週次蒸留 preflight (2026-07-10 弱モデル耐性ハードニング): ビルド開始前の機械ゲート。

散文チェックリスト(skill手順2-3)をscript強制に。FAILが1つでもあれば exit 1 = ビルド開始禁止。

  python scripts/_weekly-preflight.py          # 検査のみ(FAIL項目と直し方を列挙)
  python scripts/_weekly-preflight.py --fix    # 安全に直せる物は直す(junction再作成/stagingコピー)

検査項目:
  1. scripts/src/lib/next.config.ts の未コミット変更なし(promote拡張commit漏れ=2026-07-04実害)
  2. next.config.ts staticPageGenerationTimeout=300(無いと重頁3回超過でビルドkill)
  3. ディスク: D:空き20GB+ / C:空き5GB+(ENOSPC=2026-07-05実害)
  4. out/ と .next/ が D:\\mangal-cache へのjunction(--fixで再作成。実体dirは絶対に消さない=abort)
  5. staging D:\\mangal-cache\\proddata: junction3本(manga/seeds/art-books)+masters6+索引3本がdata/と同期
  6. 手順1の生成物鮮度(本番索引が7日超古い=再生成忘れ疑い)=WARN
"""
import os, sys, json, shutil, subprocess, time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = r"D:\mangal-cache\proddata"
OUT_TARGET = r"D:\mangal-cache\weekly-out"
NEXT_TARGET = r"D:\mangal-cache\next-build"
MASTERS = ["demographics.yml", "genres.yml", "magazines.yml",
           "publisher-aliases.yml", "publishers.yml", "slug-aliases.yml"]
INDEXES = ["manga-list-index.json", "manga-search-index.json", "manga-catch-index.json"]

fails, warns = [], []


def ok(msg):
    print(f"  OK   {msg}")


def fail(msg, how=""):
    fails.append(msg)
    print(f"  FAIL {msg}" + (f"\n       → {how}" if how else ""))


def warn(msg):
    warns.append(msg)
    print(f"  WARN {msg}")


def is_junction(path):
    try:
        os.readlink(path)
        return True
    except OSError:
        return False


def main():
    fix = "--fix" in sys.argv
    os.chdir(ROOT)

    # 1. コード未コミット
    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8")
    dirty_code = [l for l in (r.stdout or "").splitlines()
                  if l[3:].startswith(("scripts/", "src/", "lib/", "next.config", "package.json"))]
    if dirty_code:
        fail(f"コード未コミット {len(dirty_code)} 件(ビルドに乗るのにgitに無い=diff-deploy基準が壊れる)",
             "commit+pushしてから: " + " / ".join(l.strip() for l in dirty_code[:5]))
    else:
        ok("scripts/src/lib/next.config = コミット済")

    # 2. timeout設定
    try:
        cfg = open(os.path.join(ROOT, "next.config.ts"), encoding="utf-8").read()
        if "staticPageGenerationTimeout" in cfg and "300" in cfg:
            ok("staticPageGenerationTimeout=300")
        else:
            fail("staticPageGenerationTimeout=300 が next.config.ts に無い", "無いと重頁が3回超過でビルドkill(2026-07-05)")
    except OSError:
        fail("next.config.ts が読めない")

    # 3. ディスク
    try:
        d_free = shutil.disk_usage("D:\\").free / 1e9
        c_free = shutil.disk_usage("C:\\").free / 1e9
        if d_free < 20:
            fail(f"D: 空き {d_free:.1f}GB < 20GB", "out/.next で10-15GB要る")
        else:
            ok(f"D: 空き {d_free:.1f}GB")
        if c_free < 5:
            warn(f"C: 空き {c_free:.1f}GB < 5GB(junction運用なら可だが余裕なし)")
    except OSError as e:
        fail(f"ディスク確認不能: {e}")

    # 4. out/.next junction (★実体dirは消さない=中身があるrmdirは失敗する仕様を安全弁に使う)
    for name, target in (("out", OUT_TARGET), (".next", NEXT_TARGET)):
        p = os.path.join(ROOT, name)
        if is_junction(p) and not fix:
            ok(f"{name}/ = junction ({os.readlink(p)})")
            continue
        if not fix:
            if os.path.exists(p):
                fail(f"{name}/ が実体dir(C:直ビルドになりENOSPC危険)", f"--fix で再作成(実体に中身があればabortする)")
            else:
                fail(f"{name}/ junction が無い", "--fix で作成")
            continue
        # --fix: rmdir(linkと空dirのみ消せる。実体+中身は失敗→abort=絶対に再帰削除しない)
        if os.path.exists(p) or is_junction(p):
            r2 = subprocess.run(["cmd", "/c", "rmdir", p], capture_output=True, text=True)
            if os.path.exists(p):
                fail(f"{name}/ が中身のある実体dir=自動では消さない",
                     f"中身を確認して手動退避(robocopy /E /MOVE)後に再実行: {p}")
                continue
        os.makedirs(target, exist_ok=True)
        r3 = subprocess.run(["cmd", "/c", "mklink", "/J", p, target], capture_output=True, text=True)
        if is_junction(p):
            ok(f"{name}/ junction 再作成 → {target}")
        else:
            fail(f"{name}/ junction 作成失敗: {(r3.stderr or r3.stdout).strip()[:120]}")

    # 5. staging同期
    if not os.path.isdir(STAGE):
        fail(f"staging が無い: {STAGE}")
    else:
        for j in ("manga", "seeds", "art-books"):
            jp = os.path.join(STAGE, j)
            if os.path.isdir(jp):
                ok(f"staging/{j} あり")
            else:
                fail(f"staging/{j} が無い(junction切れ)", f"cmd /c mklink /J {jp} <data側実体>")
        stale = []
        for f in MASTERS + INDEXES:
            src, dst = os.path.join(ROOT, "data", f), os.path.join(STAGE, f)
            if not os.path.exists(src):
                fail(f"data/{f} が無い(手順1の生成漏れ?)")
                continue
            if (not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst) + 1
                    or os.path.getsize(src) != os.path.getsize(dst)):
                if fix:
                    shutil.copy2(src, dst)
                    ok(f"staging同期: {f}")
                else:
                    stale.append(f)
        if stale:
            fail(f"staging未同期 {len(stale)} 件: {', '.join(stale)}", "--fix でコピー")
        elif not fix:
            ok("staging masters+索引 = 同期済")

    # 6. 生成物鮮度(WARN)
    idx = os.path.join(ROOT, "data", "manga-list-index.json")
    if os.path.exists(idx):
        age = (time.time() - os.path.getmtime(idx)) / 86400
        if age > 7:
            warn(f"本番索引が {age:.0f} 日前(手順1の再生成を忘れていないか)")
        else:
            ok(f"本番索引 鮮度 {age:.1f} 日")

    print(f"\n結果: FAIL {len(fails)} / WARN {len(warns)}")
    if fails:
        print("★ビルド開始禁止。上のFAILを直してから再実行。")
        sys.exit(1)
    print("→ preflight全通過。ビルド開始可:")
    print(r'  $env:MANGAL_DATA_DIR="D:\mangal-cache\proddata"; npx next build 2>&1 | Out-File .cache\weekly-build.log')


if __name__ == "__main__":
    main()
