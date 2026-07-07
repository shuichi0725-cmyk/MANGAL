#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISBNダブリ AUTO層の一括適用 (= _isbn-dup-triage.py の isbn-dup-auto.json を seed に焼く)。

各クラスタ: page-dedup.yml(drop) + slug-aliases.yml + public/_redirects + changelog。
反映(reflect-targeted)は別途 --only/--drop で実行(このスクリプトは seed 書込のみ)。
実行: python scripts/_isbn-dup-apply.py  → 出力される reflect コマンドを実行
"""
import os, sys, json, datetime

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTO = json.load(open(os.path.join(ROOT, ".cache", "isbn-dup-auto.json"), encoding="utf-8"))
TODAY = datetime.date.today().isoformat()

# 既存 page-dedup drop 集合 (重複防止)
import yaml
pd_path = os.path.join(ROOT, "data", "seeds", "page-dedup.yml")
existing_drops = {e["drop"] for e in (yaml.safe_load(open(pd_path, encoding="utf-8")) or {}).get("dedup", [])}

pd_lines, alias_lines, redir_lines, log_lines = [], [], [], []
only, drops = [], []
for a in AUTO:
    only.append(a["canonical"])
    for d in a["drops"]:
        if d["stem"] in existing_drops:
            print(f"skip(既にdedup済): {d['stem']}")
            continue
        drops.append(d["stem"])
        note = "ISBNダブリ一括dedup(集合完全一致+同題)" + ("・著者表記違いは作画交代断片" if a.get("author_differ") else "")
        pd_lines.append(f"- drop: {d['stem']}\n  canonical: {a['canonical']}\n"
                        f"  title: {a['title']}\n  isbns: {a['isbns']}\n  note: {note}({TODAY})\n")
        if d["slug"] != a["canonical_slug"]:
            alias_lines.append(f"{d['slug']}: {a['canonical_slug']}\n")
            redir_lines.append(f"/{d['slug']} /{a['canonical_slug']} 301\n")
        log_lines.append(json.dumps({
            "slug": a["canonical_slug"], "op": "isbn-dup-dedup", "source": "_audit-isbn-dup-pages",
            "before": f"2頁分裂: {a['canonical']} + {d['stem']}(題={d['title']})",
            "after": f"1頁: {a['canonical']}。{d['slug']}は301 alias",
            "at": datetime.datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")

with open(pd_path, "a", encoding="utf-8") as f:
    f.writelines(pd_lines)
with open(os.path.join(ROOT, "data", "slug-aliases.yml"), "a", encoding="utf-8") as f:
    f.writelines(alias_lines)
with open(os.path.join(ROOT, "public", "_redirects"), "a", encoding="utf-8") as f:
    f.writelines(redir_lines)
with open(os.path.join(ROOT, "data", "seeds", "samename-dedup-changelog.jsonl"), "a", encoding="utf-8") as f:
    f.writelines(log_lines)

print(f"seed書込: page-dedup {len(pd_lines)} / alias {len(alias_lines)} / redirect {len(redir_lines)}")
print("\n次を実行:")
print(f"python scripts/_reflect-targeted.py --only {','.join(only)} --drop {','.join(drops)} --push -m \"...\"")
