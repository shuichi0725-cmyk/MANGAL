#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ジャンル・要素の「見直しの表」を作る(= 全頁を1行ずつ。 経路と順番を機械で決める)。 2026-10-12 新設。

  python scripts/_gen-element-review-queue.py            # 表を作り直して要約を出す(読み取りのみ・約20秒)
  python scripts/_gen-element-review-queue.py --material # 手元の材料の束を作り直す(楽天キャッシュ1.2GBを1回だけ走査・約2分。 蒸留で巻が増えた後に)
  python scripts/_gen-element-review-queue.py --next 100 [--route L]   # 次に見直す stem を順番どおりに出す(未の行だけ)

★表は手で編集しない。 状態(未/案あり/適用済)は台帳から毎回引き直すので、いつ作り直しても続きから始まる。
  出力: .cache/element-harvest/review-queue.tsv(全件・git 管理外)/ data/element-harvest/review-queue-summary.json(要約・git 追跡)

経路(安い順に通す):
  A = AniList の関連作(原作小説・アニメ)の票を引き継ぐ見込み(アニメ化あり)。 機械が主、材料は補助
  L = 手元の材料(楽天・Kobo の紹介文 / あらすじ seed / 巻説明)を Haiku が読む。 Web は見ない
  W = 手元の材料が薄い → Web で集める(1作 約2分。 アイドル運転で少しずつ)
  後 = もう要素が3つ以上あり、ジャンルも汎用だけではない(後回し)
順番 = 経路の安い順 → 同じ経路の中は手元の材料の多い順(★人気順にしない)。
原作グループ = 題が前方一致し著者が重なる頁(材料を1回集めて共有する手がかり。 機械の見立てなので確定ではない)。
"""
import argparse, collections, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)
OUT = D(".cache", "element-harvest", "review-queue.tsv")
SUMMARY = D("data", "element-harvest", "review-queue-summary.json")
GENERIC = {"drama", "comedy", "romance", "slice-of-life", "action", "other"}
LOCAL_MIN = 150  # 手元の材料(AI が書いたキャッチは数えない)がこの字数以上 = 経路 L
ROUTE_ORDER = {"A": 0, "L": 1, "W": 2, "後": 3}
COLS = ["order", "route", "state", "stem", "slug", "title", "tier", "group", "genres", "generic_only", "elements", "local_chars", "sources", "year", "volumes"]


def jl(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    yield json.loads(l)


def norm(t):
    return re.sub(r"[\s　・!！?？。、,.\-–—~〜()（）\[\]【】「」『』:：]", "", t or "").lower()


CAPS = D(".cache", "element-harvest", "_local", "captions.jsonl")
AD = re.compile(r"コンビニ|付録|特典|重版|セット|限定版|ポストカード|特装|電子版|電子書籍|配信|廉価|価格|お買い得|シリーズ累計|万部")


def build_material():
    """楽天の巻ごとの紹介文(itemCaption)を頁ごとに束ねる。 ★重いキャッシュはここで1回だけ読み、後段(Haiku の判定)には束を渡す。"""
    with open(D(".cache", "isbn-page-index.json"), encoding="utf-8") as f:
        ipi = json.load(f)
    by = collections.defaultdict(dict)  # slug → {isbn: (題, 紹介文)}
    pat = re.compile(r'"isbn":\s*"(97\d{11})"')
    for p in (D(".cache", "rakuten-isbn.jsonl"), D(".cache", "rakuten-isbn-delta.jsonl")):
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                m = pat.search(line)
                if not m or m.group(1) not in ipi or '"itemCaption": ""' in line:
                    continue
                try:
                    it = json.loads(line).get("item") or {}
                except ValueError:
                    continue
                c = re.sub(r"\s+", " ", it.get("itemCaption") or "").strip()
                if len(c) < 40:
                    continue
                for slug in ipi[m.group(1)]:
                    by[slug][m.group(1)] = (it.get("title") or "", c)
    os.makedirs(os.path.dirname(CAPS), exist_ok=True)
    n = 0
    with open(CAPS, "w", encoding="utf-8", newline="\n") as f:
        for slug in sorted(by):
            seen, caps = set(), []
            for isbn, (t, c) in sorted(by[slug].items(), key=lambda kv: (len(kv[1][0]), kv[1][0])):
                if c in seen:
                    continue
                seen.add(c)
                caps.append({"isbn": isbn, "title": t, "cap": c, "ad": bool(AD.search(c))})
            f.write(json.dumps({"slug": slug, "chars": sum(len(x["cap"]) for x in caps if not x["ad"]), "caps": caps}, ensure_ascii=False) + "\n")
            n += 1
    print(f"手元の材料の束: {n:,}頁 → {os.path.relpath(CAPS, ROOT)}")


def build():
    import yaml
    with open(D("data", "manga-list-index.json"), encoding="utf-8") as f:
        ix = json.load(f)
    rows = [dict(zip(ix["f"], r)) for r in ix["d"]]
    with open(D("data", "seeds", "slug-overrides.yml"), encoding="utf-8") as f:
        ov = (yaml.safe_load(f) or {}).get("overrides", {})
    p2s = {v["slug"]: k for k, v in ov.items() if isinstance(v, dict) and v.get("slug")}

    # 手元の材料(頁の公開 slug → 出所ごとの字数)
    mat = collections.defaultdict(dict)
    for o in jl(D(".cache", "genre-rakuten", "corpus-v2.jsonl")):
        if o.get("caption"):
            mat[o["slug"]]["楽天"] = len(o["caption"])
    for o in jl(CAPS):
        if o.get("chars"):
            mat[o["slug"]]["楽天"] = o["chars"]
    for o in jl(D(".cache", "booklive-desc.jsonl")):
        if o.get("desc"):
            mat[o["slug"]]["BookLive"] = len(o["desc"])
    for o in jl(D(".cache", "kobo-caption", "harvest.jsonl")):
        m = o.get("matched")
        if isinstance(m, str):
            try:
                m = json.loads(m.replace("'", '"'))
            except ValueError:
                m = []
        n = sum(len(x.get("cap") or "") for x in (m or []) if isinstance(x, dict) and x.get("match") == "strict")
        if n:
            mat[o["slug"]]["Kobo"] = n
    for o in jl(D("data", "seeds", "volume-desc-ja.jsonl")):
        mat[o["slug"]]["巻説明"] = mat[o["slug"]].get("巻説明", 0) + len(o.get("desc") or "")
    with open(D("data", "seeds", "synopsis-slug-ja.json"), encoding="utf-8") as f:
        for s, t in json.load(f).items():
            mat[s]["あらすじ"] = len(t if isinstance(t, str) else json.dumps(t, ensure_ascii=False))

    # 状態(台帳から)
    proposed = {o["stem"] for o in jl(D("data", "element-harvest", "assign-ledger.jsonl"))}
    proposed |= {o["stem"] for o in jl(D("data", "element-harvest", "review-ledger.jsonl")) if o.get("stem")}
    applied = {o.get("stem") for o in jl(D("data", "seeds", "element-assign-changelog.jsonl"))}

    # 原作グループ(題の前方一致 + 著者の重なり)
    def names(r):
        return {a.split("\t")[0] for a in (r.get("authors") or []) + (r.get("original_authors") or [])}
    srt = sorted(rows, key=lambda r: norm(r["title"]))
    group, base = {}, None
    for r in srt:
        t = norm(r["title"])
        if base and len(norm(base["title"])) >= 4 and t.startswith(norm(base["title"])) and names(r) & names(base):
            group[r["slug"]] = group.setdefault(base["slug"], base["slug"])
        else:
            base = r
    gsize = collections.Counter(group.values())

    out = []
    for r in rows:
        s = r["slug"]
        g = set(r.get("genres") or [])
        n_el = len(r.get("themes") or [])
        generic = bool(g) and g <= GENERIC
        m = mat.get(s, {})
        local = sum(m.values())
        tier = "A" if r.get("popularity") and r.get("anime_adapted") else "B" if r.get("popularity") else "C"
        if n_el >= 3 and not generic:
            route = "後"
        elif tier == "A":
            route = "A"
        elif local >= LOCAL_MIN:
            route = "L"
        else:
            route = "W"
        # ★ファイル名(stem)= 対応表の元の名前。 ただし元の名前のファイルが無く公開 slug のファイルが在る頁はそちら
        #   (2026-10-16: 芦屋山手お道具迎賓館 = 対応表は旧名、ファイルは公開 slug で、見直しが「頁が無い」で止まった)
        stem = p2s.get(s, s)
        if stem != s and not os.path.exists(D("data", "manga.v2", stem + ".yml")) and os.path.exists(D("data", "manga.v2", s + ".yml")):
            stem = s
        state = "適用済" if stem in applied else "案あり" if stem in proposed else "未"
        gk = group.get(s, "")
        out.append({"route": route, "state": state, "stem": stem, "slug": s, "title": r["title"], "tier": tier,
                    "group": gk if gsize.get(gk, 0) >= 2 else "", "genres": ",".join(sorted(g)), "generic_only": int(generic), "elements": n_el,
                    "local_chars": local, "sources": "+".join(sorted(m)), "year": r.get("year_started") or "", "volumes": r.get("total_volumes") or 0})
    out.sort(key=lambda x: (ROUTE_ORDER[x["route"]], -x["local_chars"], x["stem"]))
    for i, x in enumerate(out, 1):
        x["order"] = i
    return out


def write(out):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write("\t".join(COLS) + "\n")
        for x in out:
            f.write("\t".join(str(x[c]).replace("\t", " ") for c in COLS) + "\n")
    summ = {"pages": len(out), "routes": {}}
    for rt in ROUTE_ORDER:
        xs = [x for x in out if x["route"] == rt]
        summ["routes"][rt] = {"pages": len(xs), "未": sum(x["state"] == "未" for x in xs), "案あり": sum(x["state"] == "案あり" for x in xs),
                              "適用済": sum(x["state"] == "適用済" for x in xs), "要素0": sum(x["elements"] == 0 for x in xs),
                              "汎用ジャンルだけ": sum(x["generic_only"] for x in xs), "原作グループに入る頁": sum(bool(x["group"]) for x in xs)}
    with open(SUMMARY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return summ


def main():
    ap = argparse.ArgumentParser(description="ジャンル・要素の見直しの表")
    ap.add_argument("--next", type=int, default=0, help="次に見直す stem を N 件(未の行を順番どおり)")
    ap.add_argument("--route", default="", help="--next の経路を絞る(A / L / W / 後)")
    ap.add_argument("--material", action="store_true", help="手元の材料の束(楽天の巻ごとの紹介文)を作り直す")
    a = ap.parse_args()
    if a.material:
        build_material()
    out = build()
    if a.next:
        todo = [x for x in out if x["state"] == "未" and (not a.route or x["route"] == a.route)][:a.next]
        for x in todo:
            print(x["stem"])
        return
    summ = write(out)
    print(f"== 見直しの表 == {summ['pages']:,}頁 → {os.path.relpath(OUT, ROOT)}")
    print("経路\t頁\t未\t案あり\t適用済\t要素0\t汎用ジャンルだけ\t原作グループ")
    for rt, v in summ["routes"].items():
        print(f"{rt}\t{v['pages']:,}\t{v['未']:,}\t{v['案あり']:,}\t{v['適用済']:,}\t{v['要素0']:,}\t{v['汎用ジャンルだけ']:,}\t{v['原作グループに入る頁']:,}")


if __name__ == "__main__":
    main()
