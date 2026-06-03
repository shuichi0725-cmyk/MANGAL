"""(A)第4批: 同一作の版/連続巻 merge を純粋追加。 [[merge-needs-external-proof]]準拠。"""
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
    "watashitachi-wa-hanshokushiteiru": "内田春菊 私たちは繁殖している統合(本編24巻 + 角川文庫オレンジ/ソーダ/トラベラー=同一作の文庫版)。 2026-06",
    "shiori-to-shimiko": "諸星大二郎 栞と紙魚子シリーズ統合(本編 + 青い馬/生首事件/殺戮詩集=眠れぬ夜の奇妙な話の同一連作各巻、 同キャラ)。 2026-06",
    "papa-told-me": "榛野なな恵 Papa told me統合(本編27巻 + 夏/秋/春=Young you特別企画文庫の同一作選集)。 2026-06",
    "kouun-ryuusui": "本宮ひろ志 こううんりゅうすい統合(徐福/信長=同一作の連続巻4-8 + ジャンプremix廉価版=promoteでedition drop)。 2026-06",
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    col = {c["slug"]: c for c in json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))}
    mp = ROOT / "data/seeds/series-merge.yml"
    ms = io.open(mp, encoding="utf-8").read()
    blocks = []
    for slug, note in MERGES.items():
        pages = col.get(slug, {}).get("pages", [])
        if len(pages) < 2 or pages[0] in ms:
            print(f"  - {slug}: skip"); continue
        b = ["- merge_keys:"] + [f'  - "{k}"' for k in pages] + [f'  note: {note}']
        blocks.append("\n".join(b))
        print(f"  ✓ {slug}: merge {len(pages)}")
    if blocks:
        if not ms.endswith("\n"):
            ms += "\n"
        io.open(mp, "w", encoding="utf-8").write(ms + "\n".join(blocks) + "\n")
    m = yaml.safe_load(io.open(mp, encoding="utf-8").read())
    print(f"\nseries-merge.yml: {len(m)} entries (YAML OK)")


if __name__ == "__main__":
    main()
