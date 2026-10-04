#!/usr/bin/env python3
"""
版バリアント durability stage: editions-supplement.yml を本番/テストに再適用。
seeded作品は editions を seed の権威版に置換(replace)。flat な版を置くので、後段 regroup が
同(type,巻数)を刷タブに畳む。書影は持たず(coverfill が ISBN で付与)。
intake STAGES の promote 後、regroup の前に走らせる。
使い方: python _apply-editions-supplement.py [mangaDir...]   既定= .preview-data/manga と data/manga.v2
"""
import sys, os, json, time, shutil
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L, CSafeDumper as Dp
except ImportError: from yaml import SafeLoader as L, SafeDumper as Dp
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seeds", "editions-supplement.yml")

def mk_edition(e):
    ed = {"type": e.get("type", "standard"), "label": e.get("label")}
    if e.get("publisher"): ed["publisher"] = e["publisher"]
    if e.get("imprint"): ed["imprint"] = e["imprint"]
    vols = []
    for v in (e.get("volumes") or []):
        vd = {"number": v.get("number"), "asin": None, "isbn13": v.get("isbn13"),
              "cover_url": None, "release_date": v.get("release_date")}
        if v.get("volume_label"): vd["volume_label"] = v["volume_label"]
        vols.append(vd)
    ed["volumes"] = vols
    return ed

CANON_DIR = os.path.join(ROOT, "data", "seeds", "edition-canonical")


def load_works():
    """editions-supplement.yml → {SRC stem: entry}。
    ★edition-canonical/<stem>.yml を持つ作品は除く(= canonical が正本・CLAUDE.md「canonical後勝ち」)。
      この後段は promote の canonical を丸ごと上書きしてしまう: w3 で9冊消失(2026-09-21)/
      うる星の刷タブ「初版カバー/新装版カバー」(7/4 canonical)が seed の古い版に戻り書影44頁が空に(9/22)。"""
    data = yaml.load(open(SEED, encoding="utf-8"), Loader=L) or {}
    works = {w["slug"]: w for w in (data.get("works") or [])}
    canon = sorted(s for s in works if os.path.exists(os.path.join(CANON_DIR, s + ".yml")))
    if canon:
        print(f"  canonical 優先で版seedを使わない: {canon}", flush=True)
    return {s: w for s, w in works.items() if s not in canon}


def apply_work(fp, w, bak_dir=None, bak_name=None, cover_for=None):
    """1作分の版seedを yml に適用する(intake 後段 edisup と promote --only の共通実体)。
    replace=True は editions を seed の版へ置換、False は label の無い版だけ追加。
    その後 _regroup-versions.py で同(type,巻数)を刷タブに畳む。
    cover_for(isbn13)->url を渡すと、畳んだ後に空の書影を埋める
    (★mk_edition は cover_url=None で置くため。intake は後段 coverfill が埋めるので渡さない)。
    戻り値 = 適用したか(seedに版が無い/yml が dict でない時は False)。"""
    doc = yaml.load(open(fp, encoding="utf-8"), Loader=L)
    if not isinstance(doc, dict): return False
    new_eds = [mk_edition(e) for e in (w.get("editions") or [])]
    if not new_eds: return False
    if w.get("replace", True):
        if bak_dir:
            os.makedirs(bak_dir, exist_ok=True)
            shutil.copy2(fp, os.path.join(bak_dir, bak_name or os.path.basename(fp)))
        doc["editions"] = new_eds
    else:
        exist = {e.get("label") for e in (doc.get("editions") or [])}
        doc.setdefault("editions", []).extend(e for e in new_eds if e["label"] not in exist)
    # ★work-level 上書き(durable): 版置換は promote後なので、promote中に raw版から導出された
    #   magazine/year_started が誤ったまま残る(= 再promoteで戻る)。seed の権威版に揃える。
    if w.get("magazine"): doc["magazine"] = w["magazine"]
    _yrs = [v.get("release_date") for e in new_eds for v in (e.get("volumes") or []) if v.get("release_date")]
    if _yrs:
        try: doc["year_started"] = min(int(str(y)[:4]) for y in _yrs)
        except (ValueError, TypeError): pass
    open(fp, "w", encoding="utf-8").write(yaml.dump(doc, allow_unicode=True, sort_keys=False, Dumper=Dp))
    # 同(type,巻数)を刷タブに畳む (= _regroup-versions.py をその場で実行)
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_regroup-versions.py"), fp],
                   capture_output=True)
    if cover_for is not None:
        doc = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        n = 0
        for e in doc.get("editions") or []:
            for vols in [e.get("volumes") or []] + [x.get("volumes") or [] for x in (e.get("versions") or [])]:
                for v in vols:
                    if not v.get("cover_url") and v.get("isbn13"):
                        c = cover_for(v["isbn13"])
                        if c: v["cover_url"] = c; n += 1
        if n:
            open(fp, "w", encoding="utf-8").write(yaml.dump(doc, allow_unicode=True, sort_keys=False, Dumper=Dp))
    return True


def main():
    dirs = [a for a in sys.argv[1:] if not a.startswith("--")] or [".preview-data/manga", "data/manga.v2"]
    works = load_works()
    print(f"版seed: {len(works)}作", flush=True)
    bak = os.path.join(ROOT, ".cache", f"edisup-bak-{time.strftime('%Y%m%d-%H%M%S')}")
    n_app = 0
    for d in dirs:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base): continue
        applied = 0
        for slug, w in works.items():
            fp = os.path.join(base, slug + ".yml")
            if not os.path.exists(fp): continue
            if apply_work(fp, w, bak, d.replace("/", "_").replace("\\", "_") + "__" + slug + ".yml"):
                applied += 1
        print(f"  [{d}] 版適用 {applied}作", flush=True); n_app += applied
    print(f"完了: 版適用 延べ{n_app}", flush=True)

if __name__ == "__main__":
    main()
