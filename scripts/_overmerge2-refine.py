"""(2)精査: 主範囲外の少数派巻を「下限割れ(vol1等=良性=シリーズ先頭の別版ISBN)」と
「上限超え(花の慶次vol20型=シリーズ巻数を超える=別作混入の強疑い)」に分け、上限超えの実題名を照合。"""
import json, yaml, re, os, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
tmap = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
amap = json.load(open(f"{ROOT}/.cache/isbn-author-map.json", encoding="utf-8"))
outr = json.load(open(f"{ROOT}/.cache/overmerge2-outrange.json", encoding="utf-8"))

def reg(i):
    if not i.startswith("9784") or len(i) != 13:
        return None
    b = i[4:12]; n = int(b[:2])
    return b[:2] if n <= 19 else b[:3] if n <= 69 else b[:4] if n <= 84 else b[:5] if n <= 89 else b[:6] if n <= 94 else b[:7]

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\[\]【】/／\-~〜]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

below_only = 0       # 下限割れのみ(良性)
above = []           # 上限超え(混入疑い) → 実題名照合
for sl, t, top, rng, intr in outr:
    lo, hi = rng
    above_vols = [(r, n) for r, n in intr if n > hi]
    below_vols = [(r, n) for r, n in intr if n < lo]
    if not above_vols:
        below_only += 1
        continue
    # 上限超え巻のISBN+実題名を yml から取得
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p):
        continue
    d = yaml.safe_load(open(p, encoding="utf-8"))
    wt = norm(d.get("title", ""))
    wau = [norm(a.get("name")) for a in (d.get("authors") or []) + (d.get("original_authors") or []) if a.get("name")]
    for e in d.get("editions", []):
        for v in e.get("volumes", []):
            n = v.get("number")
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            if (reg(ib), n) in above_vols:
                rt = tmap.get(ib, ""); ra = amap.get(ib, "")
                title_ok = bool(rt) and wt in norm(rt)
                au_ok = bool(ra) and any(wa and wa in norm(ra) for wa in wau)
                verdict = "?" if not rt else ("同一作(版)" if (title_ok or au_ok) else "★別作混入")
                above.append((sl, d.get("title", "")[:22], n, ib, rt[:26], ra[:16], verdict))
        break

print(f"下限割れのみ(良性=先頭別版ISBN): {below_only}")
print(f"上限超え(混入疑い)を持つ作 の巻: {len(above)}")
import collections
vc = collections.Counter(x[6] for x in above)
print("内訳:", dict(vc))
print("\n=== 上限超え巻の実題名照合 ===")
for sl, t, n, ib, rt, ra, vd in above[:40]:
    print(f"  [{vd}] {t:22} vol{n} → 実題[{rt}] 著[{ra}]")
json.dump(above, open(f"{ROOT}/.cache/overmerge2-above.json", "w", encoding="utf-8"), ensure_ascii=False)
