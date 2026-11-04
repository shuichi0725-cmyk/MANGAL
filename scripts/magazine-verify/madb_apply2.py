"""第2弾: new_mags_2.CONFIG に従って、 正しい誌がマスタに無かった頁(誤った値60・空欄191)を直す。
入力 = .cache/magazine-lists/missing-mags-2.json(mag_missing_list.py)+ 検証表 TSV(根拠の文言)
書く = data/magazines.yml・.preview-data/magazines.yml(末尾追記)/ magazine-corrections.yml(末尾追記)/ changelog /
       .cache/magazine-lists/stems-madb2.txt / .cache/magazine-fix-bak-<日時>/
usage: python scripts/magazine-verify/madb_apply2.py [--write]"""
import csv, datetime, json, os, re, shutil, sys
from collections import Counter
from pathlib import Path
import yaml

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import madb_apply as A
from new_mags_2 import CONFIG
sys.stdout.reconfigure(encoding="utf-8")
ROOT = A.ROOT
L = ROOT / ".cache" / "magazine-lists"


def main(write):
    groups = json.load(open(L / "missing-mags-2.json", encoding="utf-8"))
    unknown = [c for c in groups if c not in CONFIG]
    if unknown:
        sys.exit(f"★CONFIG に無い誌: {unknown}")
    mags = yaml.safe_load(open(ROOT / "data" / "magazines.yml", encoding="utf-8"))
    pubs = yaml.safe_load(open(ROOT / "data" / "publishers.yml", encoding="utf-8"))
    demos = yaml.safe_load(open(ROOT / ".preview-data" / "demographics.yml", encoding="utf-8"))
    new = {}
    for c, v in CONFIG.items():
        if v[0] == "NEW":
            _, key, name, pub, demo = v
            if key in mags:
                sys.exit(f"★既にマスタに在るキー: {key}")
            if key in new:
                sys.exit(f"★キーが重複: {key}")
            if pub and pub not in pubs:
                sys.exit(f"★出版社キーが無い: {pub}({key})")
            if demo not in demos:
                sys.exit(f"★読者層が無い: {demo}({key})")
            new[key] = (name, pub, demo)
    rows = {r["slug"]: r for r in csv.DictReader((ln for ln in open(A.TSV, encoding="utf-8") if not ln.startswith("#")), delimiter="\t")}
    existing = yaml.safe_load(open(ROOT / "data" / "seeds" / "magazine-corrections.yml", encoding="utf-8"))["corrections"]
    plan, skip = {}, Counter()
    for c, g in groups.items():
        v = CONFIG[c]
        if v[0] == "EXCLUDE":
            skip[f"除外: {v[1]}"] += len(g["pages"]); continue
        tgt = v[1]
        if tgt not in mags and tgt not in new:
            sys.exit(f"★寄せ先が無い: {tgt}")
        for s in g["pages"]:
            r = rows[s]
            if tgt == r["今の連載誌"]:
                skip["今と同じ(直さない)"] += 1; continue
            if s in existing:
                skip["既存seedあり"] += 1; continue
            plan[s] = {"title": r["title"], "old": r["今の連載誌"], "new": tgt, "tier": r["段階"], "why": r["理由"],
                       "map": v[2] if v[0] == "MAP" else "", "wiki": r["Wikipedia"], "madb": r["MADB"], "rakuten": r["楽天"]}
    ov = yaml.safe_load(open(ROOT / "data" / "seeds" / "slug-overrides.yml", encoding="utf-8"))["overrides"]
    rev = {}
    for k, v in ov.items():
        if isinstance(v, dict) and v.get("slug"):
            rev.setdefault(v["slug"], []).append(k)
    stems = {s: A.stem_of(s, rev) for s in plan}
    missing = [s for s, st in stems.items() if not st]
    for s in missing:
        plan.pop(s); stems.pop(s)
    used = sorted({p["new"] for p in plan.values() if p["new"] in new})
    print("適用", len(plan), "頁(誤り直し", sum(1 for p in plan.values() if p["old"]), "/ 空欄埋め", sum(1 for p in plan.values() if not p["old"]),
          ") / 見送り", dict(skip), "/ stem不明", missing)
    print("新しい誌", len(used), "/ 設定したが頁が無い誌", sorted(set(new) - set(used)))
    print("読者層の内訳", dict(Counter(new[k][2] for k in used)))
    if not write:
        return
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = ROOT / ".cache" / f"magazine-fix-bak-{ts}"; bak.mkdir(parents=True)
    for st in set(stems.values()):
        shutil.copy2(ROOT / "data" / "manga.v2" / f"{st}.yml", bak / f"{st}.yml")
    block = ("\n# ★2026-11-04 第2弾(ユーザ「残り約130誌を足して60頁と194頁を直して」)。 根拠= MADB 雑誌掲載履歴/単行本の初出欄 × ja.wikipedia。\n"
             "#   読者層= ja.wikipedia の誌の分類(無い時は頁の多数)。 子ども向けは児童。 設定の正本= scripts/magazine-verify/new_mags_2.py\n")
    for k in used:
        name, pub, demo = new[k]
        block += f"{k}:\n  name: {yaml.safe_dump(name, allow_unicode=True).strip().removesuffix(chr(10) + '...')}\n  publisher: {pub}\n  demographic: {demo}\n"
    for p in (ROOT / "data" / "magazines.yml", ROOT / ".preview-data" / "magazines.yml"):
        txt = p.read_text(encoding="utf-8")
        p.write_text(txt + ("" if txt.endswith("\n") else "\n") + block, encoding="utf-8")
        chk = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert all(chk[k]["name"] == new[k][0] for k in used), p
    entries = {}
    for s, pl in sorted(plan.items()):
        src = {"A": "madb+wiki-verified", "B": "madb", "D": "manual"}[pl["tier"][0]]
        ev = f"MADB(1.2.21) {pl['madb'][:150]}"
        if pl["wiki"]:
            ev += f" / ja.wikipedia{pl['wiki'][:120]}"
        if pl["why"]:
            ev += f"。{pl['why']}"
        if pl["map"]:
            ev += f"。{pl['map']}"
        ev += f"。旧値 {pl['old'] or '空'}(種3のAI埋め)"
        entries[s] = {"magazine": pl["new"], "source": src, "evidence": re.sub(r"\s+", " ", ev), "added_at": "2026-11-04"}
    dumped = yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=10000)
    dumped = "\n".join(("  " + ln) if ln else ln for ln in dumped.splitlines())
    cp = ROOT / "data" / "seeds" / "magazine-corrections.yml"
    txt = cp.read_text(encoding="utf-8")
    cp.write_text(txt + ("" if txt.endswith("\n") else "\n")
                  + "  # ★2026-11-04 第2弾(正しい誌がマスタに無かった頁)。 誌の設定= scripts/magazine-verify/new_mags_2.py\n" + dumped + "\n", encoding="utf-8")
    yaml.safe_load(cp.read_text(encoding="utf-8"))
    at = datetime.datetime.now().isoformat(timespec="seconds")
    with open(ROOT / "data" / "seeds" / "magazine-fix-changelog.jsonl", "a", encoding="utf-8") as f:
        for s, pl in sorted(plan.items()):
            f.write(json.dumps({"op": "magazine-correct", "slug": s, "title": pl["title"], "before": pl["old"] or None, "after": pl["new"],
                                "evidence": entries[s]["evidence"], "tier": pl["tier"], "at": at,
                                "via": "magazine-corrections.yml → _reflect-targeted --only-file",
                                "reversible": f"magazine-corrections.yml の当該キーを消して再反映(退避 {bak.name})"}, ensure_ascii=False) + "\n")
    (L / "stems-madb2.txt").write_text("\n".join(sorted(set(stems.values()))) + "\n", encoding="utf-8", newline="\n")
    json.dump({s: {"stem": stems[s], **p} for s, p in plan.items()}, open(L / "madb-apply2-plan.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("書いた: 雑誌マスタ +", len(used), "/ corrections +", len(entries), "/ stems", len(set(stems.values())), "/ 退避", bak)


if __name__ == "__main__":
    main("--write" in sys.argv)
