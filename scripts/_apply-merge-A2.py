"""(A)第2批: 確証済み merge + satellite drop を純粋追加。 [[merge-needs-external-proof]]準拠。"""
import io
import sys
import json
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


MERGES = {
    "bar-lemon-heart": dict(
        note="古谷三敏 BARレモン・ハート 統合(本編37巻 + 双葉文庫テーマ別編=想いの色/夫婦愛/恋を彩る、 同著者同社の同一作編集版)。 2026-06",
        exclude=lambda t: False),
}
# drop-only: title一致でnon-manga-drop追加(本編は残す)
DROPS = {
    "one-piece": [
        (lambda t: "COLOR WALK" in t, "ONE PIECE COLOR WALK=画集"),
        (lambda t: t.strip() == "ONE PIECE RED", "ONE PIECE RED=キャラクター設定資料databook(2002)"),
        (lambda t: t.strip() == "ワンピース", "ワンピース=SJR集英社ジャンプリミックス(コンビニ廉価版)"),
    ],
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    col = {c["slug"]: c for c in json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))}
    mp = ROOT / "data/seeds/series-merge.yml"
    ms = io.open(mp, encoding="utf-8").read()
    nm_path = ROOT / "data/seeds/non-manga-drop.yml"
    nm_text = io.open(nm_path, encoding="utf-8").read()

    blocks, drops = [], []
    for slug, d in MERGES.items():
        pages = col.get(slug, {}).get("pages", [])
        mk = [k for k in pages if not d["exclude"](title_of(k))]
        if len(mk) < 2 or mk[0] in ms:
            print(f"  - {slug}: skip"); continue
        b = ["- merge_keys:"] + [f'  - "{k}"' for k in mk] + [f'  note: {d["note"]}']
        blocks.append("\n".join(b))
        print(f"  ✓ merge {slug}: {len(mk)}")
    for slug, rules in DROPS.items():
        pages = col.get(slug, {}).get("pages", [])
        for k in pages:
            t = title_of(k)
            for pred, why in rules:
                if pred(t) and k not in nm_text:
                    drops.append(f'  - series_key: "{k}"\n    reason: satellite_or_databook\n    note: "(A)merge検証: {why}"')
                    print(f"  ✓ drop {slug}: {t[:24]} ({why[:20]})")
                    break

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
