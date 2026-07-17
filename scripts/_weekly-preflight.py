#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週次蒸留 preflight (2026-07-10 弱モデル耐性ハードニング): ビルド開始前の機械ゲート。

散文チェックリスト(skill手順2-3)をscript強制に。FAILが1つでもあれば exit 1 = ビルド開始禁止。

  python scripts/_weekly-preflight.py          # 検査のみ(FAIL項目と直し方を列挙)
  python scripts/_weekly-preflight.py --fix    # 安全に直せる物は直す(junction再作成/stagingコピー)

検査項目 (★2026-07-17 C:完結に全面改訂=ユーザ裁定「ジャンクション全廃・D:はバックアップ倉庫のみ」。
  旧D:junction構成は旧PCのC:満杯が理由で、新PCはC:856GB空きのため廃止。D:外付けはストールしやすく
  ビルド経路に入れない):
  1. scripts/src/lib/next.config.ts の未コミット変更なし(promote拡張commit漏れ=2026-07-04実害)
  2. next.config.ts staticPageGenerationTimeout=300(無いと重頁3回超過でビルドkill)
  3. ディスク: C:空き30GB+(out/.next 10-15GB + staging ~3GB。ENOSPC=2026-07-05実害)
  4. out/ と .next/ が junctionでない(残骸junctionは--fixで除去。実体dirはそのまま=nextが管理)
  5. staging .cache/proddata: 実体コピー3dir(manga=manga.v2/seeds/art-books)+masters6+索引3本を同期(--fix=robocopy /MIR)
  6. 手順1の生成物鮮度(本番索引が7日超古い=再生成忘れ疑い)=WARN
"""
import os, sys, json, shutil, subprocess, time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, ".cache", "proddata")
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

    # 3. ディスク (★C:のみ=D:はビルド経路から完全排除 2026-07-17)
    try:
        c_free = shutil.disk_usage("C:\\").free / 1e9
        if c_free < 30:
            fail(f"C: 空き {c_free:.1f}GB < 30GB", "out/.next 10-15GB + staging ~3GB 要る")
        else:
            ok(f"C: 空き {c_free:.1f}GB")
    except OSError as e:
        fail(f"ディスク確認不能: {e}")

    # 4. out/.next は junction 禁止 (★残骸junctionがD:を指すとD:ストールに巻き込まれる)
    for name in ("out", ".next"):
        p = os.path.join(ROOT, name)
        if is_junction(p):
            if fix:
                os.rmdir(p)   # junction自体のみ除去(再帰しない)
                ok(f"{name}/ 残骸junction除去(以後C:実体でnextが自動作成)")
            else:
                fail(f"{name}/ が junction({os.readlink(p)})", "--fix で除去(C:完結方針)")
        else:
            ok(f"{name}/ = {'C:実体dir' if os.path.exists(p) else '無し(ビルドが作る)'}")

    # 5. staging同期 (★実体コピー。junction不使用)
    os.makedirs(STAGE, exist_ok=True)
    for sub, src_name in (("manga", os.path.join("data", "manga.v2")),
                          ("seeds", os.path.join("data", "seeds")),
                          ("art-books", os.path.join("data", "art-books"))):
        sp, dp = os.path.join(ROOT, src_name), os.path.join(STAGE, sub)
        if not os.path.isdir(sp):
            fail(f"{src_name} が無い")
            continue
        if fix:
            r2 = subprocess.run(["robocopy", sp, dp, "/MIR", "/NFL", "/NDL", "/NJH", "/NJS", "/R:2", "/W:2"],
                                capture_output=True, text=True)
            if r2.returncode <= 7:   # robocopy 0-7=成功
                ok(f"staging/{sub} 同期(robocopy /MIR ← {src_name})")
            else:
                fail(f"staging/{sub} robocopy失敗 rc={r2.returncode}")
        else:
            n_src = sum(len(f) for _, _, f in os.walk(sp))
            n_dst = sum(len(f) for _, _, f in os.walk(dp)) if os.path.isdir(dp) else 0
            if n_src == n_dst and n_dst > 0:
                ok(f"staging/{sub} 件数一致 {n_dst:,}")
            else:
                fail(f"staging/{sub} 不一致 src={n_src:,} dst={n_dst:,}", "--fix でrobocopy /MIR")
    if True:
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

    # 7. ★索引衛生監査(2026-07-14 新設: cover短縮漏れ/スキーマドリフト/head・alt整合。fail=ビルド禁止)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_audit-index-hygiene.py"), "data"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        ok("索引衛生(cover slim/スキーマ/head/alt) = OK")
    else:
        fail("索引衛生NG", (r.stdout or "") + (r.stderr or ""))

    print(f"\n結果: FAIL {len(fails)} / WARN {len(warns)}")
    if fails:
        print("★ビルド開始禁止。上のFAILを直してから再実行。")
        sys.exit(1)
    print("→ preflight全通過。ビルド開始可:")
    print(f'  $env:MANGAL_DATA_DIR="{STAGE}"; npx next build 2>&1 | Out-File .cache\\weekly-build.log')


if __name__ == "__main__":
    main()
