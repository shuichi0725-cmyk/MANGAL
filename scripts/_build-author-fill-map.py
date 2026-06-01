"""著者ゼロページ補完用: AniList staff から anilist_id→著者マップを構築。

★原作と作画を厳密分離(whitelist):
  authors(作画): Story & Art→writer_artist / Art→artist / Story→writer
  original_authors(原作): Original Story / Original Creator
  除外: Character Design / Translator* / Lettering* / Assistant / Editor* / Cover* / Supervisor / Touch-up* 等
日本語名(native)優先。 出力: .cache/author-fill-map.json
"""
import sys, gzip, json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path("C:/Users/shuic/code/mangal")
DUMP = ROOT / ".cache/anilist-manga-dump-v3.jsonl.gz"

AUTHOR_ROLE = {"Story & Art": "writer_artist", "Art": "artist", "Story": "writer"}
ORIGINAL_ROLE = {"Original Story", "Original Creator"}


def jp_name(node):
    nm = node.get("name", {})
    return nm.get("native") or nm.get("full") or ""


def main():
    out = {}
    n = 0
    for line in gzip.open(DUMP, "rt", encoding="utf-8"):
        d = json.loads(line); n += 1
        aid = d.get("id")
        if not aid:
            continue
        authors = []; originals = []
        seen_a = set(); seen_o = set()
        for e in (d.get("staff") or {}).get("edges", []):
            role = e.get("role", "")
            name = jp_name(e.get("node", {}))
            if not name:
                continue
            if role in AUTHOR_ROLE:
                if name not in seen_a:
                    seen_a.add(name); authors.append({"name": name, "role": AUTHOR_ROLE[role]})
            elif role in ORIGINAL_ROLE:
                if name not in seen_o:
                    seen_o.add(name); originals.append(name)
            # それ以外(Character Design/Translator/Lettering/Assistant/Editor等)は除外
        if authors or originals:
            out[str(aid)] = {"authors": authors, "original_authors": originals}
    OUT = ROOT / ".cache/author-fill-map.json"
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"dump {n:,}件 → 著者マップ {len(out):,}件(authors or originals あり)")
    print(f"  wrote {OUT}")
    # 検証
    print("\n=== 検証(原作/作画の分離)===")
    for aid, lbl in [("86199", "虚構推理"), ("85564", "無職転生(本編)"), ("146378", "無職転生(4コマ)"),
                     ("109229", "左ききのエレン"), ("109228", "左ききのエレン(別id)")]:
        e = out.get(aid)
        if e:
            au = " / ".join(f"{a['name']}({a['role']})" for a in e["authors"])
            og = " / ".join(e["original_authors"])
            print(f"  {lbl}: 作画[{au}] 原作[{og}]")


if __name__ == "__main__":
    main()
