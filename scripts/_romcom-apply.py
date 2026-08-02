# -*- coding: utf-8 -*-
"""romcom裁定台帳(verdict=yes)を genre-append.yml へ純粋追加する(適用=Opus+専権)。

  python scripts/_romcom-apply.py --dry     … 追加予定の件数と内訳のみ表示
  python scripts/_romcom-apply.py --apply   … genre-append.yml へ追記 + 対象slugを .cache/romcom-applied-slugs.txt へ

- 冪等: 既に genre-append.yml で romcom が付いている slug / 本番genresに既に romcom がある slug は skip。
- ★seed機械追記の戒め: source に ":" を含むため必ず quote する([[seed_yaml_colon_quoting]])。
- 反映: 適用後は「反映して」(_reflect-targeted.py --only)か次の週次蒸留。件数が多い時は週次に乗せるのが安い。
"""
import io
import json
import os
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JUDGED = os.path.join(ROOT, "data", "seeds", "romcom-judged.jsonl")
APPEND = os.path.join(ROOT, "data", "seeds", "genre-append.yml")
OUTSLUGS = os.path.join(ROOT, ".cache", "romcom-applied-slugs.txt")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry"
    yes = {}
    with io.open(JUDGED, encoding="utf-8") as fp:
        for line in fp:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("verdict") == "yes":
                yes[r["slug"]] = r.get("source", "ai-judge")

    doc = yaml.safe_load(open(APPEND, encoding="utf-8")) or {}
    already = {e["slug"] for e in doc.get("additions", []) if "romcom" in (e.get("add") or [])}

    # 本番索引で既に romcom が付いている作品も skip(二重追記防止)
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    fi = idx["f"]
    slug_i, gen_i = fi.index("slug"), fi.index("genres")
    has_already = {r[slug_i] for r in idx["d"] if r[gen_i] and "romcom" in r[gen_i]}

    todo = [(s, src) for s, src in sorted(yes.items()) if s not in already and s not in has_already]
    from collections import Counter
    c = Counter(src for _, src in todo)
    print(f"yes総数 {len(yes)} / 既適用skip {len(yes) - len(todo)} / 追加予定 {len(todo)} (内訳 {dict(c)})")
    if mode != "--apply":
        print("(--dry。書き込みは --apply)")
        return

    with io.open(APPEND, "a", encoding="utf-8") as fp:
        for s, src in todo:
            fp.write(f"  - slug: {s}\n    add: [romcom]\n    source: \"romcom-judge:{src}\"\n")
    os.makedirs(os.path.dirname(OUTSLUGS), exist_ok=True)
    with io.open(OUTSLUGS, "w", encoding="utf-8") as fp:
        fp.write("\n".join(s for s, _ in todo))
    print(f"追記 {len(todo)}件 → {APPEND}")
    print(f"対象slug一覧 → {OUTSLUGS} (反映は _reflect-targeted.py --only か週次)")


if __name__ == "__main__":
    main()
