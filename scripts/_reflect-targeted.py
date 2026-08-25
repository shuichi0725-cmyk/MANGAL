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
    ap.add_argument("--allow-loss", dest="allow_loss", action="store_true",
                    help="巻/版が減る反映を承認してpushする(既定は減少検出でpush中止=silent lossの防止)")
    ap.add_argument("--commit-only", dest="commit_only", action="store_true",
                    help="add+commitまでで止め、pushしない(日次/週次で途中反映を溜め、最後に1回だけpush=追いpush回避)")
    ap.add_argument("-m", "--msg", default="targeted反映")
    ap.add_argument("--no-preview", action="store_true", help="preview同期をskip")
    a = ap.parse_args()
    only = [s.strip() for s in a.only.split(",") if s.strip()]
    drop = [s.strip() for s in a.drop.split(",") if s.strip()]
    if not only and not drop:
        print("--only か --drop を指定", file=sys.stderr); sys.exit(1)

    # 0. ★反映前スナップショット(2026-08-08 新設): 対象頁の ISBN集合/巻数 を控える。
    #    狙い= **実在する巻を黙って消す事故**の検出。ユーザは「不自然な数字」には気付けるが
    #    「本当にある物が無い」には**構造的に気付けない**(2026-08-08 ユーザ裁定)。
    #    増える分は無害なので通し、**減る分だけ**を反映後に必ず列挙する。
    def _snapshot(stems):
        snap = {}
        for _st in stems:
            _fp = os.path.join(MV2, _st + ".yml")
            if not os.path.exists(_fp):
                continue
            try:
                _d = yaml.safe_load(open(_fp, encoding="utf-8")) or {}
            except Exception:
                continue
            _is, _lbl = set(), set()
            for _e in (_d.get("editions") or []):
                _lbl.add(str(_e.get("label") or _e.get("type")))
                for _vs in [_e.get("volumes") or []] + [_vv.get("volumes") or [] for _vv in (_e.get("versions") or [])]:
                    for _v in _vs:
                        if _v.get("isbn13"):
                            _is.add(str(_v["isbn13"]))
            snap[_st] = {"isbn": _is, "editions": _lbl,
                         "vols": sum(len(_e.get("volumes") or []) for _e in (_d.get("editions") or []))}
        return snap
    _before = _snapshot(only)

    # 1. drop頁削除 (内部slug回収→索引remove用)
    remove_slugs = []
    for st in drop:
        remove_slugs.append(internal_slug(st, MV2))
        for base in (MV2, PV):
            fp = os.path.join(base, st + ".yml")
            if os.path.exists(fp):
                os.remove(fp); print(f"  削除 {os.path.relpath(fp, ROOT)}", flush=True)

    # 1.5 ★canonicalゲート(2026-08-20 新設): 対象に edition-canonical 結線slugが含まれる時は
    #     番人(_check-edition-canonical.py)を先に通す。★壊れたcanonicalはpromoteが
    #     `except: continue` で無警告skipし、reflectは「成功」と表示する(実験人形
    #     ダミー・オスカーで実踏)ため、promoteに入る前に止めるのが唯一確実な位置。
    #     連載中の続巻取りこぼし(検査7)もここで鳴る。
    _canon_dir0 = os.path.join(ROOT, "data", "seeds", "edition-canonical")
    _gate_slugs = []
    if only and os.path.isdir(_canon_dir0):
        for st in only:
            for cand in dict.fromkeys([st, internal_slug(st, MV2)]):
                if os.path.exists(os.path.join(_canon_dir0, cand + ".yml")):
                    _gate_slugs.append(cand)
    if _gate_slugs:
        print(f"  canonicalゲート: {len(_gate_slugs)}slug を番人で検査", flush=True)
        rc = run([PY, "scripts/_check-edition-canonical.py", "--slugs", ",".join(_gate_slugs)])
        if rc != 0:
            print("★canonicalゲートNG(反映中止): 上のNGを直してから再実行。"
                  "壊れたまま進めるとpromoteが無警告skipし頁が直らない/巻が消える", file=sys.stderr)
            sys.exit(4)

    # 1.7 ★seed lintゲート(2026-08-26 新設): parse死/純粋追加台帳の減少/種4フィールド不正を
    #     promote前に止める(2スペsilent不着・全消しの汎用番人。~数秒)
    rc = run([PY, "scripts/_check-seeds.py"])
    if rc != 0:
        print("★seed lintゲートNG(反映中止): 上のFAILを直してから再実行。"
              "正当な台帳退役なら _check-seeds.py --allow-shrink を単独実行して確認後、"
              "該当seedをcommitしてから反映する", file=sys.stderr)
        sys.exit(5)

    # 2. promote --only (書影統合済)
    if only:
        run([PY, "scripts/_promote-bulk-v2.py", "--only", ",".join(only)])

    # 2.3 ★減少差分レポート(2026-08-08 新設): 反映で**消えた巻/版**を必ず表示する。
    #     熱愛プリンス誤deny(実在68巻)/ワイルド7の欠落13巻 のような silent loss を目に入れるのが目的。
    #     ★消えること自体は正当な場合もある(版分離で別頁へ移した/非掲載ISBNを除去した)ので止めはしないが、
    #     **--push 時だけは確認を要求**する(--allow-loss で明示承認)。
    _after = _snapshot(only)
    _loss = []
    for _st in only:
        _b, _af = _before.get(_st), _after.get(_st)
        if not _b or not _af:
            continue
        _gone = sorted(_b["isbn"] - _af["isbn"])
        _ged = sorted(_b["editions"] - _af["editions"])
        if _gone or _ged:
            _loss.append((_st, _gone, _ged, _b["vols"], _af["vols"]))
    if _loss:
        print("\n★減少検出(反映で消えた巻/版がある):", file=sys.stderr)
        for _st, _gone, _ged, _bv, _av in _loss:
            print(f"  {_st}: 巻 {_bv} → {_av}", file=sys.stderr)
            if _ged:
                print(f"     消えた版: {', '.join(_ged)}", file=sys.stderr)
            if _gone:
                print(f"     消えたISBN {len(_gone)}件: {', '.join(_gone[:12])}"
                      + (" …" if len(_gone) > 12 else ""), file=sys.stderr)
        print("  → 意図した除去(版分離で別頁へ移設/非掲載ISBN除去)ならそのまま。"
              "★心当たりが無ければ**実在する巻を消している**=止めて調べる", file=sys.stderr)
        if a.push and not a.allow_loss:
            print("  ★--push は中止した。意図した減少なら --allow-loss を付けて再実行", file=sys.stderr)
            sys.exit(3)
    elif only:
        print(f"  減少なし(対象{len(only)}頁: 巻・版とも減っていない)", flush=True)

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
            for _au in (d.get(fld) or []):
                if not isinstance(_au, dict) or _au.get("role") not in _ROLES:
                    _errs.append(f"{st}: {fld}にrole欠落/不正={_au!r}")
        for e in (d.get("editions") or []):
            for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]:
                for v in vs:
                    n = v.get("number")
                    # ★0巻は実在する(前日譚の商業化等。可哀想な君は僕だけの甘やかな傷(0)=楽天題も(0) 2026-07-28実踏)
                    if not (isinstance(n, int) and n >= 0):
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

    # 5. commit(+push) (★seed変更(edition-overrides/種4/slug等)も含める=反映の source も永続化)
    #   --commit-only = pushせずcommitまで(日次/週次で途中反映を溜め、最後に1回だけpush=追いpush回避)。
    if a.push or a.commit_only:
        # ★統合台帳を自動集約(数秒)=「節目で手動」だと忘れて台帳が死ぬ、の恒久対策
        run([PY, "scripts/_manifest-consolidate-ops.py"])
        # ★slug-aliases/_redirects/主要索引も必ずadd(per-case修正で毎回触るのに漏れ→301切れ+版タブ消失事故 2026-07-08)
        # ★manga-alt-index/manga-list-head も索引出力(追跡対象)= addリスト漏れで未commitのまま残る事故
        #   (2026-07-27 日次蒸留で実踏)。list-index/search-index はgitignore(巨大)なので -f せず、
        #   ignored混在で git add が exit 1 を返しても他パスは add 済み = 続行してよい。
        run(["git", "add", ".preview-data", "data/manga-catch-index.json", "data/seeds",
             "data/slug-aliases.yml", "public/_redirects",
             "data/manga-alt-index.json", "data/manga-list-head.json",
             "data/manga-list-index.json"])
        run(["git", "commit", "-q", "-m", a.msg])
        if a.push:
            run(["git", "push"])
        else:
            print("(--commit-only: pushは保留。最後に1回だけ git push する)", flush=True)

if __name__ == "__main__":
    main()
