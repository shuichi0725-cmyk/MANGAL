#!/usr/bin/env python3
"""
Phase① caption強化 = 分類器の入力を底上げ(= [[genre_from_rakuten_story_plan]])。

旧: work ごとに「最長1キャプション」。
新: **巻番号順に複数巻のキャプションを連結**(1巻あらすじ=導入を先頭、重複除去、600字上限)。
    → genre/tag 分類の precision/recall を底上げ(タダ・LLM不要)。

同時に、以降の適用に必要な per-work メタを1スキャンで集約 → corpus-v2.jsonl:
  {slug, title, anilist_id, trusted(bool), provisional(bool),
   label(=trusted genres), has_theme_tag(bool), caption(=v2連結), n_caps}

入力: .cache/rakuten-isbn.jsonl + data/manga.v2/*.yml
"""
import json, sys, time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
RAK = ROOT / ".cache" / "rakuten-isbn.jsonl"
MANGA = ROOT / "data" / "manga.v2"
OUT = ROOT / ".cache" / "genre-rakuten"
OUT.mkdir(parents=True, exist_ok=True)

import yaml
try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import SafeLoader as Loader

MIN_CAP = 40
CAP_BUDGET = 600


def to_isbn13(s):
    if not s:
        return None
    s = str(s).replace("-", "").replace(" ", "").strip()
    if len(s) == 13 and s.isdigit():
        return s
    if len(s) == 10:
        core = "978" + s[:9]
        try:
            tot = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(core))
        except ValueError:
            return None
        return core + str((10 - tot % 10) % 10)
    return None


def clean(c):
    if not c:
        return ""
    c = c.replace("\r", " ").replace("\n", " ").replace("　", " ")
    while "  " in c:
        c = c.replace("  ", " ")
    return c.strip()


def load_caps():
    cap = {}
    t0 = time.time(); n = 0
    with open(RAK, encoding="utf-8") as f:
        for line in f:
            n += 1
            try:
                r = json.loads(line)
            except Exception:
                continue
            item = r.get("item") or {}
            c = clean(item.get("itemCaption"))
            if len(c) < MIN_CAP:
                continue
            isbn = to_isbn13(r.get("isbn") or item.get("isbn"))
            if not isbn:
                continue
            old = cap.get(isbn)
            if old is None or len(c) > len(old):
                cap[isbn] = c
    print(f"  caption ISBN: {len(cap):,} [{time.time()-t0:.0f}s]", flush=True)
    return cap


def build_caption_v2(vols, cap):
    """巻番号順に複数巻 caption を連結(重複除去, 600字上限)。"""
    seq = []
    for v in vols:
        isbn = to_isbn13(v.get("isbn13"))
        if not isbn:
            continue
        c = cap.get(isbn)
        if not c:
            continue
        num = v.get("number")
        num = num if isinstance(num, int) else 9999
        seq.append((num, c))
    if not seq:
        return None, 0
    seq.sort(key=lambda x: x[0])
    out = []
    seen_pref = set()
    total = 0
    for _, c in seq:
        pref = c[:30]
        if pref in seen_pref:
            continue
        # 既出の部分文字列はスキップ
        if any(c in o or o in c for o in out):
            continue
        seen_pref.add(pref)
        out.append(c)
        total += len(c)
        if total >= CAP_BUDGET:
            break
    joined = " / ".join(out)[:CAP_BUDGET]
    return joined, len(out)


def main():
    print("=== Phase① caption強化 ===", flush=True)
    cap = load_caps()
    files = sorted(MANGA.glob("*.yml"))
    print(f"  manga.v2 {len(files):,} 走査...", flush=True)

    cf = (OUT / "corpus-v2.jsonl").open("w", encoding="utf-8")
    t0 = time.time()
    n_cap = 0; n_multi = 0
    st = {"trusted": 0, "provisional": 0, "has_tag": 0}
    for i, fp in enumerate(files):
        if i % 12000 == 0 and i:
            print(f"   ...{i:,} [{time.time()-t0:.0f}s]", flush=True)
        try:
            d = yaml.load(fp.read_text(encoding="utf-8"), Loader=Loader)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        genres = d.get("genres") or []
        prov = bool(d.get("genres_provisional"))
        is_trusted = bool(genres) and genres != ["other"] and not prov
        theme = [t for t in (d.get("tags") or [])
                 if t.get("category") and t.get("category") != "Demographic" and t.get("name")]
        vols = []
        for ed in (d.get("editions") or []):
            for v in (ed.get("volumes") or []):
                vols.append(v)
        capv2, ncaps = build_caption_v2(vols, cap)
        if not capv2:
            continue
        n_cap += 1
        if ncaps > 1:
            n_multi += 1
        if is_trusted:
            st["trusted"] += 1
        if prov:
            st["provisional"] += 1
        if theme:
            st["has_tag"] += 1
        cf.write(json.dumps({
            "slug": d.get("slug"), "title": d.get("title"),
            "anilist_id": d.get("anilist_id"),
            "trusted": is_trusted, "provisional": prov,
            "label": sorted(genres) if is_trusted else [],
            "has_theme_tag": bool(theme), "n_caps": ncaps,
            "caption": capv2,
        }, ensure_ascii=False) + "\n")
    cf.close()
    print(f"\ncaption有り work: {n_cap:,}(複数巻連結 {n_multi:,} = {100*n_multi//max(n_cap,1)}%)", flush=True)
    print(f"  trusted {st['trusted']:,} / provisional {st['provisional']:,} / theme tag有 {st['has_tag']:,}", flush=True)
    print(f"  → 適用対象: genre(provisional)={st['provisional']:,} / tag(tag未保有)={n_cap-st['has_tag']:,}", flush=True)
    print(f"corpus-v2 → {OUT/'corpus-v2.jsonl'}", flush=True)


if __name__ == "__main__":
    main()
