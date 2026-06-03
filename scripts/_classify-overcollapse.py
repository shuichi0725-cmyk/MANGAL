"""post-merge over-collapse群を「共通base題=同系統(merge候補)」と
「共通base無=別作が同読み(別slug/suffix候補)」に機械分類する (dry-run, read-only)。

入力: .cache/slug-overcollapse-postmerge.json (merge適用後も同slugな別ページ群)
出力: .cache/oc-franchise.json / .cache/oc-homonym.json
"""
import json
import sys
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
STRIP = re.compile(r"[・･\s　.\-,，。!！?？=~〜:：\"'’]")


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def norm(t):
    t = unicodedata.normalize("NFKC", t or "").lower().translate(HIRA)
    return STRIP.sub("", t)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    remain = json.load((ROOT / ".cache/slug-overcollapse-postmerge.json").open(encoding="utf-8"))
    franchise, homonym = [], []
    for g in remain:
        titles = [norm(title_of(k)) for k in g["keys"]]
        titles = [t for t in titles if t]
        if len(titles) < 2:
            continue
        short = min(titles, key=len)
        if len(short) >= 2 and all(short in t for t in titles):
            franchise.append((g["slug"], g["keys"], short))
        else:
            homonym.append((g["slug"], g["keys"]))
    print(f"post-merge over-collapse: {len(remain)}群")
    print(f"  ├ ★(2)共通base有=同系統 → merge候補: {len(franchise)}")
    print(f"  └ ★(3)共通base無=別作が同読み → 別slug(suffix)候補: {len(homonym)}")
    print("\n■(2)系統merge候補の例(共通base題):")
    for slug, keys, base in sorted(franchise, key=lambda x: -len(x[1]))[:10]:
        print(f"   [{slug}] base「{base}」 ×{len(keys)}")
    print("\n■(3)別作suffix候補の例(共通base無=本当に別の作品):")
    for slug, keys in sorted(homonym, key=lambda x: -len(x[1]))[:14]:
        ts = list(dict.fromkeys(title_of(k)[:14] for k in keys))
        print(f"   [{slug}]: " + " / ".join(ts))
    json.dump([{"slug": s, "keys": k, "base": b} for s, k, b in franchise],
              (ROOT / ".cache/oc-franchise.json").open("w", encoding="utf-8"), ensure_ascii=False)
    json.dump([{"slug": s, "keys": k} for s, k in homonym],
              (ROOT / ".cache/oc-homonym.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n→ franchise{len(franchise)} / homonym{len(homonym)} を保存")


if __name__ == "__main__":
    main()
