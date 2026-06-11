"""slug適用の仕上げ2点(★apply-build後・promote前後に実行):

  --volume : volume-final の REVIEW_APPLYTIME 行(本番旧ページ名参照)を解決。
             旧本番slug → (旧合成ソース slug→key) → key2slug → 新slug に書換。
  --alias  : 旧本番ページ(old-v2-slugs.txt) → 新slug の alias 表を生成・統合。
             merge で消えたページも key2slug(全key網羅)で新ページへ転送。

入力: .cache/old-source-slug2key.tsv / .cache/old-v2-slugs.txt / .cache/apply/key2slug.tsv
出力: data/seeds/slug-volume-final.tsv 更新 / data/slug-aliases.yml 追記 / public/_redirects 追記
"""
import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent


def load_maps():
    s2k = {}
    with (ROOT / ".cache/old-source-slug2key.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            s2k[r["slug"]] = r["key"]
    k2s = {}
    with (ROOT / ".cache/apply/key2slug.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            k2s[r["key"]] = r["slug"]
    return s2k, k2s


def do_volume():
    s2k, k2s = load_maps()
    p = ROOT / "data/seeds/slug-volume-final.tsv"
    rows = list(csv.DictReader(p.open(encoding="utf-8"), delimiter="\t"))
    n = {"resolved": 0, "unresolved": 0, "other": 0}
    for r in rows:
        if r.get("rekey") != "REVIEW_APPLYTIME":
            n["other"] += 1
            continue
        ob = r["base"]
        key = s2k.get(ob)
        ns = k2s.get(key) if key else None
        if ns and r["final_slug"].startswith(ob):
            r["final_slug"] = ns + r["final_slug"][len(ob):]
            r["base"] = ns
            r["rekey"] = "RESOLVED_APPLYTIME"
            n["resolved"] += 1
        else:
            r["rekey"] = "UNRESOLVED_APPLYTIME"
            n["unresolved"] += 1
    fields = list(rows[0].keys())
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"volume-final: {n}")
    if n["unresolved"]:
        for r in rows:
            if r.get("rekey") == "UNRESOLVED_APPLYTIME":
                print("  UNRESOLVED:", r["base"], r["isbn13"])


def do_alias():
    s2k, k2s = load_maps()
    old_slugs = (ROOT / ".cache/old-v2-slugs.txt").read_text(encoding="utf-8").split("\n")
    pairs = []
    miss = 0
    for os_ in old_slugs:
        if not os_:
            continue
        key = s2k.get(os_)
        ns = k2s.get(key) if key else None
        if ns is None:
            miss += 1     # drop された旧ページ(画集分離/外国版等)= alias 先なし
            continue
        if ns != os_:
            pairs.append((os_, ns))
    print(f"alias対象(旧→新が変化): {len(pairs)} / 旧ページ {len([s for s in old_slugs if s])} / 転送先なし(drop) {miss}")
    # data/slug-aliases.yml へ追記(既存形式: 'old: new' の単純map想定で確認の上追記)
    ap = ROOT / "data/slug-aliases.yml"
    existing = ap.read_text(encoding="utf-8") if ap.exists() else ""
    have = {l.split(":")[0].strip() for l in existing.splitlines() if ":" in l and not l.startswith("#")}
    added = 0
    with ap.open("a", encoding="utf-8", newline="") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"# slug規則v2適用(2026-06-11): 旧本番slug → 新slug\n")
        for o, nn in pairs:
            if o in have or o == nn:
                continue
            f.write(f"{o}: {nn}\n")
            added += 1
    rp = ROOT / "public/_redirects"
    rexist = rp.read_text(encoding="utf-8") if rp.exists() else ""
    rhave = {l.split()[0] for l in rexist.splitlines() if l.strip() and not l.startswith("#")}
    radd = 0
    with rp.open("a", encoding="utf-8", newline="") as f:
        if rexist and not rexist.endswith("\n"):
            f.write("\n")
        f.write(f"# slug規則v2適用(2026-06-11)\n")
        for o, nn in pairs:
            if f"/{o}" in rhave:
                continue
            f.write(f"/{o} /{nn} 301\n")
            radd += 1
    print(f"slug-aliases.yml +{added} / _redirects +{radd}")


def do_hygiene():
    """★promote後に実行: alias の整合性検査。
    - old側が現役ページslugと一致 → 削除(現役URLからのredirectは事故)
    - new側が現役ページに無い → alias連鎖を解決、 ダメなら報告して除外"""
    pages = {f.stem for f in (ROOT / "data/manga.v2").glob("*.yml")}
    ap = ROOT / "data/slug-aliases.yml"
    amap = {}
    for l in ap.read_text(encoding="utf-8").splitlines():
        if ":" in l and not l.lstrip().startswith("#"):
            o, _, nn = l.partition(":")
            if o.strip() and nn.strip():
                amap[o.strip()] = nn.strip()
    drop_self, retarget, dead = [], [], []
    out = {}
    for o, nn in amap.items():
        if o in pages:
            drop_self.append((o, nn))
            continue
        t = nn
        seen = {t}
        while t not in pages and t in amap and amap[t] not in seen:
            t = amap[t]
            seen.add(t)
        if t in pages:
            if t != nn:
                retarget.append((o, nn, t))
            out[o] = t
        else:
            dead.append((o, nn))
    with ap.open("w", encoding="utf-8", newline="") as f:
        f.write("# 旧 slug → 新 slug の alias mapping。\n")
        f.write("# Next.js middleware / _redirects 生成用。 _resolve-applytime-and-alias.py --hygiene が整合性を保証。\n\n")
        for o, nn in sorted(out.items()):
            f.write(f"{o}: {nn}\n")
    with (ROOT / "public/_redirects").open("w", encoding="utf-8", newline="") as f:
        f.write("# Auto-generated from data/slug-aliases.yml (hygiene済)\n")
        for o, nn in sorted(out.items()):
            f.write(f"/{o} /{nn} 301\n")
    print(f"hygiene: 有効alias {len(out)} / 現役slug衝突で削除 {len(drop_self)} / 連鎖解決 {len(retarget)} / 行き先消失 {len(dead)}")
    for o, nn in drop_self[:10]:
        print(f"  SELF-DROP: {o} -> {nn}")
    for o, nn in dead[:10]:
        print(f"  DEAD: {o} -> {nn}")


if __name__ == "__main__":
    if "--volume" in sys.argv:
        do_volume()
    if "--alias" in sys.argv:
        do_alias()
    if "--hygiene" in sys.argv:
        do_hygiene()
