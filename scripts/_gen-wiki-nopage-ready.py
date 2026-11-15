# -*- coding: utf-8 -*-
"""Wikipedia に在ってサイトに頁が無い作品のうち「すぐ出せる物」だけを機械で絞る (2026-11-15 新設)。

ユーザ裁定(2026-11-15): 「ISBN と書影が楽天にあり、全巻揃っていて抜けのない物だけ出したい。 漫画以外・アダルトには気をつけて」。

  python scripts/_gen-wiki-nopage-ready.py

入力 = _audit-wiki-volume-gap.py と同じ + 楽天の全項目(.cache/rakuten-isbn-delta.jsonl を1パス)。 外部へは出ない・モデル不使用。
出力 = docs/production-diagnostics/wiki-nopage-ready.tsv (合格) / wiki-nopage-ready-rejected.tsv (落とした理由つき)

合格の条件(全部):
  1. Wikipedia の情報欄(漫画)に題と巻数が在り、サイトに頁が無い(題でも ISBN でも当たらない)
  2. 楽天の題(巻番号を落とした幹)が Wikipedia の題と**完全一致**する本が在る(前方一致は使わない)
  3. その本が 1..N で**抜けなし・重複なし**(完結 = Wikipedia の「全N巻」とぴったり / 既刊 = N 以上で連番)
  4. 全冊がどの頁にも載っていない(= 別の頁の版ではない)
  5. 全冊に楽天の書影が在る(noimage・仮書影 .gif は不可)
  6. 全冊が楽天で「漫画(コミック)」のジャンル(booksGenreId 001001…)
  7. 楽天の著者と Wikipedia の著者が重なる / 全冊が同じ出版社
  8. 成人の印が1つも無い: Wikipedia の分類・ジャンル欄 / 成人出版社・成人レーベル一覧 / 成人作家一覧 /
     種2の同題 series の adult_score / AniList の isAdult
  9. 題が掲載対象外の型(アンソロジー・小説・画集 …)でない / non-manga-drop に題が無い
★合格 = 「機械の条件を全部通った」まで。 頁を作るのは別工程(題ヨミ・役割の確定は新規登録 protocol のまま)。
"""
from __future__ import annotations
import gzip
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("wvg", os.path.join(ROOT, "scripts", "_audit-wiki-volume-gap.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
norm = G.norm
DIAG = os.path.join(ROOT, "docs", "production-diagnostics")

_NUM_TAIL = re.compile(r"(?:[（(【\[]\s*)?(?:第\s*)?(\d{1,3})\s*(?:巻|集)?\s*[）)】\]]?\s*$")
ADULT_WIKI = re.compile(r"成人向け|アダルト|18禁|R-?18|エロ漫画|エロティック|ポルノ|官能|ティーンズラブ|レディースコミック")
ADULT_CAT = re.compile(r"\[\[\s*Category\s*:[^\]]*(成人向け|アダルト|ティーンズラブ|レディースコミック|性風俗|ポルノ)[^\]]*\]\]", re.I)


def vol_no(title):
    t = unicodedata.normalize("NFKC", title or "").strip()
    m = _NUM_TAIL.search(t)
    return int(m.group(1)) if m else None


def main():
    # --- サイト(題・別名・著者) ---
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {k: i for i, k in enumerate(idx["f"])}
    site_titles, by_author = set(), defaultdict(list)
    for r in idx["d"]:
        site_titles.add(norm(r[F["title"]]))
        if r[F["subtitle"]]:
            site_titles.add(norm(f'{r[F["title"]]}{r[F["subtitle"]]}'))
        for au in (r[F["authors"]] or []) + (r[F["original_authors"]] or []):
            by_author[norm(au.split("\t")[0])].append((r[0], norm(r[F["title"]])))
    for slug, alts in json.load(open(os.path.join(ROOT, "data", "manga-alt-index.json"), encoding="utf-8")).items():
        for alt in alts or []:
            site_titles.add(norm(alt))

    on_page = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    tmap = json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8"))
    stems = defaultdict(list)
    for isbn, t in tmap.items():
        if isinstance(t, str):
            stems[norm(G.stem(t))].append(isbn)

    # --- 成人の一覧 / 種2 ---
    con = sqlite3.connect(f"file:{os.path.join(ROOT, '.cache', 'db-v2.sqlite')}?mode=ro", uri=True)
    adult_pub = {norm(x) for (x,) in con.execute("select name from adult_publishers")}
    adult_imp = {norm(x) for (x,) in con.execute("select imprint from adult_imprints")}
    adult_au = {norm(x) for (x,) in con.execute("select name from adult_mangaka_known")}
    try:
        txt = open(os.path.join(ROOT, "data", "seeds", "adult-publishers-supplement.yml"), encoding="utf-8").read()
        adult_pub |= {norm(x) for x in re.findall(r"^\s*-\s*(.+)$", txt, re.M)}
    except Exception:
        pass
    adult_pub.discard(""); adult_imp.discard(""); adult_au.discard("")
    seed2_adult, seed2_has = defaultdict(int), defaultdict(int)
    for t, sc in con.execute("select title, adult_score from series"):
        k = norm(t)
        seed2_has[k] += 1
        seed2_adult[k] = max(seed2_adult[k], sc or 0)
    anilist_adult = set()
    try:
        with gzip.open(os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz"), "rt", encoding="utf-8") as f:
            for line in f:
                if '"isAdult": true' in line or '"isAdult":true' in line:
                    d = json.loads(line)
                    m = d.get("media") or d
                    for v in (m.get("title") or {}).values():
                        if v:
                            anilist_adult.add(norm(v))
    except Exception as e:
        print(f"(AniList が読めない = isAdult の印は空: {e})")
    dropped = norm(open(os.path.join(ROOT, "data", "seeds", "non-manga-drop.yml"), encoding="utf-8").read())

    # --- 候補(頁が無い箱)を集める。 記事本文は成人の分類を見るために持つ ---
    art_text = {}
    with open(G.ARTS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            art_text[d["title"]] = d.get("text") or ""
    cands, seen_key = [], set()
    for art, t, au, pub, label, raw, other, is_main in G.load_boxes():
        nums = G.vol_numbers(raw)
        if not nums:
            continue
        key = norm(t)
        if not key or key in site_titles or key in seen_key:   # 同じ題が複数の記事に在る時は最初の1つ
            continue
        books = stems.get(key) or []
        if not books:
            continue
        seen_key.add(key)
        cands.append(dict(art=art, t=t, au=au, pub=pub, label=label, raw=raw, n=nums[0][0], complete=nums[0][1],
                          key=key, books=books, is_main=is_main))
    need = {i for c in cands for i in c["books"]}

    # --- 楽天の全項目を1パス ---
    items = {}
    pat = re.compile(r'^\{"isbn":\s*"(\d{13})"')
    with open(os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"), encoding="utf-8") as f:
        for line in f:
            m = pat.match(line)
            if m and m.group(1) in need:
                try:
                    items[m.group(1)] = json.loads(line).get("item") or {}
                except Exception:
                    pass

    ok, ng = [], []
    for c in cands:
        why, books = [], c["books"]
        its = {i: items.get(i) for i in books}
        if G.OUT_OF_SCOPE.search(c["t"]):
            why.append("題が掲載対象外の型")
        if c["key"] in dropped:
            why.append("non-manga-drop に題あり")
        listed = [i for i in books if on_page.get(i)]
        if listed:
            why.append(f"{len(listed)}冊が既に別の頁に載っている")
        if any(v is None for v in its.values()):
            why.append("楽天の全項目が手元に無い本がある")
        vols = {}
        if not why:
            # 巻番号: 1冊だけで番号なし = 1巻もの
            nos = {i: vol_no(tmap[i]) for i in books}
            if len(books) == 1 and nos[books[0]] is None:
                nos[books[0]] = 1
            if any(v is None for v in nos.values()):
                why.append("巻番号が読めない本がある")
            else:
                for i, no in nos.items():
                    vols.setdefault(no, []).append(i)
                if any(len(v) > 1 for v in vols.values()):
                    why.append("同じ巻番号の本が複数(版違いの見込み)")
                top = max(vols)
                if sorted(vols) != list(range(1, top + 1)):
                    why.append(f"巻が抜けている(手元 {sorted(vols)[:6]}… / Wiki {c['n']}巻)")
                elif c["complete"] and top != c["n"]:
                    why.append(f"巻数が合わない(楽天 {top} / Wiki 全{c['n']}巻)")
                elif not c["complete"] and top < c["n"]:
                    why.append(f"巻が足りない(楽天 {top} / Wiki 既刊{c['n']}巻)")
        if not why:
            for i, it in its.items():
                img = it.get("largeImageUrl") or ""
                if not img or "noimage" in img or ".gif" in img:
                    why.append("書影の無い本がある"); break
            if any(not str(it.get("booksGenreId", "")).startswith("001001") for it in its.values()):
                why.append("楽天のジャンルが漫画でない本がある")
            pubs = {norm(it.get("publisherName")) for it in its.values()}
            if len(pubs) > 1:
                why.append("出版社が巻で違う")
            r_au = {norm(x) for it in its.values() for x in re.split(r"[/／,、]", it.get("author") or "") if x.strip()}
            w_au = {norm(x) for x in c["au"]}
            if not w_au or not r_au or not (w_au & r_au or any(a in b or b in a for a in w_au for b in r_au if len(a) >= 2 and len(b) >= 2)):
                why.append("著者が楽天と Wikipedia で重ならない")
            # --- 成人 ---
            text = art_text.get(c["art"], "")
            head = G.templates(text, "Infobox animanga/Header")
            genre = G.clean(G.params(head[0]).get("ジャンル", "")) if head else ""
            labels = {norm(it.get("seriesName")) for it in its.values()} | {norm(c["label"])}
            allpub = pubs | {norm(c["pub"])}
            if ADULT_CAT.search(text) or ADULT_WIKI.search(genre):
                why.append("成人の印: Wikipedia の分類/ジャンル欄")
            if any(p and any(a and (a in p or p in a) for a in adult_pub) for p in allpub):
                why.append("成人の印: 出版社が成人出版社の一覧")
            if any(l and any(a and a in l for a in adult_imp) for l in labels):
                why.append("成人の印: レーベルが成人レーベルの一覧")
            if (w_au | r_au) & adult_au:
                why.append("成人の印: 著者が成人作家の一覧")
            if seed2_adult.get(c["key"], 0) > 0:
                why.append(f"成人の印: 種2 の同題 series の adult_score={seed2_adult[c['key']]}")
            if c["key"] in anilist_adult:
                why.append("成人の印: AniList isAdult")
        near = sorted({sl for x in c["au"] for sl, k2 in by_author.get(norm(x), [])
                       if len(k2) >= 3 and (k2 in c["key"] or c["key"] in k2)})
        first = its.get(sorted(vols.get(1, books))[0]) if not why else None
        row = {"記事": c["art"], "題": c["t"], "著者": "・".join(c["au"][:3]), "出版社(Wiki)": c["pub"], "レーベル(Wiki)": c["label"],
               "Wiki巻数欄": c["raw"], "楽天の冊数": len(books), "種2に題": seed2_has.get(c["key"], 0),
               "同じ著者の近い頁": ",".join(near[:3]), "記事内": "主" if c["is_main"] else "2本目以降",
               "出版社(楽天)": (first or {}).get("publisherName", ""), "レーベル(楽天)": (first or {}).get("seriesName", ""),
               "1巻発売": (first or {}).get("salesDate", ""),
               "ISBN": ",".join(sorted(books, key=lambda i: (vol_no(tmap[i]) or 0, i))), "落とした理由": " / ".join(why)}
        (ng if why else ok).append(row)

    cols = ["記事", "題", "著者", "出版社(Wiki)", "レーベル(Wiki)", "Wiki巻数欄", "楽天の冊数", "出版社(楽天)", "レーベル(楽天)", "1巻発売",
            "種2に題", "同じ著者の近い頁", "記事内", "ISBN"]
    ok.sort(key=lambda r: (r["同じ著者の近い頁"] != "", r["種2に題"] != 0, r["記事"], r["題"]))
    for name, rows, cc in (("wiki-nopage-ready.tsv", ok, cols), ("wiki-nopage-ready-rejected.tsv", ng, cols + ["落とした理由"])):
        with open(os.path.join(DIAG, name), "w", encoding="utf-8", newline="\n") as f:
            f.write("\t".join(cc) + "\n")
            for r in rows:
                f.write("\t".join(str(r.get(k, "")).replace("\t", " ") for k in cc) + "\n")
    print(f"候補(頁なし・楽天に同題の本あり) {len(cands):,} → 合格 {len(ok):,} / 落とした {len(ng):,}")
    clean = [r for r in ok if not r["同じ著者の近い頁"]]
    print(f"  合格のうち 同じ著者の近い頁なし: {len(clean):,}(種2に題なし {sum(r['種2に題'] == 0 for r in clean):,} / 種2に題あり {sum(r['種2に題'] != 0 for r in clean):,})")
    print(f"  合格のうち 近い頁あり(版ちがい/続編の見込み = 要判断): {len(ok) - len(clean):,}")
    print(f"  冊数: {sum(r['楽天の冊数'] for r in ok):,} / 1巻もの {sum(r['楽天の冊数'] == 1 for r in ok):,} / 2巻以上 {sum(r['楽天の冊数'] > 1 for r in ok):,}")
    reasons = defaultdict(int)
    for r in ng:
        for w in r["落とした理由"].split(" / "):
            w = "成人の印" if w.startswith("成人") else re.sub(r"\d+冊が", "何冊かが", re.sub(r"[\(（].*", "", w))
            reasons[w] += 1
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"    落とした理由 {k}: {v:,}")


if __name__ == "__main__":
    main()
