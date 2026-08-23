# -*- coding: utf-8 -*-
"""役割マーカー掃引・汎用版 (2026-08-24 ユーザGO④。訳者版 _sweep-translator-authors.py の一般化)。

MADB raw(metadata101)のcreator役割マーカー([監修]/[構成]/[編集]…)を一次証拠に、
非著者roleの人物を著者欄から除去して credits(role表示) へ移す。

ガード(3層):
  1. 同一series内でマーカー無しcreatorとしても現れる人物 = 著者兼任の疑い → 触らない
  2. ★その人物が唯一の著者である頁が1つでもある = 除去すると(unknown)化 → 全域で触らない(dog-man教訓)
  3. 本番頁の著者欄に実在する人物のみ対象

usage: python scripts/_sweep-role-authors.py --roles 監修,構成,編集 [--apply]
※[編](7,456件)はアンソロジー編者=正当著者が多いため既定に含めない(個別裁定マター)。
"""
import argparse
import glob
import io
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / ".cache" / "madb" / "metadata101.json"
CORR = ROOT / "data" / "seeds" / "author-role-corrections.yml"


def _to13(s):
    s = re.sub(r"[^0-9Xx]", "", s or "")
    if len(s) == 13:
        return s
    if len(s) == 10:
        core = "978" + s[:9]
        chk = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
        return core + str((10 - chk % 10) % 10)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", default="監修,構成,編集")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    roles = [r.strip() for r in a.roles.split(",") if r.strip()]
    role_re = re.compile(r"^\[(" + "|".join(re.escape(r) for r in roles) + r")\]\s*(.+)$")
    tag = "-".join(roles)

    per_isbn_hit, per_isbn_plain = defaultdict(set), defaultdict(set)
    g = json.load(io.open(RAW, encoding="utf-8"))
    rows = g.get("@graph", g) if isinstance(g, dict) else g
    for r in rows:
        cr = r.get("schema:creator")
        if not cr:
            continue
        names = cr if isinstance(cr, list) else [cr]
        hit, plain = set(), set()
        for nm in names:
            if not isinstance(nm, str):
                continue
            nm = nm.strip()
            m = role_re.match(nm)
            if m:
                hit.add((m.group(1), m.group(2).strip()))
            else:
                plain.add(re.sub(r"^\[[^\]]*\]\s*", "", nm).strip())
        if not hit:
            continue
        i = r.get("schema:isbn")
        if isinstance(i, list):
            i = i[0] if i else None
        k = _to13(str(i)) if i else None
        if not k:
            continue
        per_isbn_hit[k] |= hit
        per_isbn_plain[k] |= plain
    del g, rows
    print(f"raw走査: 対象ISBN {len(per_isbn_hit):,}", flush=True)

    con = sqlite3.connect(ROOT / ".cache" / "db-v2.sqlite")
    key_hit, key_plain = defaultdict(set), defaultdict(set)
    for isbn, pairs in per_isbn_hit.items():
        r = con.execute("select s.series_key from series s join editions e on e.series_id=s.id "
                        "join volumes v on v.edition_id=e.id where v.isbn13=?", (isbn,)).fetchone()
        if not r:
            continue
        key_hit[r[0]] |= pairs
        key_plain[r[0]] |= per_isbn_plain.get(isbn, set())
    print(f"series_key解決: {len(key_hit):,}", flush=True)

    final, guarded = {}, []
    for k, pairs in key_hit.items():
        names = {}
        for role, nm in pairs:
            if nm in key_plain.get(k, set()):
                guarded.append((k, nm, "無印兼任"))
                continue
            names[nm] = role
        if names:
            final[k] = names

    # 本番影響+唯一著者ガード
    all_names = {nm for names in final.values() for nm in names}
    name_pat = re.compile("|".join(re.escape(n) for n in sorted(all_names, key=len, reverse=True)))
    affected_pages, sole_protected = {}, set()
    for f in glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")):
        t = io.open(f, encoding="utf-8").read()
        am = re.search(r"(?ms)^authors:\n(.*?)^(?:original_authors|publisher|magazine|editions):", t)
        if not am:
            continue
        blk = am.group(1)
        hits = set(name_pat.findall(blk)) if all_names else set()
        if not hits:
            continue
        page_authors = set(re.findall(r"(?m)^- name: (.+)$", blk))
        if page_authors and page_authors <= {str(h) for h in hits}:
            sole_protected |= hits          # この頁で唯一の著者=全域で保護
        else:
            affected_pages[Path(f).stem] = hits
    print(f"本番影響頁: {len(affected_pages)} / 唯一著者保護: {len(sole_protected)}名", flush=True)

    doc = yaml.safe_load(io.open(CORR, encoding="utf-8")) or {}
    have = {e.get("series_key"): set(e.get("remove") or []) for e in doc.get("corrections", [])}
    page_names = {nm for hs in affected_pages.values() for nm in hs}
    emit = []
    for k, names in sorted(final.items()):
        todo = {nm: role for nm, role in names.items()
                if nm in page_names and nm not in sole_protected and nm not in have.get(k, set())}
        if todo:
            emit.append((k, todo))
    print(f"corrections追加対象: {len(emit)} key / のべ {sum(len(v) for _, v in emit)} 名")

    outp = ROOT / "docs" / "production-diagnostics" / f"role-sweep-{tag}.tsv"
    with io.open(outp, "w", encoding="utf-8", newline="\n") as w:
        w.write("series_key\t人物\trole\n")
        for k, todo in emit:
            for nm, role in sorted(todo.items()):
                w.write(f"{k}\t{nm}\t{role}\n")
        for k, nm, why in guarded:
            w.write(f"{k}\t{nm}\t(ガード={why})\n")
        for nm in sorted(sole_protected):
            w.write(f"-\t{nm}\t(ガード=唯一著者頁あり=全域保護)\n")
    print("TSV:", outp)
    io.open(ROOT / ".cache" / f"role-sweep-{tag}-pages.txt", "w", encoding="utf-8", newline="\n").write(
        "\n".join(sorted(affected_pages)))

    if not a.apply:
        for k, todo in emit[:10]:
            print("  例:", k, "→", list(todo.items()))
        print("(dry-run。--apply で corrections へ追記)")
        return

    NOTE = f"役割マーカー掃引2026-08-24({tag}): raw metadata101の[{'/'.join(roles)}]マーカーを一次証拠に著者→credits"
    with io.open(CORR, "a", encoding="utf-8", newline="\n") as w:
        for k, todo in emit:
            w.write("- series_key: " + json.dumps(k, ensure_ascii=False) + "\n")
            w.write("  remove:\n")
            for nm in sorted(todo):
                w.write("  - " + json.dumps(nm, ensure_ascii=False) + "\n")
            w.write("  credits:\n")
            for nm, role in sorted(todo.items()):
                w.write("  - name: " + json.dumps(nm, ensure_ascii=False) + "\n")
                w.write("    role: " + json.dumps(role, ensure_ascii=False) + "\n")
            w.write("  note: " + json.dumps(NOTE, ensure_ascii=False) + "\n")
    # 追記後のYAML健全性検証(月次skill罠: 機械追記は必ずparse確認)
    yaml.safe_load(io.open(CORR, encoding="utf-8"))
    print(f"corrections += {len(emit)} entries (YAML OK)")


if __name__ == "__main__":
    main()
