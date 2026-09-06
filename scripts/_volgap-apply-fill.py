# -*- coding: utf-8 -*-
"""【巻抜け充填 適用】裁定済み(decision=APPLY)の巻を 正しい seed へ純粋追加する。

経路で書く先が変わる(= _volgap-gap-targets.py の route):
  seed4          → data/seeds/volumes-supplement-auto.yml に純粋追加
  canon:volumes  → data/seeds/edition-canonical/<stem>.yml の volumes
  canon:compact  → 同 compact_edition.volumes
  canon:extra[i] → 同 extra_editions[i].volumes
  ★canonical は promote の最後に editions を丸ごと置換するので、種4に書いても頁に出ない

安全策:
 - 既定 dry-run(--apply で書込)
 - 変更ファイルは .cache/volgap-fill-bak-<ts>/ へ退避(可逆)
 - 既に同じISBNを持つ seed / canonical は skip(冪等・純粋追加)
 - 種4の series_keys は **その版の既存巻ISBN** から db-v2 逆引き(頁全体ではない)。
   版にISBNが1本も無く、かつ頁が separate_editions / merge_edition_types に載っている時は
   「どの版タブに入るか保証できない」ので HOLD(報告のみ)
 - changelog = data/seeds/intake-manifest/volgap-fill-changelog.jsonl に1行/巻

使用: python scripts/_volgap-apply-fill.py --in .cache/volgap-apply.json,.cache/volgap-apply-ndl.json [--apply]
"""
import os
import sys
import re
import json
import shutil
import sqlite3
import datetime
from collections import defaultdict, Counter

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
SEED4 = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
CANON = os.path.join(ROOT, "data", "seeds", "edition-canonical")
MERGE_YML = os.path.join(ROOT, "data", "seeds", "series-merge.yml")
LOG = os.path.join(ROOT, "data", "seeds", "intake-manifest", "volgap-fill-changelog.jsonl")
APPLY = "--apply" in sys.argv
INS = (sys.argv[sys.argv.index("--in") + 1] if "--in" in sys.argv
       else ".cache/volgap-apply.json,.cache/volgap-apply-ndl.json").split(",")
TODAY = datetime.date.today().isoformat()
STAMP = TODAY.replace("-", "") + "-volgap-fill"
BAK = os.path.join(ROOT, ".cache", "volgap-fill-bak-" + STAMP)


def nisbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def backup(path):
    if not APPLY:
        return
    os.makedirs(BAK, exist_ok=True)
    dst = os.path.join(BAK, os.path.basename(path))
    if not os.path.exists(dst):
        shutil.copy2(path, dst)


def main():
    rows = []
    for p in INS:
        p = p if os.path.isabs(p) else os.path.join(ROOT, p)
        if os.path.exists(p):
            rows += [r for r in json.load(open(p, encoding="utf-8")) if r["decision"] == "APPLY"]
    print("適用候補 {} 巻 / {} 頁".format(len(rows), len({r["stem"] for r in rows})))
    print("経路:", dict(Counter(r["route"] for r in rows)))

    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    cur = con.cursor()
    key_to_sid = {sk: sid for sid, sk in cur.execute("SELECT id, series_key FROM series")}

    # ★頁が separate_editions / merge_edition_types に載っているか(種4の着地が保証できない条件)
    flagged_keys = set()
    for entry in (yaml.safe_load(open(MERGE_YML, encoding="utf-8")) or []):
        if entry.get("separate_editions") or entry.get("merge_edition_types"):
            flagged_keys.update(entry.get("merge_keys") or [])

    def skeys_of_isbns(isbns):
        ks = set()
        for ib in isbns:
            for (k,) in cur.execute(
                    "SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id "
                    "JOIN series se ON se.id=e.series_id WHERE v.isbn13=?", (ib,)):
                ks.add(k)
        return ks

    pagecache = {}

    def page(stem):
        if stem not in pagecache:
            pagecache[stem] = yaml.safe_load(open(os.path.join(SRC, stem + ".yml"),
                                                  encoding="utf-8")) or {}
        return pagecache[stem]

    seed = yaml.safe_load(open(SEED4, encoding="utf-8")) or {}
    seed.setdefault("volumes", [])
    seed_isbns = {nisbn(e.get("isbn13")) for e in seed["volumes"] if e.get("isbn13")}
    n_seed_before = len(seed["volumes"])

    new4, held, canon_edits = [], [], defaultdict(list)
    for r in rows:
        stem, ei, num, ib = r["stem"], int(r["ei"]), int(r["number"]), r["isbn"]
        d = page(stem)
        eds = d.get("editions") or []
        e = eds[ei] if ei < len(eds) else {}
        if r["route"].startswith("canon:"):
            canon_edits[stem].append(r)
            continue
        if ib in seed_isbns:
            held.append((r, "既に種4に在る(冪等skip)"))
            continue
        ed_isbns = [nisbn(v.get("isbn13")) for v in (e.get("volumes") or []) if v.get("isbn13")]
        ks = sorted(skeys_of_isbns(ed_isbns))
        scope = "版"
        if not ks:
            all_isbns = [nisbn(v.get("isbn13")) for ee in eds for v in (ee.get("volumes") or [])
                         if v.get("isbn13")]
            ks = sorted(skeys_of_isbns(all_isbns))
            scope = "頁"
            if any(k in flagged_keys for k in ks):
                held.append((r, "版にISBNが無く、頁が separate_editions/merge_edition_types 指定"
                                "= どの版タブに着地するか保証できない"))
                continue
        if not ks:
            held.append((r, "series_key を結線できない(頁にISBNが1本も無い)"))
            continue
        new4.append({
            "series_keys": ks, "qid": None, "number": num, "isbn13": ib,
            "release_date": r["date"] or None, "pages": None,
            "publisher": r.get("rak_publisher") or e.get("publisher") or None,
            "edition_type": r["etype"], "title_display": r.get("rak_title") or "",
            "source": "volgap-fill-" + r.get("source", ""), "added_at": TODAY,
            "note": "巻抜け充填 slug={} 版[{}]{} 結線={}単位 gate={}".format(
                stem, ei, e.get("label") or "", scope, r.get("decision_why", "")),
        })
        seed_isbns.add(ib)

    # ---- canonical ----
    canon_plan = []
    for stem, rs in canon_edits.items():
        p = os.path.join(CANON, stem + ".yml")
        if not os.path.exists(p):
            for r in rs:
                held.append((r, "edition-canonical seed が無い"))
            continue
        s = yaml.safe_load(open(p, encoding="utf-8")) or {}
        have = set()
        for lst in ([s.get("volumes") or []] + [(s.get("compact_edition") or {}).get("volumes") or []]
                    + [x.get("volumes") or [] for x in (s.get("extra_editions") or [])]
                    + [x.get("volumes") or [] for x in (s.get("versions") or [])]):
            for v in lst:
                if v.get("isbn13"):
                    have.add(nisbn(v["isbn13"]))
        adds = []
        for r in rs:
            if r["isbn"] in have:
                held.append((r, "既に canonical に在る(冪等skip)"))
                continue
            route = r["route"]
            if route == "canon:volumes":
                tgt = s.setdefault("volumes", [])
            elif route == "canon:compact":
                tgt = s.setdefault("compact_edition", {}).setdefault("volumes", [])
            else:
                m = re.match(r"canon:extra\[(\d+)\]$", route)
                xs = s.get("extra_editions") or []
                if not m or int(m.group(1)) >= len(xs):
                    held.append((r, "canonical の extra_editions[{}] が無い".format(route)))
                    continue
                tgt = xs[int(m.group(1))].setdefault("volumes", [])
            if any(v.get("number") == int(r["number"]) for v in tgt):
                held.append((r, "canonical のその版に同じ巻番号が既に在る"))
                continue
            o = {"number": int(r["number"]), "isbn13": r["isbn"]}
            if r["date"]:
                o["release_date"] = r["date"]
            tgt.append(o)
            tgt.sort(key=lambda v: (v.get("number") is None, v.get("number")))
            adds.append(r)
            have.add(r["isbn"])
        if adds:
            s["source"] = (s.get("source") or "") + (
                " / ★{} 巻抜け充填: ローカル楽天種とNDLで欠番巻を確認し {} 巻を追加"
                "(題完全一致+版元+ISBN連番+発売日+著者の5ゲート)".format(TODAY, len(adds)))
            canon_plan.append((p, s, adds))

    print("\n=== 適用計画 ===")
    print("  種4(volumes-supplement-auto.yml) 追加 {} 巻".format(len(new4)))
    print("  canonical seed 追加 {} 巻 / {} ファイル".format(
        sum(len(a) for _, _, a in canon_plan), len(canon_plan)))
    print("  保留 {} 巻".format(len(held)))
    for r, why in held:
        print("    HOLD {:28s} v{:<4} {} : {}".format(r["stem"][:28], r["number"], r["isbn"], why))
    if not APPLY:
        print("\ndry-run(--apply で書込)")
        return

    os.makedirs(BAK, exist_ok=True)
    if new4:
        backup(SEED4)
        seed["volumes"].extend(new4)
        tmp = SEED4 + ".new"
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(seed, f, allow_unicode=True, sort_keys=False, width=10000)
        chk = yaml.safe_load(open(tmp, encoding="utf-8"))
        assert len(chk["volumes"]) == n_seed_before + len(new4), "種4 件数検証NG"
        os.replace(tmp, SEED4)
        print("種4: {} → {} entry".format(n_seed_before, len(seed["volumes"])))
    for p, s, adds in canon_plan:
        backup(p)
        tmp = p + ".new"
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(s, f, allow_unicode=True, sort_keys=False, width=10000)
        yaml.safe_load(open(tmp, encoding="utf-8"))
        os.replace(tmp, p)
    print("canonical: {} ファイル更新".format(len(canon_plan)))

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        for r in rows:
            if any(h[0] is r for h in held):
                continue
            f.write(json.dumps({
                "at": TODAY, "op": "volgap-fill", "slug": r["stem"],
                "before": "版[{}] v{} 欠番".format(r["ei"], r["number"]),
                "after": "v{} = {}".format(r["number"], r["isbn"]),
                "route": r["route"], "edition_type": r["etype"], "label": r.get("label"),
                "source": r.get("source"), "gate": r.get("decision_why"),
                "backup": os.path.relpath(BAK, ROOT),
            }, ensure_ascii=False) + "\n")
    print("→ changelog {}".format(os.path.relpath(LOG, ROOT)))
    print("→ backup    {}".format(os.path.relpath(BAK, ROOT)))
    print("次: python scripts/_reflect-targeted.py --only <stems> で反映")


if __name__ == "__main__":
    main()
