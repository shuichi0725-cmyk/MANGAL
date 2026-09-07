#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日次蒸留①の穴埋め: 続巻を種4に入れる前に「頁max巻と新刊巻の間の欠番」を機械回収する。

★なぜ要るか(2026-09-07 実踏):
  楽天予約harvestの窓は「未来〜今日」。**今日より前に発売された巻は構造的に入らない**。
  日次の間隔が空く/緩和一致が max+1..+3 を許すため、続巻だけを足すと頁に穴が残る。
  実例= 土竜(モグラ)の唄: 頁max95(2026-06) に 97(2026-10予約)を足すと 96(2026-08-28)が永久に欠ける。
       才女のお世話: 頁max2 に 7 が来て 3..6 が欠ける。
  NDL(B柱)は納本後に拾うが遅く、月次MADBはもっと遅い。**この日の楽天スナップショットで塞ぐのが一番安い**。

やること(classify後・apply-zokkan前に走らせる):
  1. zokkan 各行の _vol と「頁standard巻 ∪ 種4-auto巻」を比べ、欠番を列挙。
  2. 欠番だけ楽天live title検索で回収(1.3s/req・_lookup の rate gate 経由)。
     ★同定ゲート= ①分離器の base が頁題/harvest題の base と一致 ②vol が欠番 ③isbn13 が 978/979 始まり
       ④★**著者overlap必須**(頁の著者 or 今回の続巻行の著者と1人でも一致) ⑤★**原作ラノベ排除**。
     ★④⑤が要る(2026-09-07 実踏 [[novel_in_manga_page]]): 「才女のお世話」は同題のHJ文庫(原作ラノベ)が
       1..12巻あり、題一致+巻番号だけだと **ラノベ3〜6巻をコミック頁に混ぜて**しまった。
       決め手は著者= コミックだけ作画(水島空彦)が入る。ラノベ側 seriesName は空のこともある(HJ文庫1巻)ので
       レーベル名だけのゲートでは足りない。
  3. 一致した巻を classified.json の zokkan に**追記**する(= 以後は既存の全ゲート
     [slug実在/巻番号/同巻番号既在/series_key逆引き/covers seed追記]をそのまま通る)。
  ★捏造しない: 楽天に出てこない欠番は埋めず、欠番のまま worklist に残す。

usage: python scripts/_preorder-zokkan-gapfill.py [--dry-run] [--max-gap 12]
"""
import json, os, re, sys, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _preorder_title_lib as TL

_spec = importlib.util.spec_from_file_location("_lk", os.path.join(ROOT, "scripts", "_lookup.py"))
LK = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LK)

DRY = "--dry-run" in sys.argv
MAX_GAP = int(sys.argv[sys.argv.index("--max-gap") + 1]) if "--max-gap" in sys.argv else 12
CLS = os.path.join(ROOT, ".cache", "preorders", "classified.json")
AUTO = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
TRIAGE = os.path.join(ROOT, "docs", "production-diagnostics", "preorder-triage.tsv")


def load_pub2stem():
    m = {}
    p = os.path.join(ROOT, "data", "seeds", "slug-overrides.yml")
    if os.path.exists(p):
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        ov = d.pop("overrides", {}) or {}
        for stem, pub in d.items():
            if isinstance(pub, str) and pub != stem:
                m[pub] = stem
        for stem, rec in ov.items():
            pub = (rec or {}).get("slug") if isinstance(rec, dict) else None
            if pub and pub != stem:
                m[pub] = stem
    return m


P2S = load_pub2stem()


def stem_of(slug):
    if os.path.exists(f"{ROOT}/data/manga.v2/{slug}.yml"):
        return slug
    s = P2S.get(slug)
    return s if s and os.path.exists(f"{ROOT}/data/manga.v2/{s}.yml") else None


def page_info(stem):
    y = yaml.safe_load(open(f"{ROOT}/data/manga.v2/{stem}.yml", encoding="utf-8")) or {}
    ns = set()
    for e in y.get("editions") or []:
        if (e.get("type") or "standard") != "standard":
            continue
        for v in e.get("volumes") or []:
            if isinstance(v.get("number"), int):
                ns.add(v["number"])
    # ★著者ゲートは authors(=作画/主著者)だけを使う。original_authors(原作者)は
    #   原作ラノベと共有されるため、入れると「才女のお世話」型でラノベを通してしまう。
    who = {akey(a.get("name")) for a in (y.get("authors") or [])}
    return y.get("title") or "", ns, {w for w in who if w}


def akey(name):
    """著者名の照合キー(空白差を吸収)。[[author_name_space_conventions_conflict]]"""
    return re.sub(r"[\s　・,]", "", TL._nfkc(name)).lower()


def author_set(s):
    """楽天の author 欄「A/B ほか」→ 照合キー集合。"""
    out = set()
    for part in re.split(r"[/／、,]", TL._nfkc(s)):
        part = re.sub(r"(ほか|他)$", "", part.strip())
        k = akey(part)
        if k:
            out.add(k)
    return out


# ★原作ラノベ/小説レーベルの明示排除(補助ゲート。著者overlapが主ゲート)
NOVEL_SERIES = re.compile(r"文庫|ノベル|ノベルス|ノベルズ|novels?|新書|ブックス$", re.I)


def norm(s):
    """同定用の緩い正規化(記号/空白/ルビ注記を落とす)。"""
    s = TL._nfkc(s)
    s = re.sub(r"[（(][^）)]{0,12}[）)]", "", s)
    s = re.sub(r"[\s　・,.。、!！?？:：;；'\"“”‘’〜~\-−ー―_/\\|]", "", s)
    return s.lower()


def lead_fill(cls):
    """★同一batchの刊行run内で先頭巻だけ `_vol` を失う型を救う(2026-09-07 実踏)。

    分離器は「かな/漢字直後の裸数字」を確定巻にしない(ワイルド7型を壊すため)= vol_suspect 止まり。
    分類器は suspect>=2 のときだけ巻扱いにするので、**suspect==1 の第1巻だけが落ちる**。
    実例= 「そして誰もいなくなった1/2/3」(ハヤカワ・コミックス・同日3巻同時刊)で 2,3 だけが種4に入り、
          新設される通常版タブが**2巻始まり**になる([[edition_lead_gap_atom_type]] 検出器#29 と同じ絵)。
    ゲート= 同 _slug・同 base・同 publisher・同 ym・同 seriesName の兄弟に確定巻が2つ以上あり、
            その suspect 番号が兄弟の巻集合の欠番であること。ISBNは連番でなくてもよいが上記5点一致を要求。
    """
    from collections import defaultdict
    g = defaultdict(list)
    for r in cls.get("zokkan", []):
        if r.get("_slug"):
            g[(r["_slug"], norm(r.get("_base") or ""))].append(r)
    filled = []
    for (slug, _b), rows in g.items():
        conf = {r["_vol"] for r in rows if isinstance(r.get("_vol"), int)}
        if len(conf) < 2:
            continue
        for r in rows:
            if r.get("_vol") is not None:
                continue
            sp = TL.split_title(r.get("title") or "")
            n = sp.get("vol_suspect")
            if not isinstance(n, int) or n in conf or not (min(conf) - 1 <= n <= max(conf)):
                continue
            sib = next(x for x in rows if isinstance(x.get("_vol"), int))
            if (r.get("publisher"), r.get("ym"), r.get("seriesName")) != (sib.get("publisher"), sib.get("ym"), sib.get("seriesName")):
                continue
            r["_vol"] = n
            filled.append((slug, n, r["isbn"], r.get("title")))
    for slug, n, isbn, t in filled:
        print(f"  ^ 先頭欠け補完 {slug} 第{n}巻 {isbn} {t}")
    return filled


def main():
    cls = json.load(open(CLS, encoding="utf-8"))
    filled = lead_fill(cls)
    auto = yaml.safe_load(open(AUTO, encoding="utf-8")) or {"volumes": []}
    have_isbn = {str(v.get("isbn13")) for v in auto["volumes"]}
    seed4_by_slug = {}
    for v in auto["volumes"]:
        m = re.search(r"slug=([a-z0-9\-]+)", str(v.get("note") or ""))
        if m and isinstance(v.get("number"), int):
            seed4_by_slug.setdefault(m.group(1), set()).add(v["number"])

    # 1. 穴の列挙
    gaps = []          # (stem, slug, page_title, harvest_base, missing[], sample_row, who)
    for r in cls.get("zokkan", []):
        vol, slug = r.get("_vol"), r.get("_slug")
        if not isinstance(vol, int) or not slug:
            continue
        stem = stem_of(slug)
        if not stem:
            continue
        ptitle, have, who = page_info(stem)
        if not who:                       # 頁に著者が無い時だけ harvest行の著者で代用
            who = author_set(r.get("author"))
        have = have | seed4_by_slug.get(slug, set()) | seed4_by_slug.get(stem, set())
        if not have:
            continue
        mx = max(have)
        if vol <= mx + 1:
            continue
        missing = [n for n in range(mx + 1, vol) if n not in have]
        if not missing:
            continue
        if len(missing) > MAX_GAP:
            print(f"  [skip] {stem}: 欠 {len(missing)} 巻 > --max-gap {MAX_GAP} (per-case案件)")
            continue
        gaps.append((stem, slug, ptitle, r.get("_base") or "", missing, r, who))

    if not gaps:
        print("穴なし(続巻適用で欠番は生じない)")
        if filled and not DRY:
            json.dump(cls, open(CLS, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"先頭欠け補完 {len(filled)} 巻 → classified.json を更新")
        return
    for stem, slug, ptitle, base, missing, _, who in gaps:
        print(f"GAP {stem}: 欠={missing}  頁題={ptitle}  harvest題={base}  著者={sorted(who)}")

    # 2. 欠番だけ楽天live回収
    env = LK._env()
    added, notfound, rejected = [], [], []
    for stem, slug, ptitle, base, missing, row, who in gaps:
        want = set(missing)
        found = {}
        for q in dict.fromkeys([base, ptitle]):
            if not q or not want:
                continue
            try:
                items = LK.rakuten_live(env, title=q, hits=30)
            except SystemExit:
                print("★429/中断 → gapfill 打ち切り(捏造せず欠番のまま残す)")
                items = []
                want = set()
            for it in items:
                isbn = str(it.get("isbn") or "")
                if not re.match(r"^97[89]\d{10}$", isbn) or isbn in have_isbn:
                    continue
                sp = TL.split_title(it.get("title") or "")
                if sp.get("vol") not in want:
                    continue
                if norm(sp.get("base") or "") not in (norm(base), norm(ptitle)):
                    continue
                # ★著者overlap必須(原作ラノベ/同題別作の混入をここで止める)
                cand = author_set(it.get("author"))
                if not (cand & who):
                    rejected.append((stem, sp["vol"], isbn, it.get("seriesName") or "", it.get("author") or "", "著者overlap無"))
                    continue
                if NOVEL_SERIES.search(str(it.get("seriesName") or "")):
                    rejected.append((stem, sp["vol"], isbn, it.get("seriesName") or "", it.get("author") or "", "小説レーベル"))
                    continue
                prev = found.get(sp["vol"])
                if prev is None or len(cand & who) > len(author_set(prev.get("author")) & who):
                    found[sp["vol"]] = it
        for n in sorted(found):
            it = found[n]
            sd = str(it.get("salesDate") or "")
            m = re.match(r"(\d{4})年(\d{2})月(?:(\d{2})日)?", sd)
            ym = f"{m.group(1)}-{m.group(2)}" if m else None
            day = int(m.group(3)) if (m and m.group(3)) else None
            cov = it.get("largeImageUrl") or ""
            cls["zokkan"].append({
                "isbn": str(it["isbn"]), "title": it.get("title"), "titleKana": it.get("titleKana") or "",
                "author": it.get("author") or "", "authorKana": it.get("authorKana") or "",
                "publisher": it.get("publisherName") or "", "salesDate": sd, "ym": ym, "day": day,
                "unknown_date": ym is None, "cover": (cov if cov and "noimage" not in cov else None),
                "caption": it.get("itemCaption") or "", "seriesName": it.get("seriesName") or "",
                "subgenre": row.get("subgenre") or "", "_base": TL.split_title(it.get("title") or "")["base"],
                "_vol": n, "_slug": row.get("_slug"),
                "_gapfill": f"日次①穴埋め(頁max→新刊の欠番回収) stem={stem}",
            })
            added.append((stem, n, it["isbn"], it.get("title")))
        for n in sorted(want - set(found)):
            notfound.append((stem, n))

    for stem, n, isbn, t in added:
        print(f"  + {stem} 第{n}巻 {isbn} {t}")
    for stem, n, isbn, ser, au, why in rejected:
        print(f"  - 除外 {stem} 第{n}巻 {isbn} [{why}] series={ser} author={au}")
    for stem, n in notfound:
        print(f"  ? {stem} 第{n}巻 = 楽天に出ず(捏造せず欠番のまま)")

    if DRY:
        print(f"[dry-run] 回収 {len(added)} / 除外 {len(rejected)} / 未回収 {len(notfound)} / 先頭欠け補完 {len(filled)} (classified.json は書かない)")
        return
    if added or filled:
        json.dump(cls, open(CLS, "w", encoding="utf-8"), ensure_ascii=False)
    with open(TRIAGE, "a", encoding="utf-8") as f:
        for stem, n, isbn, t in added:
            f.write(f"zokkan_gapfill\t{isbn}\t\t{str(t)[:40]}\t\t\t欠番回収 stem={stem} vol={n}\n")
        for stem, n in notfound:
            f.write(f"zokkan_gap_open\t\t\t\t\t\t欠番未回収 stem={stem} vol={n}(楽天に出ず)\n")
    with open(TRIAGE, "a", encoding="utf-8") as f:
        for slug, n, isbn, t in filled:
            f.write(f"zokkan_leadfill\t{isbn}\t\t{str(t)[:40]}\t\t\t先頭欠け補完 slug={slug} vol={n}\n")
    print(f"回収 {len(added)} 巻 → classified.json の zokkan に追記(以後は既存ゲートを通る) / 未回収 {len(notfound)} / 先頭欠け補完 {len(filled)}")


if __name__ == "__main__":
    main()
