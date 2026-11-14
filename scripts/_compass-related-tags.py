#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""羅針盤の隠し要素: 関連作(アニメ・原作小説)の AniList タグを、漫画の頁へ引き継ぐための材料を集める。

2026-11-14 ユーザ依頼「隠し要素を関連作から引き継ぐ」。 漫画のエントリは票が薄く、アニメ・原作小説に濃い
(SLAM DUNK は見える要素が1つ。 俺ガイル妄言録は学園以外すべて票20)。

■ やること
  harvest: 頁の anilist_id → 手元の dump(.cache/anilist-manga-dump-v3.jsonl.gz)の関係から、題が同じ範囲の
           アニメ・小説を辿り、AniList の API で 50件ずつ引く(1回2秒・門 _rate_gate 経由)。 生の応答は
           .cache/anilist-related/media.jsonl に追記 = 途中で止めても続きから。
  build  : 集めた分を git に残る小さい表へ = data/seeds/anilist-related-tags.json
           {"v":1,"built":日付,"media":{id:[群,format,登録者,[[タグ英名,票],…]]},"family":{漫画のanilist_id:[id,…]}}
           (タグは票40以上・成人タグ/分野/性的描写の区分/本の形式を除いた分だけ)
  読むのは scripts/_build-compass-hidden.py(本筋のエントリだけ使う = 要素収集 ani_main と同じ線)。

■ 決まり(要素収集 _element-harvest.py の anilist_family と同じ)
  題が同じ関連だけ辿る(頁の題・dump の題のどちらかが相手の題に含まれる/含む。 4字以上)。 別題の続編・クロスオーバーは辿らない。
  辿るのは アニメ と 小説 だけ(他の漫画の票は使わない)。 1作あたり最大30件・3段まで。
  本番データ(manga.v2 / 索引)は読むだけ。 モデルは使わない。

  python scripts/_compass-related-tags.py harvest [--limit N]   # N = API を呼ぶ回数の上限(試し)
  python scripts/_compass-related-tags.py build
  python scripts/_compass-related-tags.py status
"""
import argparse, datetime, gzip, importlib.util, io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz")
INDEX = os.path.join(ROOT, "data", "manga-list-index.json")
WORK = os.path.join(ROOT, ".cache", "anilist-related")
RAW = os.path.join(WORK, "media.jsonl")
FAMILY = os.path.join(WORK, "family.json")
OUT = os.path.join(ROOT, "data", "seeds", "anilist-related-tags.json")
RANK_MIN = 40
SKIP_BASE = {"Sexual Content", "Technical"}
MAX_FAMILY, ROUNDS = 30, 3


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def roots():
    """→ {漫画の anilist_id: {正規化した題…}}(頁に結線済みの分だけ)と、dump の関係。"""
    H = _load("eh", "_element-harvest.py")
    B = _load("ch", "_build-compass-hidden.py")
    s2a = B.slug_to_aid()
    with io.open(INDEX, encoding="utf-8") as f:
        idx = json.load(f)
    i_slug, i_title = idx["f"].index("slug"), idx["f"].index("title")
    title = {r[i_slug]: r[i_title] for r in idx["d"]}
    bases = {}
    for slug, aid in s2a.items():
        t = title.get(slug)
        if t:
            bases.setdefault(aid, set()).add(H.norm(H.base_title(H.strip_edition(t) or t)))
    rel = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("id") in bases:
                bases[d["id"]].add(H.norm(H.base_title((d.get("title") or {}).get("native") or "")))
                rel[d["id"]] = ((d.get("relations") or {}).get("edges")) or []
    for b in bases.values():
        b.discard("")
    return H, bases, rel


def wanted(node):
    return node.get("type") == "ANIME" or node.get("format") == "NOVEL"


def same_title(H, bases, node):
    nb = H.norm((node.get("title") or {}).get("native"))
    return bool(nb) and any(len(b) >= 4 and (b in nb or (len(nb) >= 4 and nb in b)) for b in bases)


def read_raw():
    got = {}
    if os.path.exists(RAW):
        with io.open(RAW, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    m = json.loads(line)
                    got[m["id"]] = m
    return got


def harvest(a):
    os.makedirs(WORK, exist_ok=True)
    H, bases, rel = roots()
    got = read_raw()
    fam = {aid: [] for aid in bases}
    front = {}
    for aid, edges in rel.items():
        front[aid] = [e["node"]["id"] for e in edges if wanted(e["node"]) and same_title(H, bases[aid], e["node"])]
    calls = 0
    for rnd in range(ROUNDS):
        need = sorted({i for aid, ids in front.items() for i in ids if i not in got})
        print(f"{rnd + 1}段目: 辿る先 {sum(len(v) for v in front.values())}(漫画 {sum(1 for v in front.values() if v)}作)/ 未取得 {len(need)}", flush=True)
        with io.open(RAW, "a", encoding="utf-8") as out:
            for k in range(0, len(need), 50):
                if a.limit and calls >= a.limit:
                    print(f"上限 {a.limit}回で止めた(続きは同じコマンド)")
                    return
                chunk = need[k:k + 50]
                ms = H.anilist_call(chunk)
                calls += 1
                seen = set()
                for m in ms:
                    got[m["id"]] = m
                    seen.add(m["id"])
                    out.write(json.dumps(m, ensure_ascii=False) + "\n")
                for i in chunk:  # 消えた id も「引いた」と記録する(引き直し続けない)
                    if i not in seen:
                        got[i] = {"id": i, "gone": True}
                        out.write(json.dumps(got[i]) + "\n")
                out.flush()
                if calls % 10 == 0:
                    print(f"  {calls}回 / このあと {max(0, (len(need) - k - 50) // 50)}回", flush=True)
        nxt = {}
        for aid, ids in front.items():
            have = set(fam[aid])
            for i in ids:
                if i in have or len(fam[aid]) >= MAX_FAMILY:
                    continue
                m = got.get(i)
                if not m or m.get("gone"):
                    continue
                fam[aid].append(i)
                have.add(i)
            cand = []
            for i in ids:
                for e in ((got.get(i) or {}).get("relations") or {}).get("edges") or []:
                    n = e["node"]
                    if n["id"] not in have and n["id"] not in cand and n["id"] != aid and wanted(n) and same_title(H, bases[aid], n):
                        cand.append(n["id"])
            if cand and len(fam[aid]) < MAX_FAMILY:
                nxt[aid] = cand[:MAX_FAMILY - len(fam[aid])]
        front = nxt
        if not front:
            break
    fam = {str(k): v for k, v in sorted(fam.items()) if v}
    with io.open(FAMILY, "w", encoding="utf-8") as f:
        json.dump(fam, f)
    print(f"済: 関連作のある漫画 {len(fam)} / 関連作 {len({i for v in fam.values() for i in v})} / API {calls}回 → build へ")


def build(a):
    got = read_raw()
    with io.open(FAMILY, encoding="utf-8") as f:
        fam = json.load(f)
    media = {}
    for i in sorted({i for v in fam.values() for i in v}):
        m = got[i]
        grp = "N" if m.get("format") == "NOVEL" else "A"
        tags = sorted([t["name"], t["rank"]] for t in m.get("tags") or []
                      if (t.get("rank") or 0) >= RANK_MIN and not t.get("isAdult")
                      and "Demographic" not in (t.get("category") or "") and (t.get("category") or "").split("-")[0] not in SKIP_BASE)
        media[str(i)] = [grp, m.get("format"), m.get("popularity") or 0, tags]
    obj = {"v": 1, "built": datetime.date.today().isoformat(), "media": media, "family": fam}
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace('],"', '],\n"')  # 1件1行 = git の差分が読める
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(raw + "\n")
    os.replace(tmp, OUT)
    print(f"書いた → {os.path.relpath(OUT, ROOT)}: 漫画 {len(fam)} / 関連作 {len(media)}(アニメ {sum(1 for v in media.values() if v[0] == 'A')}・小説 {sum(1 for v in media.values() if v[0] == 'N')})/ {len(raw):,} バイト")


def status(a):
    got = read_raw()
    print(f"取得済みの関連作 {len(got)}(消えた id {sum(1 for m in got.values() if m.get('gone'))})/ family.json {'在る' if os.path.exists(FAMILY) else '無い(harvest が最後まで行っていない)'} / seed {'在る' if os.path.exists(OUT) else '無い'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("harvest"); s.add_argument("--limit", type=int, default=0); s.set_defaults(f=harvest)
    s = sub.add_parser("build"); s.set_defaults(f=build)
    s = sub.add_parser("status"); s.set_defaults(f=status)
    a = ap.parse_args()
    a.f(a)
