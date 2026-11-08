"""著者補正 seed (author-role-corrections.yml) の「同じ series_key が2つ以上」で前の指定が消えている頁を出す。

  python scripts/_audit-author-corr-dupkey.py      # → docs/production-diagnostics/author-corr-dupkey.tsv

2026-11-08 ユーザ指摘(水木しげる漫画大全集の著者欄に解説者42人)で判明した型:
promote の _load_author_corr は series_key → 補正 を dict に入れるので、同じ key が2回出ると**後の entry が丸ごと勝つ**。
8/24 の役割マーカー掃引(監修/構成/編集)が既存 entry にまとめず別 entry を足したため、前の指定(解説者の除去など)が消えた。

表の「まとめた後」= entry をファイル順に重ね、**同じ人について食い違えば後の指定が勝つ**(=その人の扱いは今と同じ)。
食い違わない前の指定だけが生き返る。 衝突列 = 同じ人を片方は著者/原作に残し、もう片方は外している(今は後の指定どおり)。
"""
import collections, csv, importlib.util, os, sqlite3, sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "author-corr-dupkey.tsv")


def merge_entries(entries):
    """entry をファイル順に重ねる。 人ごとに最後の指定が勝つ。 戻り値は _AUTHOR_CORR の1件と同じ形。"""
    act = {}                                   # name -> drop / original / add / add_original
    creds = {}                                 # name -> [credit, ...](最後に credit にした entry のもの)
    for e in entries:
        orig = set(e.get("original") or [])
        add = list(e.get("add") or [])
        rem = set(e.get("remove") or [])
        cr = [c for c in (e.get("credits") or []) if c.get("name")]
        for nm in orig:
            act[nm] = "original"
        for nm in rem | {c["name"] for c in cr}:
            act[nm] = "drop"
        for nm in add:
            act[nm] = "add_original" if nm in orig else "add"
        by = collections.defaultdict(list)
        for c in cr:
            by[c["name"]].append(c)
        for nm, cs in by.items():
            creds[nm] = cs
    credits = [c for nm, cs in creds.items() if act.get(nm) == "drop" for c in cs]
    return {"drop": {nm for nm, a in act.items() if a == "drop"},
            "credits": credits,
            "original": {nm for nm, a in act.items() if a in ("original", "add_original")},
            "add": [nm for nm, a in act.items() if a in ("add", "add_original")],
            "remove": set()}


def main():
    sys.argv = sys.argv[:1]
    spec = importlib.util.spec_from_file_location("pb", os.path.join(ROOT, "scripts", "_promote-bulk-v2.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    doc = yaml.safe_load(open(os.path.join(ROOT, "data", "seeds", "author-role-corrections.yml"), encoding="utf-8")) or {}
    groups = collections.defaultdict(list)
    for e in doc.get("corrections") or []:
        if e.get("series_key"):
            groups[e["series_key"]].append(e)
    dups = {k: v for k, v in groups.items() if len(v) > 1}

    # series_key -> 頁(SRC の _skey。 skey-overrides が在ればそちら)
    skey2slug = collections.defaultdict(list)
    src = os.path.join(ROOT, "data", "manga")
    for fn in os.listdir(src):
        if not fn.endswith(".yml"):
            continue
        with open(os.path.join(src, fn), encoding="utf-8") as f:
            for line in f:
                if line.startswith("_skey: "):
                    skey2slug[line[7:].strip().strip("'\"")].append(fn[:-4])
                    break
    ovr = (yaml.safe_load(open(os.path.join(ROOT, "data", "seeds", "skey-overrides.yml"), encoding="utf-8")) or {}).get("overrides") or {}
    for slug, v in ovr.items():
        if isinstance(v, dict) and v.get("skey"):
            for k, ss in skey2slug.items():
                if slug in ss:
                    ss.remove(slug)
            skey2slug[v["skey"]].append(slug)

    con = sqlite3.connect(f"file:{os.path.join(ROOT, '.cache', 'db-v2.sqlite')}?mode=ro", uri=True)
    sid = {k: i for i, k in con.execute("select id, series_key from series")}

    def run(authors, corr):
        pb._AUTHOR_CORR = {"K": corr}
        return [(a["name"], a["role"]) for a in pb.apply_author_corrections([dict(x) for x in authors], "K")]

    rows, same = [], 0
    for k, es in dups.items():
        if k not in sid:
            continue
        au = pb.get_authors(con, sid[k])
        last = merge_entries([es[-1]])
        new = merge_entries(es)
        a1, a2 = run(au, last), run(au, new)
        c1 = sorted({(c["role"], c["name"]) for c in last["credits"]})
        c2 = sorted({(c["role"], c["name"]) for c in new["credits"]})
        if a1 == a2 and c1 == c2:
            same += 1
            continue
        keep, kill = set(), set()
        for e in es:
            keep |= set(e.get("add") or []) | set(e.get("original") or [])
            kill |= {c["name"] for c in (e.get("credits") or []) if c.get("name")} | set(e.get("remove") or [])
        s1, s2 = {n for n, _ in a1}, {n for n, _ in a2}
        r1, r2 = dict(a1), dict(a2)
        slugs = skey2slug.get(k) or []
        live = [s for s in slugs if os.path.exists(os.path.join(ROOT, "data", "manga.v2", s + ".yml"))]
        rows.append({
            "slug": ",".join(live) or ("(頁なし)" + ",".join(slugs)),
            "series_key": k,
            "entries": len(es),
            "衝突": "・".join(sorted(keep & kill)),
            "著者から外れる": "・".join(sorted(s1 - s2)),
            "著者に加わる": "・".join(sorted(s2 - s1)),
            "役割が変わる": "・".join(f"{n}:{r1[n]}→{r2[n]}" for n in sorted(s1 & s2) if r1[n] != r2[n]),
            "別枠が増える": "・".join(f"{r}:{n}" for r, n in sorted(set(c2) - set(c1))),
            "今の著者": "・".join(f"{n}" for n, _ in a1),
            "まとめた後の著者": "・".join(f"{n}" for n, _ in a2),
            "指定の出所": " / ".join((e.get("note") or "(note無し)")[:60] for e in es),
        })
    rows.sort(key=lambda r: (r["slug"].startswith("(頁なし)"), r["slug"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["slug"], delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    live = [r for r in rows if not r["slug"].startswith("(頁なし)")]
    print(f"同じ series_key が2つ以上: {len(dups)} / まとめても同じ {same} / 変わる {len(rows)}(頁あり {len(live)})"
          f" / うち衝突あり {sum(1 for r in rows if r['衝突'])}")
    print(f"  著者から外れる人がいる {sum(1 for r in live if r['著者から外れる'])} 頁 / 役割だけ変わる {sum(1 for r in live if r['役割が変わる'] and not r['著者から外れる'])} 頁"
          f" / 別枠だけ増える {sum(1 for r in live if r['別枠が増える'] and not r['著者から外れる'] and not r['役割が変わる'])} 頁")
    print(f"→ {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
