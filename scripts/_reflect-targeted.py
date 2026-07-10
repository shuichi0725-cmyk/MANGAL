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

    # 2.4 ★edition-canonical警告: canonical結線slug(golgo/釣りバカ等)は edition-overrides を
    #     直しても canonical が後勝ちで無効(2026-07-01の実事故)。修正先を間違えていないか警告。
    _canon_dir = os.path.join(ROOT, "data", "seeds", "edition-canonical")
    if os.path.isdir(_canon_dir):
        _canon = {os.path.splitext(f)[0] for f in os.listdir(_canon_dir) if f.endswith(".yml")}
        for st in only:
            if st in _canon or internal_slug(st, MV2) in _canon:
                print(f"  ★注意: {st} は edition-canonical 結線slug = 版/巻/ISBN修正は "
                      f"data/seeds/edition-canonical/{st}.yml が正(edition-overridesは上書きされ無効)", flush=True)

    # 2.5 ★検証ゲート(=Zod相当のquickチェック。落ちる頁をpush前に検出=検索404の再発防止)
    import re as _re
    _DATE = _re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
    _errs = []
    for st in only:
        fp = os.path.join(MV2, st + ".yml")
        if not os.path.exists(fp):
            _errs.append(f"{st}: promote後にファイル無し(SRC stem誤り?)"); continue
        try:
            d = yaml.safe_load(open(fp, encoding="utf-8"))
        except Exception as e:
            _errs.append(f"{st}: YAML parse失敗 {e}"); continue
        if not d.get("slug"): _errs.append(f"{st}: slug欠落")
        if not d.get("title"): _errs.append(f"{st}: title欠落")
        if not d.get("title_kana"): _errs.append(f"{st}: title_kana欠落")
        # ★著者role必須(Zod AuthorSchema)。eov手書きでrole忘れ→ビルドskip404の実害(ポケスペ 2026-07-11)
        _ROLES = {"writer", "artist", "writer_artist", "editor"}
        for fld in ("authors", "original_authors"):
            for a in (d.get(fld) or []):
                if not isinstance(a, dict) or a.get("role") not in _ROLES:
                    _errs.append(f"{st}: {fld}にrole欠落/不正={a!r}")
        for e in (d.get("editions") or []):
            for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]:
                for v in vs:
                    n = v.get("number")
                    if not (isinstance(n, int) and n >= 1):
                        _errs.append(f"{st}: 不正number={n!r}")
                    rd = v.get("release_date")
                    if rd is not None and not _DATE.match(str(rd)):
                        _errs.append(f"{st}: 不正release_date={rd!r}")
                    ib = v.get("isbn13")
                    if ib is not None and len(str(ib)) != 13:
                        _errs.append(f"{st}: 不正isbn13={ib!r}")
    if _errs:
        print("\n★検証ゲートNG(push中止・修正してから再実行):", file=sys.stderr)
        for x in _errs[:20]: print(f"  {x}", file=sys.stderr)
        sys.exit(2)
    if only:
        print(f"  検証ゲートOK({len(only)}頁: slug/title/kana/number/date/isbn)", flush=True)

    # 3. 索引 増分更新 (本番 data/ + preview)
    # ★slug変更(slug-override)検知: 内部slugがSRC stemと違う頁は、旧stem名の索引エントリが
    #   残留し二重表示になる(SHERLOCK sherlock-ooinaru-game→sherlock事故 2026-07-08)。
    #   内部slug≠stem の stem を remove に追加し旧エントリを purge。
    for st in only:
        isl = internal_slug(st, MV2)
        if isl != st and st not in remove_slugs:
            remove_slugs.append(st)
            print(f"  slug変更検知: {st} → {isl} (旧slug索引purge)", flush=True)
    upd = ",".join(only)
    rem = ",".join(remove_slugs)
    idx_data = [PY, "scripts/_build-list-index.py", "data/manga.v2", "data"]
    if only: idx_data += ["--update", upd]
    if remove_slugs: idx_data += ["--remove", rem]
    if only or remove_slugs: run(idx_data)

    # 4. preview同期 (changed頁が.preview-dataに在れば新版で上書き) + preview索引
    #    ★内部slug≠SRC名の罠対応: preview側ファイル名はSRC名/内部slug名の両方があり得る→両方試す
    pv_changed = []
    if not a.no_preview:
        import shutil
        for st in only:
            src = os.path.join(MV2, st + ".yml")
            if not os.path.exists(src):
                continue
            islug = internal_slug(st, MV2)
            for dst_name in dict.fromkeys([st, islug]):  # 順序保持dedup
                dst = os.path.join(PV, dst_name + ".yml")
                if os.path.exists(dst):
                    shutil.copyfile(src, dst); pv_changed.append(dst_name); break
        if pv_changed or remove_slugs:
            idx_pv = [PY, "scripts/_build-list-index.py", ".preview-data/manga", ".preview-data"]
            if pv_changed: idx_pv += ["--update", ",".join(pv_changed)]
            if remove_slugs: idx_pv += ["--remove", rem]
            run(idx_pv)

    print(f"\n=== targeted反映 完了 === 再生成{len(only)} / drop{len(drop)} / preview同期{len(pv_changed)}", flush=True)

    # 5. push (★seed変更(edition-overrides/種4/slug等)も含める=反映の source も永続化)
    if a.push:
        # ★統合台帳を自動集約(数秒)=「節目で手動」だと忘れて台帳が死ぬ、の恒久対策
        run([PY, "scripts/_manifest-consolidate-ops.py"])
        # ★slug-aliases/_redirects/主要索引も必ずadd(per-case修正で毎回触るのに漏れ→301切れ+版タブ消失事故 2026-07-08)
        run(["git", "add", ".preview-data", "data/manga-catch-index.json", "data/seeds",
             "data/slug-aliases.yml", "public/_redirects",
             "data/manga-list-index.json", "data/manga-search-index.json"])
        run(["git", "commit", "-q", "-m", a.msg])
        run(["git", "push"])

if __name__ == "__main__":
    main()
