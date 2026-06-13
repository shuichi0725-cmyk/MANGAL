"""Phase 0a = 簿記監査(read-only)。 本番 data/manga.v2 全ページの「穴」を機械集計。
設計: docs/intake-manifest-gate-design.md §7 Phase 0。

★本番を一切変更しない。 .cache/manifest-audit/ に出力するのみ。
出力:
  - holes.jsonl    : 1行=1ページ {slug,title,status,vols,year,holes:[{field,sev}]}
  - 標準出力        : フィールド別 fill率 + 優先度ビュー(高価値ページの穴)

穴の層(設計 §3):
  T0=スキーマ床(loaderが拒否=本来0のはず) / T1=品質blocker / T2=warn(出してよいが追跡)
"""
import sys, json, re
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "manga.v2"
OUT = ROOT / ".cache" / "manifest-audit"
OUT.mkdir(parents=True, exist_ok=True)

import yaml
try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import SafeLoader as Loader

JP = re.compile(r"[぀-ヿ㐀-鿿]")  # かな+漢字
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def vols(d):
    out = []
    for ed in d.get("editions") or []:
        out += ed.get("volumes") or []
    return out


def audit_page(d):
    """1ページの穴リストを返す。 [(field, severity)]"""
    holes = []
    vs = vols(d)
    # --- T0 スキーマ床(本来 loader が弾く=0のはず。 0でなければ要調査) ---
    for f in ("title", "title_kana", "title_romaji", "slug", "publisher", "demographic"):
        val = d.get(f)
        empty = (not val) or (isinstance(val, str) and not val.strip())
        if empty:
            holes.append((f, "T0"))
    if not (d.get("genres") or []):
        holes.append(("genres", "T0"))
    if not vs:
        holes.append(("volumes", "T0"))

    # --- T1 品質 blocker ---
    au = d.get("authors") or []
    if not au or (len(au) == 1 and au[0].get("name") == "(unknown)"):
        holes.append(("author_unknown", "T1"))
    if "other" in (d.get("genres") or []):
        holes.append(("genre_other", "T1"))
    if d.get("demographic") == "other":
        holes.append(("demographic_other", "T1"))
    # 著者読み欠落(50音索引に出ない)
    if au and any(a.get("name") != "(unknown)" and not a.get("kana") for a in au):
        holes.append(("author_kana_missing", "T1"))

    # --- T2 warn(出してよいが追跡) ---
    if not (d.get("synopsis") or "").strip():
        holes.append(("synopsis", "T2"))
    if not d.get("anilist_id"):
        holes.append(("anilist_unmatched", "T2"))
    if not d.get("magazine"):
        holes.append(("magazine", "T2"))
    if not (d.get("catch") or "").strip():
        holes.append(("catch", "T2"))
    if not ((d.get("alternative_titles") or {}).get("en")):
        holes.append(("alt_title_en", "T2"))
    # 書影: 全巻 cover_url 無し(現状ほぼ全件=アフィAPI前。 普遍ギャップ)
    if vs and not any(v.get("cover_url") for v in vs):
        holes.append(("cover_all_missing", "T2"))
    # 発売日 日精度: 1巻でも月精度(日欠落)があれば
    if vs:
        n_day = sum(1 for v in vs if DAY.match(str(v.get("release_date") or "")))
        if n_day < len(vs):
            holes.append(("release_date_month_only", "T2"))
    # synonyms に日本語混入(表示分離が必要)
    syn = d.get("synonyms") or []
    if any(JP.search(s or "") for s in syn):
        holes.append(("synonyms_japanese", "T2"))

    return holes


def main():
    files = sorted(SRC.glob("*.yml"))
    n = len(files)
    field_count = Counter()
    sev_pages = Counter()      # 各層の穴を1つ以上持つページ数
    status_count = Counter()
    # 高価値ページ(完結 vols>=10)で synopsis 欠けの数
    high_value_no_synopsis = []
    clean_pages = 0

    with (OUT / "holes.jsonl").open("w", encoding="utf-8") as fout:
        for i, p in enumerate(files):
            try:
                d = yaml.load(p.read_text(encoding="utf-8"), Loader=Loader) or {}
            except Exception as e:
                fout.write(json.dumps({"slug": p.stem, "error": str(e)}, ensure_ascii=False) + "\n")
                continue
            holes = audit_page(d)
            vs = vols(d)
            vc = max([len(ed.get("volumes") or []) for ed in d.get("editions") or []] or [0])
            status_count[d.get("status") or "?"] += 1
            for f, sev in holes:
                field_count[f] += 1
            for sev in {s for _, s in holes}:
                sev_pages[sev] += 1
            if not holes:
                clean_pages += 1
            # 高価値の synopsis 欠け
            if d.get("status") == "completed" and vc >= 10 and ("synopsis", "T2") in holes:
                high_value_no_synopsis.append((p.stem, d.get("title"), vc))
            fout.write(json.dumps({
                "slug": p.stem, "title": d.get("title"), "status": d.get("status"),
                "vols": vc, "year": d.get("year_started"),
                "holes": [{"field": f, "sev": s} for f, s in holes],
            }, ensure_ascii=False) + "\n")
            if (i + 1) % 10000 == 0:
                print(f"  ...{i+1:,}/{n:,}", flush=True)

    print(f"\n{'='*64}")
    print(f"簿記監査 完了: 全 {n:,} ページ / 穴ゼロ(clean) {clean_pages:,} ({clean_pages*100//n}%)")
    print(f"{'='*64}")
    print(f"status: {dict(status_count)}")
    print(f"\n層別(1つ以上の穴を持つページ数):")
    for sev in ("T0", "T1", "T2"):
        print(f"  {sev}: {sev_pages[sev]:,} ({sev_pages[sev]*100//n}%)")
    print(f"\nフィールド別 穴ページ数(多い順):")
    LABEL = {
        "synopsis": "あらすじ空", "anilist_unmatched": "AniList未照合",
        "magazine": "掲載誌なし", "catch": "キャッチコピー空", "alt_title_en": "英題なし",
        "cover_all_missing": "書影ゼロ(=アフィAPI前)", "release_date_month_only": "発売日が月精度",
        "synonyms_japanese": "synonyms日本語混入", "author_unknown": "著者unknown",
        "genre_other": "ジャンルother", "demographic_other": "demographic other",
        "author_kana_missing": "著者読み欠落",
    }
    for f, c in field_count.most_common():
        sev = next((s for ff, s in [(x, y) for x in [f] for y in ["?"]]), "")
        print(f"  {c:>7,}  {f:<26} {LABEL.get(f,'')}")
    print(f"\n高価値ページ(完結・10巻以上)で あらすじ空: {len(high_value_no_synopsis):,}")
    for slug, title, vc in sorted(high_value_no_synopsis, key=lambda x: -x[2])[:15]:
        print(f"    {vc:>3}巻  {slug:<40} {title}")
    print(f"\n→ 詳細(ページ単位): {OUT/'holes.jsonl'}")


if __name__ == "__main__":
    main()
