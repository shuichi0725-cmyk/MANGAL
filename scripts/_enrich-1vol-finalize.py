# -*- coding: utf-8 -*-
"""1巻見直しの下書き(.cache/enrich-1vol/raw-<N>.json = {slug: {catch, g, t}})を applier 形式へ変換。

  g = 足すジャンル(master32)。 頁のジャンルが空なら genres_add(=provisional付きで入る)、
      既にあれば genres_union(= genre-append.yml で既存を消さず足す)。
  t = 要素の和名(theme-vocab-ja.json の語彙のみ)。
  "skip": "理由" = 書かない(材料不足/掲載境界)。 enrich-hold.tsv に理由付きで残す。

出力 data/enrich-out-2026-07/batch-<N>.json。 字数(48-74)と丸写し率を先に表示する。
  python scripts/_enrich-1vol-finalize.py 9700
"""
import datetime, io, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
n = sys.argv[1]
raw = json.load(io.open(os.path.join(ROOT, ".cache", "enrich-1vol", f"raw-{n}.json"), encoding="utf-8"))
# 字数/丸写しの手直しは別ファイル fix-<N>.json = {slug: 新catch} に書き、ここで上書き合流する(下書き本体は触らない)
_fx = os.path.join(ROOT, ".cache", "enrich-1vol", f"fix-{n}.json")
if os.path.exists(_fx):
    for _s, _c in json.load(io.open(_fx, encoding="utf-8")).items():
        raw[_s]["catch"] = _c
st = {e["slug"]: e for e in json.load(io.open(os.path.join(ROOT, ".cache", "enrich-batches", f"batch-{n}.json"), encoding="utf-8"))["items"]}


def ov(a, b, k=8):
    a = re.sub(r"\s", "", a); b = re.sub(r"\s", "", b)
    if len(a) < k or len(b) < k: return 0.0
    bs = {b[i:i + k] for i in range(len(b) - k + 1)}
    return sum(1 for i in range(len(a) - k + 1) if a[i:i + k] in bs) / max(1, len(a) - k + 1)


out, holds, probs = {}, [], []
for s, v in raw.items():
    if s not in st:
        probs.append(f"  {s}: batch外"); continue
    if v.get("skip"):
        holds.append((s, st[s]["title"], v["skip"])); continue
    c = v["catch"].strip()
    L = len(c)
    m = max(ov(c, x["caption"]) for x in st[s]["captions"])
    if not (48 <= L <= 74) or m >= 0.40:
        probs.append(f"  {s}: len={L} overlap={m:.2f}")
    e = {"catch": c}
    g = [x for x in (v.get("g") or []) if x not in st[s]["genres_now"]]
    if g:
        e["genres_add" if not st[s]["genres_now"] else "genres_union"] = g
    if v.get("t"):
        e["themes"] = v["t"]
    out[s] = e
missing = [s for s in st if s not in raw]
json.dump(out, io.open(os.path.join(ROOT, "data", "enrich-out-2026-07", f"batch-{n}.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
if holds:
    hp = os.path.join(ROOT, "docs", "production-diagnostics", "enrich-hold.tsv")
    seen = {ln.split("	")[0] for ln in io.open(hp, encoding="utf-8")}
    with io.open(hp, "a", encoding="utf-8") as f:
        for s, t, r in holds:
            if s in seen: continue
            f.write(f"{s}\t{t}\t{datetime.date.today()}\t{n}\t1巻見直し: {r}\n")
print(f"batch-{n}: 書く {len(out)} / 見送り {len(holds)} / 未記入 {len(missing)} {missing[:5]}")
print("要修正:" if probs else "字数・丸写し OK", *probs, sep="\n")
