"""×2保留ペアの個別判定(Wikipedia確証)を適用。 .cache/x2-decisions.json を読む。
形式: [{"match": "題の一部", "action": "merge"|"drop"|"separate", "note": "..."}]
  merge   = そのペア両keyを series-merge.yml へ
  drop    = match を含む側の key を non-manga-drop.yml へ(本編側は残す)
  separate= 何もしない(固有slugのまま=記録のみ)
[[merge-needs-external-proof]]: Wikipedia確証ベース。
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
    decisions = json.load((ROOT / ".cache/x2-decisions.json").open(encoding="utf-8"))
    defer = json.load((ROOT / ".cache/x2-final-defer.json").open(encoding="utf-8"))
    mp = ROOT / "data/seeds/series-merge.yml"
    ms = io.open(mp, encoding="utf-8").read()
    nm = ROOT / "data/seeds/non-manga-drop.yml"
    nt = io.open(nm, encoding="utf-8").read()

    blocks, drops = [], []
    for d in decisions:
        match, action = d["match"], d["action"]
        note = d.get("note", "")
        pair = next((r for r in defer if any(match in title_of(k) for k in r["pages"])), None)
        if not pair:
            print(f"  ! '{match}': ペア無し"); continue
        if action == "merge":
            if pair["pages"][0] in ms:
                print(f"  - '{match}': merge既存skip"); continue
            safe_note = note.replace(": ", "=").lstrip("@`!&*?|>%#~ ")  # YAML予約文字ガード
            b = ["- merge_keys:"] + [f'  - "{k}"' for k in pair["pages"]] + [f"  note: {safe_note}"]
            blocks.append("\n".join(b))
            print(f"  ✓ merge '{match}'")
        elif action == "drop":
            for k in pair["pages"]:
                if match in title_of(k) and k not in nt:
                    drops.append(f'  - series_key: "{k}"\n    reason: satellite_anthology_guide\n    note: "(Wiki確証)({note[:30]}): {title_of(k)[:24]}"')
                    print(f"  ✓ drop '{match}': {title_of(k)[:24]}")
        else:
            print(f"  · separate '{match}'(記録のみ)")

    if blocks:
        if not ms.endswith("\n"):
            ms += "\n"
        io.open(mp, "w", encoding="utf-8").write(ms + "\n".join(blocks) + "\n")
    if drops:
        if not nt.endswith("\n"):
            nt += "\n"
        io.open(nm, "w", encoding="utf-8").write(nt + "\n".join(drops) + "\n")
    m = yaml.safe_load(io.open(mp, encoding="utf-8").read())
    n = yaml.safe_load(io.open(nm, encoding="utf-8").read())
    print(f"\nseries-merge: {len(m)} / non-manga-drop: {len(n['non_manga'])} (YAML OK)")


if __name__ == "__main__":
    main()
