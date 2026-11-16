# -*- coding: utf-8 -*-
"""Wikipedia の巻数に頁が届いていない作品(wiki-volume-gap.tsv の SHORT・確度A)を、1件ずつ「何を足せば届くか」まで調べる。

入力 = wiki-volume-gap.tsv / 頁の yml(該当分だけ) / 楽天の題(.cache/isbn-title-map.json) /
       楽天の全項目(.cache/rakuten-isbn-delta.jsonl を1パス) / 種2(.cache/db-v2.sqlite)。 外部へは出ない・モデル不使用。
出力 = docs/production-diagnostics/wiki-short-review.tsv (作品1行) / wiki-short-review-books.tsv (足せる本1行)

判定(頁のいちばん巻の多い版 = 主版 について、1..Wiki巻数 のうち欠けている番号を出し、楽天の未掲載本を当てる):
  足せる     = 欠け番号の全部に「同じ出版者記号・漫画ジャンル・著者一致・書影あり」の本がちょうど1冊ずつ
  一部足せる = 欠け番号の一部だけ
  別の版     = 未掲載の本は在るが、主版と出版者記号が違う/判型が文庫 など(= 版の追加の話で、巻抜けではない)
  別作/対象外 = 著者が合わない・漫画ジャンルでない
  当たらず   = 欠け番号に当たる本が無い
★ここは調べるだけ。 seed には書かない。
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("wvg", os.path.join(ROOT, "scripts", "_audit-wiki-volume-gap.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
norm = G.norm
DIAG = os.path.join(ROOT, "docs", "production-diagnostics")
_NUM_TAIL = re.compile(r"(?:[（(【\[]\s*)?(?:第\s*)?(\d{1,3})\s*(?:巻|集)?\s*[）)】\]]?\s*$")


def vol_no(title):
    t = unicodedata.normalize("NFKC", title or "").strip()
    m = _NUM_TAIL.search(t)
    return int(m.group(1)) if m else None


def registrant(isbn):
    """9784 の後ろの出版者記号。"""
    if not isbn or not isbn.startswith("9784"):
        return ""
    b = isbn[4:]
    two = int(b[:2])
    n = 2 if two <= 19 else 3 if two <= 69 else 4 if two <= 84 else 5 if two <= 89 else 6 if two <= 94 else 7
    return b[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="既刊(連載中)も含める。 既定は完結だけ")
    a = ap.parse_args()
    import csv
    rows = [r for r in csv.DictReader(open(os.path.join(DIAG, "wiki-volume-gap.tsv"), encoding="utf-8-sig"), delimiter="\t")
            if r["型"] == "SHORT" and r["確度"] == "A" and (a.all or r["完結"] == "完結")]

    # --- 頁 yml (公開slug ≠ ファイル名 の頁は slug 行を rg で引く) ---
    mdir = os.path.join(ROOT, "data", "manga.v2")
    path = {}
    miss = []
    for r in rows:
        p = os.path.join(mdir, r["slug"] + ".yml")
        if os.path.exists(p) and (yaml.safe_load(open(p, encoding="utf-8")) or {}).get("slug") == r["slug"]:
            path[r["slug"]] = p
        else:
            miss.append(r["slug"])
    if miss:
        want = set(miss)
        for fn in os.listdir(mdir):          # 先頭行だけ読む(中身は開かない)
            if not want:
                break
            with open(os.path.join(mdir, fn), encoding="utf-8") as f:
                heads = [f.readline().strip() for _ in range(3)]
            for head in heads:
                if head.startswith("slug:") and head[5:].strip().strip("'\"") in want:
                    s = head[5:].strip().strip("'\"")
                    path[s] = os.path.join(mdir, fn)
                    want.discard(s)
    overrides = json.load(open(os.path.join(ROOT, "data", "seeds", "edition-overrides.json"), encoding="utf-8"))
    canon = {f[:-4] for f in os.listdir(os.path.join(ROOT, "data", "seeds", "edition-canonical"))}

    # --- 楽天の題 → 幹 ---
    on_page = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    stems = defaultdict(set)
    for isbn, t in json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8")).items():
        if isinstance(t, str):
            stems[norm(G.stem(t))].add(isbn)

    stem_keys = sorted(stems)

    def stem_isbns(key):                     # 検出器と同じ: 完全一致が無く5字以上なら前方一致
        if key in stems:
            return stems[key]
        if len(key) < 5:
            return set()
        import bisect
        got, i = set(), bisect.bisect_left(stem_keys, key)
        while i < len(stem_keys) and stem_keys[i].startswith(key) and len(got) < 400:
            got |= stems[stem_keys[i]]; i += 1
        return got

    pages, want_isbn = {}, set()
    for r in rows:
        d = yaml.safe_load(open(path[r["slug"]], encoding="utf-8")) if r["slug"] in path else None
        pages[r["slug"]] = d
        r["_unl"] = sorted(i for i in stem_isbns(norm(r["題"])) if not on_page.get(i))
        want_isbn |= set(r["_unl"])
        for e in (d or {}).get("editions", []):
            for v in e.get("volumes", []):
                if v.get("isbn13"):
                    want_isbn.add(v["isbn13"])

    items = {}
    with open(os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"), encoding="utf-8") as f:
        for line in f:
            i = line[10:23]
            if i in want_isbn:
                try:
                    items[i] = json.loads(line).get("item") or {}
                except Exception:
                    pass

    con = sqlite3.connect(f"file:{os.path.join(ROOT, '.cache', 'db-v2.sqlite')}?mode=ro", uri=True)

    def in_seed2(isbn):
        return con.execute("select 1 from volumes where isbn13=? limit 1", (isbn,)).fetchone() is not None

    out, books = [], []
    for r in rows:
        d = pages[r["slug"]]
        n = int(r["Wiki巻数"])
        base = {"記事": r["記事"], "題": r["題"], "slug": r["slug"], "Wiki巻数欄": r["Wiki巻数欄"], "Wiki巻数": n}
        if not d:
            out.append(dict(base, 判定="頁ファイル不明"))
            continue
        eds = d.get("editions") or []
        main_ed = max(eds, key=lambda e: len(e.get("volumes") or []))
        vols = main_ed.get("volumes") or []
        have = {v.get("number") for v in vols}
        gaps = [k for k in range(1, n + 1) if k not in have]
        regs = Counter(registrant(v.get("isbn13") or "") for v in vols if v.get("isbn13"))
        reg = regs.most_common(1)[0][0] if regs else ""
        au = {norm(x.get("name", "")) for x in (d.get("authors") or []) + (d.get("original_authors") or [])}
        fixed = "overrides" if r["slug"] in overrides else "canonical" if os.path.basename(path[r["slug"]])[:-4] in canon else ""
        regset = set(regs)
        pubs = {norm((items.get(v.get("isbn13") or "") or {}).get("publisherName", "")) for v in vols}
        pubs |= {norm(v.get("publisher") or "") for v in vols} | {norm(main_ed.get("publisher") or "")}   # ISBN の無い古い巻の頁
        pubs -= {""}
        imprint = norm(main_ed.get("imprint") or "")
        noisbn = {v.get("number") for v in vols if not v.get("isbn13")}
        au |= {norm(x) for x in r["著者"].split("・") if x}        # 頁の著者欄が楽天と違う表記でも Wikipedia の著者で受ける
        isbn_fill = []
        dates = {v.get("number"): str(v.get("release_date") or "") for v in vols}
        EDW = re.compile(r"新装|文庫|完全版|愛蔵|ワイド|復刻|豪華|特装|限定|電子|新版|改訂|コンビニ|廉価")

        def date_fits(no, sd):
            """発売日が前後の巻のあいだに収まるか(年月だけで比べる)。 比べる相手が無ければ None。"""
            m = re.match(r"(\d{4})年(\d{1,2})月", sd or "")
            if not m:
                return None
            ym = f"{m.group(1)}-{int(m.group(2)):02d}"
            lo = max((dates[k][:7] for k in dates if k and k < no and dates[k]), default="")
            hi = min((dates[k][:7] for k in dates if k and k > no and dates[k]), default="")
            if not lo and not hi:
                return None
            return (not lo or lo <= ym) and (not hi or ym <= hi)

        cand = defaultdict(list)
        extra = []
        why = Counter()
        for i in r["_unl"]:
            it = items.get(i)
            if not it:
                why["楽天の項目なし"] += 1
                continue
            no = vol_no(it.get("title", ""))
            ia = norm(it.get("author", ""))
            a_ok = bool(ia) and any(x and (x in ia or ia in x) for x in au)
            # 漫画 = ジャンルのどれかが 001001(漫画)。 001021(BL)は判型がコミックの時だけ
            gs = str(it.get("booksGenreId", "")).split("/")
            comic = any(g.startswith("001001") for g in gs) or (any(g.startswith("001021") for g in gs) and it.get("size") == "コミック")
            same_label = bool(imprint) and norm(it.get("seriesName", "")) == imprint
            if "アンソロジー" in it.get("author", "") or G.OUT_OF_SCOPE.search(it.get("title", "")):
                why["アンソロジー/関連書"] += 1
            elif not a_ok:
                why["著者が合わない"] += 1
            elif not comic:
                why["漫画ジャンルでない"] += 1
            elif registrant(i) not in regset and norm(it.get("publisherName", "")) not in pubs and not same_label:
                why[f"出版者が別({it.get('publisherName', '')})"] += 1
            elif main_ed.get("type") == "standard" and EDW.search(it.get("title", "") + it.get("seriesName", "")):
                why["題/レーベルが別の版(新装・文庫など)"] += 1
            elif it.get("size") == "文庫" and main_ed.get("type") != "bunkobon":
                why["文庫判"] += 1
            elif no is None:
                why["巻番号が読めない"] += 1
                extra.append(f'{it.get("title", "")}[{i} {it.get("salesDate", "")}]')
            elif no in noisbn:
                why["頁のISBN無し巻に当たる"] += 1
                isbn_fill.append(no)
            elif no not in gaps:
                why["番号は頁に在る(別の版/再刊か)"] += 1
            elif date_fits(no, it.get("salesDate", "")) is False:
                why["発売日が前後の巻と合わない"] += 1
            else:
                cand[no].append((i, it))
        filled = [k for k in gaps if len(cand[k]) == 1]
        multi = [k for k in gaps if len(cand[k]) > 1]
        for k in filled:
            i, it = cand[k][0]
            img = it.get("largeImageUrl") or it.get("mediumImageUrl") or ""
            books.append({"slug": r["slug"], "題": r["題"], "版": f'{main_ed.get("type")}/{main_ed.get("imprint") or ""}',
                          "巻": k, "ISBN": i, "楽天題": it.get("title", ""), "楽天レーベル": it.get("seriesName", ""),
                          "発売日": it.get("salesDate", "") + ("(仮の日付)" if it.get("salesDate", "") == "2000年" else ""), "書影": "無" if (not img or "noimage" in img) else "有",
                          "種2に在る": "在" if in_seed2(i) else "", "頁の固定": fixed,
                          "出版者記号": "同" if registrant(i) in regset else "別(社名は同じ)"})
        nocover = sum(1 for b in books if b["slug"] == r["slug"] and b["書影"] == "無")
        if gaps and len(filled) == len(gaps):
            verdict = "足せる"
        elif filled:
            verdict = "一部足せる"
        elif not gaps:
            verdict = "主版は番号が揃っている(Wikiの数え方が違う)"
        elif any(k.startswith("出版者が別") or k == "文庫判" for k in why):
            verdict = "別の版"
        elif why.get("著者が合わない") or why.get("漫画ジャンルでない") or why.get("アンソロジー/関連書"):
            verdict = "別作/対象外"
        elif extra:
            verdict = "番号なしの本が在る(番外編など)"
        else:
            verdict = "当たらず"
        out.append(dict(base, 判定=verdict, 状態=d.get("status"), 主版=f'{main_ed.get("type")}/{main_ed.get("imprint") or ""}',
                        主版の巻数=len(vols), 版の数=len(eds), 欠け番号=",".join(map(str, gaps)),
                        足せる番号=",".join(map(str, filled)), 候補が複数=",".join(map(str, multi)),
                        書影なし=nocover or "", 未掲載冊=len(r["_unl"]),
                        外した理由=" / ".join(f"{k}×{v}" for k, v in why.most_common()), 頁の固定=fixed, ISBN無し巻に当たる本=",".join(map(str, sorted(set(isbn_fill)))), 番号なしの本=" / ".join(extra[:4])))

    cols = ["判定", "記事", "題", "slug", "状態", "Wiki巻数欄", "Wiki巻数", "主版", "主版の巻数", "版の数", "欠け番号",
            "足せる番号", "候補が複数", "書影なし", "未掲載冊", "ISBN無し巻に当たる本", "外した理由", "番号なしの本", "頁の固定"]
    order = ["足せる", "一部足せる", "別の版", "別作/対象外", "番号なしの本が在る(番外編など)", "当たらず", "主版は番号が揃っている(Wikiの数え方が違う)", "頁ファイル不明"]
    out.sort(key=lambda x: (order.index(x["判定"]), x["記事"]))
    suffix = "-all" if a.all else ""
    for name, cc, data in ((f"wiki-short-review{suffix}.tsv", cols, out),
                           (f"wiki-short-review{suffix}-books.tsv",
                            ["slug", "題", "版", "巻", "ISBN", "楽天題", "楽天レーベル", "発売日", "書影", "種2に在る", "出版者記号", "頁の固定"], books)):
        with open(os.path.join(DIAG, name), "w", encoding="utf-8", newline="\n") as f:
            f.write("\t".join(cc) + "\n")
            for x in data:
                f.write("\t".join(str(x.get(c, "")).replace("\t", " ") for c in cc) + "\n")
    c = Counter(x["判定"] for x in out)
    print(f"対象 {len(out)} 作品")
    for k in order:
        if c[k]:
            print(f"  {k}: {c[k]}")
    print(f"足せる本 {len(books)} 冊 (書影なし {sum(1 for b in books if b['書影'] == '無')} / 種2に在る {sum(1 for b in books if b['種2に在る'])})")


if __name__ == "__main__":
    main()
