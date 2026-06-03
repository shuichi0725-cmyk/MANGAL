"""最終slug衝突 2,096群を、 merge判定の「確証コスト」で三分する worklist 生成 (read-only)。

[[merge-needs-external-proof]] 原則:
  - 著者が割れる(共通著者qid無) → ★別作確定 = AUTO_SEPARATE(証拠不要・即固有slug)
  - 共通著者qid有                → ★WIKI_NEEDED(ゲゲゲ型=同一著者でも別作あり→Wiki/cmoa確証)
  - 共通base題 + 著者多数バラバラ → ANTHOLOGY(アンソロジー誌の号=別途)
影響度(ページ数)順に出力。 出力 .cache/merge-worklist.json
"""
import json
import sys
import re
import unicodedata
import sqlite3
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
    col = json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))
    con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    key2sid = {k: s for s, k in con.execute("SELECT id, series_key FROM series")}

    def authors(key):
        sid = key2sid.get(key)
        if not sid:
            return set()
        return {q for (q,) in con.execute(
            "SELECT m.qid FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id "
            "WHERE sa.series_id=? AND m.qid IS NOT NULL AND m.qid!=''", (sid,))}

    out = {"AUTO_SEPARATE": [], "WIKI_NEEDED": [], "ANTHOLOGY": []}
    for c in col:
        pages = c["pages"]
        asets = [authors(k) for k in pages]
        nonempty = [a for a in asets if a]
        common = bool(nonempty) and len(nonempty) == len(pages) and bool(set.intersection(*nonempty))
        titles = [norm(title_of(k)) for k in pages]
        nz = [t for t in titles if t]
        short = min(nz, key=len) if nz else ""
        common_base = len(short) >= 2 and all(short in t for t in nz)
        # 著者の異なり数
        distinct_authors = len({frozenset(a) for a in nonempty})
        rec = {"slug": c["slug"], "n": len(pages), "pages": pages,
               "titles": [title_of(k) for k in pages]}
        if common:
            out["WIKI_NEEDED"].append(rec)          # 同一著者=ゲゲゲ型、要確証
        elif common_base and distinct_authors >= 4:
            out["ANTHOLOGY"].append(rec)            # 同題で著者多数=アンソロジー誌
        else:
            out["AUTO_SEPARATE"].append(rec)        # 著者割れ=別作確定
    for k in out:
        out[k].sort(key=lambda r: -r["n"])
    print("最終衝突 2,096群の三分(確証コスト別):")
    for k, v in out.items():
        print(f"  {k:14}: {len(v):,} 群 / {sum(r['n'] for r in v):,} ページ")
    print("\n■ WIKI_NEEDED 上位(同一著者=要Wiki確証、 高影響順):")
    for r in out["WIKI_NEEDED"][:30]:
        ts = list(dict.fromkeys(t[:18] for t in r["titles"]))
        print(f"   [{r['slug']}] ×{r['n']}: " + " / ".join(ts[:5]))
    json.dump(out, (ROOT / ".cache/merge-worklist.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print("\n→ .cache/merge-worklist.json")


if __name__ == "__main__":
    main()
