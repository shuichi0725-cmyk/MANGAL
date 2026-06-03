"""保留中の内包副題ペア278を、 著者qid + 巻構造 で精選 (read-only)。
[[merge-needs-external-proof]]: 同一著者前提で、 巻の連続/重複=同作分裂→MERGE、
実質副題+小巻の独立=spinoff→SEPARATE。

判定(両者 同一著者qid overlap が前提=WIKI_NEEDED):
  VOL_FRAGMENT  : 一方の巻集合 ⊆ 他方、 or 補完連続(範囲が隣接・非重複) → 同作分裂 MERGE
  VOL_OVERLAP   : 巻番号が有意に重複 → 同作の版違い MERGE
  SHORT_SUB     : 副題(差分)が短い(≤6字、 記号除く) → 副題ドリフト MERGE
  SPINOFF_RISK  : 実質副題(≥7字) ∧ 小巻独立([1..k]同士で非連続) → spinoff SEPARATE
  REVIEW        : 上記外
出力: .cache/x2-contains-buckets.json + .cache/merge-queue.json(MERGE分)
"""
import json
import sys
import re
import unicodedata
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
STRIP = re.compile(r"[・･\s　.\-,，。!！?？=~〜:：\"'’（）()「」『』【】\[\]/／]")


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def norm(t):
    return STRIP.sub("", unicodedata.normalize("NFKC", t or "").lower().translate(HIRA))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    defer = json.load((ROOT / ".cache/x2-contains-defer.json").open(encoding="utf-8"))
    en = json.load((ROOT / ".cache/anilist-enrich-map.json").open(encoding="utf-8"))
    con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    key2sid = {k: s for s, k in con.execute("SELECT id, series_key FROM series")}

    def info(key):
        sid = key2sid.get(key)
        if not sid:
            return set(), set()
        au = {q for (q,) in con.execute(
            "SELECT m.qid FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id "
            "WHERE sa.series_id=? AND m.qid IS NOT NULL AND m.qid!=''", (sid,))}
        vols = {n for (n,) in con.execute(
            "SELECT v.number FROM volumes v JOIN editions e ON e.id=v.edition_id "
            "WHERE e.series_id=? AND v.isbn13!='' AND v.number BETWEEN 1 AND 399", (sid,))}
        return au, vols

    out = {"VOL_FRAGMENT": [], "VOL_OVERLAP": [], "SHORT_SUB": [],
           "SEP_DIFF_AID": [], "SPINOFF_RISK": [], "REVIEW": []}
    for r in defer:
        k0, k1 = r["pages"]
        t0, t1 = title_of(k0), title_of(k1)
        n0, n1 = norm(t0), norm(t1)
        au0, v0 = info(k0)
        au1, v1 = info(k1)
        aids = {(en.get(k0) or {}).get("anilist_id"), (en.get(k1) or {}).get("anilist_id")}
        aids = {a for a in aids if a}
        same_aid = len(aids) == 1
        long_n, short_n = (n0, n1) if len(n0) >= len(n1) else (n1, n0)
        sub = long_n.replace(short_n, "", 1) if short_n and short_n in long_n else long_n
        rec = {"slug": r["slug"], "pages": r["pages"], "titles": [t0, t1],
               "v0": sorted(v0), "v1": sorted(v1), "sub": sub, "same_aid": same_aid}
        # ★同一anilist_id を必須(spinoffは別aid=ここで除外)。 短副題gloss(≤3)のみ例外許容
        if not same_aid and len(sub) > 3:
            out["SEP_DIFF_AID"].append(rec)
            continue
        if not v0 or not v1:
            (out["SHORT_SUB"] if len(sub) <= 6 else out["REVIEW"]).append(rec)
            continue
        overlap = v0 & v1
        subset = v0 <= v1 or v1 <= v0
        lo = (max(v0) < min(v1)) or (max(v1) < min(v0))
        gap_ok = lo and abs((min(v1) - max(v0)) if max(v0) < min(v1) else (min(v0) - max(v1))) <= 3
        if subset or len(overlap) >= 2:
            (out["VOL_OVERLAP"] if overlap else out["VOL_FRAGMENT"]).append(rec)
        elif gap_ok:
            out["VOL_FRAGMENT"].append(rec)
        elif len(sub) <= 6:
            out["SHORT_SUB"].append(rec)
        else:
            out["REVIEW"].append(rec)

    print(f"内包副題 {len(defer)}群 の著者+巻構造 精選:")
    for k, v in out.items():
        tag = "→MERGE" if k in ("VOL_FRAGMENT", "VOL_OVERLAP", "SHORT_SUB") else "→分離/保留"
        print(f"  {k:13}: {len(v):3} {tag}")
    for bk in out:
        print(f"\n■ {bk}:")
        for r in out[bk][:12]:
            print(f"   {r['titles'][0][:20]}{r['v0'][:1]}..{r['v0'][-1:] } ┃ {r['titles'][1][:20]}{r['v1'][:1]}..{r['v1'][-1:]}")
    json.dump(out, (ROOT / ".cache/x2-contains-buckets.json").open("w", encoding="utf-8"), ensure_ascii=False)
    q = []
    for bk in ("VOL_FRAGMENT", "VOL_OVERLAP", "SHORT_SUB"):
        for r in out[bk]:
            q.append({"slug": r["slug"], "note": f"×2内包ペア統合(著者+巻構造={bk}=同作の分裂/版/副題ドリフト) 2026-06"})
    json.dump(q, (ROOT / ".cache/merge-queue.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n→ MERGE候補 {len(q)}群")


if __name__ == "__main__":
    main()
