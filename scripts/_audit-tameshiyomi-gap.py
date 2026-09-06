#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【監査】試し読み(BookLive)の巻取りこぼしを **外部を一切叩かず** ローカルだけで数える
(2026-09-06 ユーザ発見「試し読みが8巻ある漫画で7までしかない」)。

比較= 試し読みseed(tameshiyomi-booklive-volumes.jsonl.gz)が持つ巻 vs 本番頁の巻。
★BookLiveは2026-08-29の規制事故で停止札。この監査はHEADを一切打たない。
出力= docs/production-diagnostics/tameshiyomi-tail-gap.tsv(next_cid列=復帰後に確認すべきcid)。
"""
import gzip, json, os, sys, collections
sys.stdout.reconfigure(encoding="utf-8")
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

seed = collections.defaultdict(set)
tid = {}
for line in gzip.open("data/seeds/tameshiyomi-booklive-volumes.jsonl.gz", "rt", encoding="utf-8"):
    try:
        d = json.loads(line)
    except Exception:
        continue
    s, v = d.get("slug"), d.get("volume")
    if s and isinstance(v, int):
        seed[s].add(v)
        tid[s] = d.get("title_id")
print(f"試し読みseed: {len(seed):,}作品 / 実巻数(dedup後) {sum(len(v) for v in seed.values()):,}")

idx = json.load(open("data/manga-list-index.json", encoding="utf-8"))
F = {k: i for i, k in enumerate(idx["f"])}
page = {r[F["slug"]]: (r[F["title"]], r[F["max_edition_volumes"]] or 0, r[F["status"]]) for r in idx["d"]}

tail, hole, none = [], [], 0
for s, vs in seed.items():
    p = page.get(s)
    if not p:
        none += 1
        continue
    title, pmax, st = p
    smax = max(vs)
    if pmax > smax:
        tail.append((s, title, smax, pmax, pmax - smax, st))
    missing = sorted(set(range(1, smax + 1)) - vs)
    if missing:
        hole.append((s, title, missing, smax))
print(f"本番に無いslug: {none}\n")
print(f"■ ★末尾の取りこぼし(頁の巻数 > 試し読みの最大巻) = {len(tail):,}作品")
c = collections.Counter(t[4] for t in tail)
print("   不足巻数の分布:", dict(sorted(c.items())[:10]), "…" if len(c) > 10 else "")
print(f"   不足巻の合計 = {sum(t[4] for t in tail):,}巻")
print(f"   うち連載中 {sum(1 for t in tail if t[5]=='ongoing'):,} / 完結 {sum(1 for t in tail if t[5]=='completed'):,}")
print("\n   不足が大きい順 15:")
for t in sorted(tail, key=lambda x: -x[4])[:15]:
    print(f"     {t[1][:30]:<30} 試し読み1〜{t[2]:>3} / 頁{t[3]:>3}巻  不足{t[4]:>3}  {t[5]}")
print(f"\n■ 途中の穴(1..maxの間で欠けている) = {len(hole):,}作品")
for h in hole[:8]:
    print(f"     {h[1][:30]:<30} 欠け{h[2][:8]} (最大{h[3]})")
out = "docs/production-diagnostics/tameshiyomi-tail-gap.tsv"
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write("slug\ttitle\tseed_max\tpage_max\tmissing\tstatus\ttitle_id\tnext_cid\n")
    for t in sorted(tail, key=lambda x: -x[4]):
        f.write(f"{t[0]}\t{t[1]}\t{t[2]}\t{t[3]}\t{t[4]}\t{t[5]}\t{tid.get(t[0])}\t{tid.get(t[0])}_{t[2]+1:03d}\n")
print(f"\n一覧 → {out}")
