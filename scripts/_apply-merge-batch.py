"""(A)汎用 merge/drop applier。 .cache/merge-queue.json を読んで series-merge.yml と
non-manga-drop.yml に純粋追加。 [[merge-needs-external-proof]]準拠。

queue形式: [{"slug": str, "exclude": [title...], "drop": [title...], "note": str, "renumber": bool}]
  exclude = merge から外す(別ページ保持)。 drop = non-manga-drop へ。
"""
import io
import sys
import json
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    queue = json.load((ROOT / ".cache/merge-queue.json").open(encoding="utf-8"))
    col = {c["slug"]: c for c in json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))}
    mp = ROOT / "data/seeds/series-merge.yml"
    ms = io.open(mp, encoding="utf-8").read()
    nm_path = ROOT / "data/seeds/non-manga-drop.yml"
    nm_text = io.open(nm_path, encoding="utf-8").read()

    blocks, drops = [], []
    for item in queue:
        slug = item["slug"]
        excl = set(item.get("exclude") or [])
        dset = set(item.get("drop") or [])
        note = item["note"]
        pages = col.get(slug, {}).get("pages", [])
        mk = [k for k in pages if title_of(k).strip() not in excl and title_of(k).strip() not in dset]
        dk = [k for k in pages if title_of(k).strip() in dset]
        if len(mk) >= 2 and mk[0] not in ms:
            b = ["- merge_keys:"] + [f'  - "{k}"' for k in mk]
            if item.get("renumber"):
                b.append("  renumber: true")
            b.append(f"  note: {note}")
            blocks.append("\n".join(b))
            print(f"  ✓ merge {slug}: {len(mk)}" + (f" / drop {len(dk)}" if dk else ""))
        else:
            print(f"  - {slug}: merge skip(既存 or <2)")
        for k in dk:
            if k not in nm_text:
                drops.append(f'  - series_key: "{k}"\n    reason: satellite_foreign_anime\n    note: "(A){title_of(k)[:30]}"')

    if blocks:
        if not ms.endswith("\n"):
            ms += "\n"
        io.open(mp, "w", encoding="utf-8").write(ms + "\n".join(blocks) + "\n")
    if drops:
        if not nm_text.endswith("\n"):
            nm_text += "\n"
        io.open(nm_path, "w", encoding="utf-8").write(nm_text + "\n".join(drops) + "\n")
    m = yaml.safe_load(io.open(mp, encoding="utf-8").read())
    n = yaml.safe_load(io.open(nm_path, encoding="utf-8").read())
    print(f"\nseries-merge.yml: {len(m)} / non-manga-drop: {len(n.get('non_manga') or [])} (YAML OK)")


if __name__ == "__main__":
    main()
