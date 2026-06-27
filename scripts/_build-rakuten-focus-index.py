"""A是正の共通土台: disorder(515)+gaps(647) の対象slugについてのみ
楽天harvestから focused index を1パスで構築し pickle 永続化。

target基底題 = 各slugの title + alternative_titles(値) + synonyms(値) を norm。
index key = (norm基底題, vol) → [printing records]。残差題=target完全一致のみ収録。
"""
import sys, os, csv, pickle, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L

ROOT = L.ROOT
OUT = f"{ROOT}/.cache/rakuten-focus-index.pkl"

def slug_bases(d):
    """1ページの target基底題 set(norm) + 表示用代表題。"""
    bases = set()
    t = d.get("title")
    if t: bases.add(L.norm(t))
    alt = d.get("alternative_titles") or {}
    if isinstance(alt, dict):
        for v in alt.values():
            if isinstance(v, str) and v.strip():
                bases.add(L.norm(v))
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, str) and x.strip(): bases.add(L.norm(x))
    for v in (d.get("synonyms") or []):
        if isinstance(v, str) and v.strip():
            bases.add(L.norm(v))
    bases.discard("")
    return bases

def main():
    slugs = set()
    for tsv in ("docs/volume-date-disorder.tsv", "docs/volume-gaps.tsv"):
        with open(f"{ROOT}/{tsv}", encoding="utf-8") as fp:
            for row in csv.DictReader(fp, delimiter="\t"):
                slugs.add(row["slug"])
    print(f"対象slug: {len(slugs)}件 (disorder+gaps union)", flush=True)

    # slug -> bases, and reverse base -> set(slug)
    slug_to_bases = {}
    base_to_slugs = {}
    target_bases = set()
    missing = 0
    for sl in sorted(slugs):
        p = f"{ROOT}/data/manga.v2/{sl}.yml"
        if not os.path.exists(p):
            missing += 1; continue
        try:
            d = yaml.safe_load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not d: continue
        bs = slug_bases(d)
        slug_to_bases[sl] = bs
        for b in bs:
            target_bases.add(b)
            base_to_slugs.setdefault(b, set()).add(sl)
    print(f"  yml読込: {len(slug_to_bases)}件 / 欠 {missing} / 基底題ユニーク {len(target_bases)}", flush=True)

    def prog(n): print(f"  ...{n:,} items scanned", flush=True)
    print("楽天harvest 1パス走査中 (delta828MB+old373MB)...", flush=True)
    index, total = L.build_index(target_bases, progress=prog)
    print(f"走査完了: {total:,} items / index keys {len(index):,}", flush=True)

    with open(OUT, "wb") as f:
        pickle.dump({
            "index": index,
            "slug_to_bases": slug_to_bases,
            "base_to_slugs": base_to_slugs,
        }, f)
    print(f"保存: {OUT}", flush=True)

if __name__ == "__main__":
    main()
