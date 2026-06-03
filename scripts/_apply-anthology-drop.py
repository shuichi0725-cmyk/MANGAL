"""(A)アンソロジー誌 + 劇場版フィルムコミックを non-manga-drop.yml へ純粋追加。
ユーザ判断(a)=非・漫画作品として除外。 ★本編・実在spinoffは保護(精密drop)。
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


# 全ページdrop(マルチ著者アンソロジー=確認済)
ANTHOLOGY_SLUGS = [
    "yabamori-hontou-ni-atta-koko-dake-no-hanashi-kiwami",
    "yabamori-hontou-ni-atta-nama-koko-dake-no-hanashi-kiwami",
    "bakumori-hontou-ni-atta-nama-koko-dake-no-hanashi-matsuri",
    "gekimori-hontou-ni-atta-nama-koko-dake-no-hanashi-chou",
    "choumori-hontou-ni-atta-nama-koko-dake-no-hanashi-chou",
    "sugomori-hontou-ni-atta-nama-koko-dake-no-hanashi-kiwami",
    "hontou-ni-atta-nama-koko-dake-no-hanashi-chou",
    "chibi-hontou-ni-atta-waraeru-hanashi",
    "hontou-ni-yabai-horror-story",
    "itadaki-shiawase-gohan",
    "komikku-ran-serekushon",
    "komikku-ran-tsuinzu-serekushon",
    "koike-kazuo-gekiga-serekushon",
    "sasupensu-ando-misuterii-komikku-honkaku-serekushon",
    "meitantei-asami-mitsuhiko-ando-ryojou-misuterii-komikku-serekushon",
    "on-buruu",
    "gasshu-maniakkusu",
    "awesome-fellows",
    "komikku-fantajii",
]
# 劇場版フィルムコミックのみdrop(本編・特別編は保護)
MOVIE_DROP = {
    "meitantei-conan": lambda t: ("摩天楼" in t) or ("標的" in t),
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    col = {c["slug"]: c for c in json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))}
    nm_path = ROOT / "data/seeds/non-manga-drop.yml"
    nm_text = io.open(nm_path, encoding="utf-8").read()

    lines = []
    n_anth = n_movie = 0
    for slug in ANTHOLOGY_SLUGS:
        for k in col.get(slug, {}).get("pages", []):
            if k not in nm_text and all(k not in ln for ln in lines):
                lines.append(f'  - series_key: "{k}"\n    reason: anthology_magazine\n    note: "(a)アンソロジー誌drop: {title_of(k)[:28]}"')
                n_anth += 1
    for slug, pred in MOVIE_DROP.items():
        for k in col.get(slug, {}).get("pages", []):
            if pred(title_of(k)) and k not in nm_text:
                lines.append(f'  - series_key: "{k}"\n    reason: movie_film_comic\n    note: "(a)劇場版フィルムコミックdrop: {title_of(k)[:28]}"')
                n_movie += 1
                print(f"  movie drop: {title_of(k)}")

    if lines:
        if not nm_text.endswith("\n"):
            nm_text += "\n"
        io.open(nm_path, "w", encoding="utf-8").write(nm_text + "\n".join(lines) + "\n")
    n = yaml.safe_load(io.open(nm_path, encoding="utf-8").read())
    print(f"\n★アンソロジー誌drop: {n_anth}ページ / 劇場版drop: {n_movie}ページ")
    print(f"non-manga-drop.yml: {len(n.get('non_manga') or [])} entries (YAML OK)")
    print("★保護: 名探偵コナン(本編)/ 名探偵コナン特別編(実在spinoff) = drop せず")


if __name__ == "__main__":
    main()
