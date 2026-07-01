#!/usr/bin/env python3
"""targeted 反映 = seed変更を「変わったページだけ」高速に本番+テストへ反映。

★フルpromote(66k・~110分)+cover stage(~52分)+全索引 の3時間コースを、
  変更N頁だけなら数分に。 per-case修正(edition-override/種4/drop/title fix)の既定にする。
  フルpromoteは月次蒸留の時だけ。

処理:
  1. --drop の頁を manga.v2 / .preview-data から削除 (内部slugは索引removeへ)
  2. promote --only <changed stems>  (★書影はpromoteに統合済=別cover stage不要)
  3. 索引を --update <changed> --remove <dropped internal slugs> で本番data + .preview-data 両方 増分更新
  4. preview同期: changed頁が.preview-dataに在れば新manga.v2で上書き
  5. --push: git add + commit + push (preview自動デプロイ)

使い方:
  python scripts/_reflect-targeted.py --only golgo-13,tsuribaka-nisshi
  python scripts/_reflect-targeted.py --only yoshida-akimi --drop kawaguchi-kaiji,mizuki-shigeru --push -m "..."

注意:
  --only / --drop は **manga.v2 のファイル名(=SRC slug)**。 slug-override頁もSRC名で指定
  (例: 夜明けは yoshida-akimi。 内部slugは yoake-yoshida2012)。
"""
import os, sys, subprocess, glob, argparse
sys.stdout.reconfigure(encoding="utf-8")
try:
    import yaml
except ImportError:
    yaml = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MV2 = os.path.join(ROOT, "data", "manga.v2")
PV = os.path.join(ROOT, ".preview-data", "manga")
PY = sys.executable

def internal_slug(stem, base):
    p = os.path.join(base, stem + ".yml")
    if not os.path.exists(p) or yaml is None:
        return stem
    try:
        d = yaml.safe_load(open(p, encoding="utf-8"))
        return (d.get("slug") if isinstance(d, dict) else None) or stem
    except Exception:
        return stem

def run(cmd):
    print(f"$ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print(f"  [warn] exit {r.returncode}", flush=True)
    return r.returncode

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="再生成する manga.v2 stem(カンマ区切り)")
    ap.add_argument("--drop", default="", help="削除する manga.v2 stem(カンマ区切り)")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("-m", "--msg", default="targeted反映")
    ap.add_argument("--no-preview", action="store_true", help="preview同期をskip")
    a = ap.parse_args()
    only = [s.strip() for s in a.only.split(",") if s.strip()]
    drop = [s.strip() for s in a.drop.split(",") if s.strip()]
    if not only and not drop:
        print("--only か --drop を指定", file=sys.stderr); sys.exit(1)

    # 1. drop頁削除 (内部slug回収→索引remove用)
    remove_slugs = []
    for st in drop:
        remove_slugs.append(internal_slug(st, MV2))
        for base in (MV2, PV):
            fp = os.path.join(base, st + ".yml")
            if os.path.exists(fp):
                os.remove(fp); print(f"  削除 {os.path.relpath(fp, ROOT)}", flush=True)

    # 2. promote --only (書影統合済)
    if only:
        run([PY, "scripts/_promote-bulk-v2.py", "--only", ",".join(only)])

    # 3. 索引 増分更新 (本番 data/ + preview)
    upd = ",".join(only)
    rem = ",".join(remove_slugs)
    idx_data = [PY, "scripts/_build-list-index.py", "data/manga.v2", "data"]
    if only: idx_data += ["--update", upd]
    if remove_slugs: idx_data += ["--remove", rem]
    if only or remove_slugs: run(idx_data)

    # 4. preview同期 (changed頁が.preview-dataに在れば新版で上書き) + preview索引
    pv_changed = []
    if not a.no_preview:
        import shutil
        for st in only:
            src = os.path.join(MV2, st + ".yml"); dst = os.path.join(PV, st + ".yml")
            if os.path.exists(dst) and os.path.exists(src):
                shutil.copyfile(src, dst); pv_changed.append(st)
        if pv_changed or remove_slugs:
            idx_pv = [PY, "scripts/_build-list-index.py", ".preview-data/manga", ".preview-data"]
            if pv_changed: idx_pv += ["--update", ",".join(pv_changed)]
            if remove_slugs: idx_pv += ["--remove", rem]
            run(idx_pv)

    print(f"\n=== targeted反映 完了 === 再生成{len(only)} / drop{len(drop)} / preview同期{len(pv_changed)}", flush=True)

    # 5. push
    if a.push:
        run(["git", "add", ".preview-data", "data/manga-catch-index.json"])
        run(["git", "commit", "-q", "-m", a.msg])
        run(["git", "push"])

if __name__ == "__main__":
    main()
