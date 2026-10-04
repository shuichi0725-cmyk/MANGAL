#!/usr/bin/env python3
"""続巻が電子のみの作品の全件調査(報告のみ・seed には書かない)。 2026-10-04 ユーザ指示「楽天回して」。

発端 = 無人島でエルフと共同生活@COMIC(紙1〜8巻・9/10巻は電子のみで完結)。 同じ型を全件で探す。
対象 = 本番索引のうち 2巻以上・紙の最終巻が 2012年以降かつ半年以上前・status-corrections で完結確定でない
     (★連載中に限らない: 紙の最終巻から12か月で日付判定が完結にするので、ongoing だけだと本命を落とす)。
     紙が止まったのが新しい順。
1作ごと: 楽天Kobo を「新しい順」で1回 → 巻番号つき・題が完全一致・著者が一致する巻だけ数える
        (分冊/単話/合本/セット/カラー版/お試し は題で外す)。 電子の最大巻 > 紙の巻数 なら候補。
候補だけ: 残りの頁も取り、仕分ける ——
  単話の混入   = 次の巻が400円未満 / 巻番号が紙の倍以上に飛ぶ
  分巻の疑い   = 紙の期間の巻で発売日がそろわない(照合率<60%)/ 次の巻の価格が紙の期間の6割未満
  紙も出ている = 楽天ブックス(紙・品切れ含む)に次の巻がある(発売済=MANGAL未掲載 / 発売前=電子先行)
  電子先行     = 電子の次の巻が発売前
  電子のみ     = 上のどれでもない(照合一致 / 照合できず を区別)
★採用は1件ずつ判断(電子続巻の決まり)。 Kobo 1.3秒/req。 中断しても同じコマンドで続きから(.cache/ebook-only-survey-*)。
使い方: python scripts/_kobo-ebook-only-survey.py [--limit N]
"""
import argparse, glob, importlib.util, json, os, re, statistics, sys, time, unicodedata
from datetime import date

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONE = os.path.join(ROOT, ".cache", "ebook-only-survey-done.json")
CAND = os.path.join(ROOT, ".cache", "ebook-only-survey-cand.jsonl")
TSV = os.path.join(ROOT, "docs", "production-diagnostics", "ebook-only-continuation.tsv")


def _load(name, rel):
    s = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_argv, sys.argv = sys.argv, [sys.argv[0]]   # 読み込む道具が argparse を持つので一旦隠す
kd = _load("kd", "scripts/_kobo-dcont-harvest.py")   # kobo() / NOISE / VOL_PAT / norm を共用
lk = _load("lk", "scripts/_lookup.py")               # 楽天ブックス(紙)= rakuten_live_retry(作法どおり)
sys.argv = _argv
ENV = lk._env()
TODAY = date.today().strftime("%Y%m%d")


def kobo_retry(params):
    """長時間用: 失敗は 60→180→600秒 待って再試行。 それでも駄目なら例外(=中断・再実行で続きから)。"""
    last = None
    for w in (0, 60, 180, 600):
        if w:
            print(f"    Kobo 待機 {w}秒 ({last})", flush=True)
            time.sleep(w)
        try:
            return kd.kobo(params)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def ymd(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d[:8] if len(d) >= 8 else (d[:6] + "15" if len(d) >= 6 else "")


def kobo_vols(items, title, authors_n):
    out = {}
    for it in items:
        t = unicodedata.normalize("NFKC", it.get("title") or "")
        if kd.NOISE.search(t) or kd.NOISE.search(it.get("seriesName") or ""):
            continue
        m = kd.VOL_PAT.search(t.strip())
        if not m or kd.norm(t[: m.start()]) != kd.norm(title):
            continue
        if authors_n and not any(x and x in kd.norm(it.get("author")) for x in authors_n):
            continue
        n = int(m.group(1))
        if n not in out:
            out[n] = {"date": ymd(it.get("salesDate")), "price": it.get("itemPrice"), "title": it.get("title"),
                      "url": it.get("itemUrl"), "author": it.get("author")}
    return out


def paper_vols(stem):
    fp = os.path.join(ROOT, "data", "manga.v2", stem + ".yml")
    if not os.path.exists(fp):
        return {}
    d = yaml.safe_load(open(fp, encoding="utf-8")) or {}
    best = max((e.get("volumes") or [] for e in d.get("editions") or []),
               key=lambda vs: sum(1 for v in vs if isinstance(v.get("number"), int)), default=[])
    return {v["number"]: ymd(v.get("release_date")) for v in best if isinstance(v.get("number"), int)}


def classify(title, pm, kv, pv):
    km = max(kv)
    nxt = min(n for n in kv if n > pm)
    nv = kv[nxt]
    # 紙の期間の照合(同じ番号の電子版が紙と同じ頃=31日以内に出ているか)
    both = [n for n in kv if n <= pm and pv.get(n) and kv[n]["date"]]
    ok = 0
    for n in both:
        a, b = pv[n], kv[n]["date"]
        try:
            if abs((date(int(a[:4]), int(a[4:6]), int(a[6:8])) - date(int(b[:4]), int(b[4:6]), int(b[6:8]))).days) <= 31:
                ok += 1
        except ValueError:
            pass
    ratio = ok / len(both) if both else None
    prices = [kv[n]["price"] for n in kv if n <= pm and kv[n]["price"]]
    med = statistics.median(prices) if prices else None
    info = {"next": nxt, "next_price": nv["price"], "next_date": nv["date"], "align": f"{ok}/{len(both)}",
            "kobo_max": km, "kobo_title": nv["title"], "kobo_url": nv["url"], "author": nv["author"]}
    if (nv["price"] or 0) and nv["price"] < 400 or (km > pm * 2 and km - pm > 10):
        return "単話の混入", info
    if (ratio is not None and len(both) >= 2 and ratio < 0.6) or (med and nv["price"] and nv["price"] < med * 0.6):
        return "分巻の疑い", info
    paper = []
    for it in lk.rakuten_live_retry(ENV, title=f"{title} {nxt}", hits=30) or []:
        tt = unicodedata.normalize("NFKC", it.get("title") or "")
        if kd.norm(title) in kd.norm(tt) and re.search(rf"(?<!\d){nxt}(?!\d)", tt):
            paper.append({"isbn": it.get("isbn"), "date": ymd(it.get("salesDate")), "title": it.get("title")})
    if paper:
        info["paper"] = paper[0]
        return ("紙は発売済(MANGAL未掲載)" if paper[0]["date"] and paper[0]["date"] <= TODAY else "電子先行(紙も予約中)"), info
    if nv["date"] and nv["date"] > TODAY:
        return "電子先行(電子が発売前)", info
    return ("電子のみ(照合一致)" if ratio is not None and len(both) >= 2 else "電子のみ(照合できず)"), info


def write_tsv():
    seen = {}
    if os.path.exists(CAND):
        for l in open(CAND, encoding="utf-8"):
            try:
                c = json.loads(l)
                seen[c["slug"]] = c
            except ValueError:
                pass
    order = ["電子のみ(照合一致)", "電子のみ(照合できず)", "電子先行(電子が発売前)", "電子先行(紙も予約中)",
             "紙は発売済(MANGAL未掲載)", "分巻の疑い", "単話の混入"]
    rows = sorted(seen.values(), key=lambda c: (order.index(c["class"]) if c["class"] in order else 99, -(c["kobo_max"] - c["paper_max"])))
    with open(TSV, "w", encoding="utf-8", newline="\n") as f:
        f.write("class\tslug\ttitle\tpaper_max\tpaper_last\tkobo_max\tnext\tnext_date\tnext_price\talign\tpaper_isbn\tkobo_title\tkobo_url\tauthor\n")
        for c in rows:
            p = c.get("paper") or {}
            f.write("\t".join(str(x) for x in (c["class"], c["slug"], c["title"], c["paper_max"], c["paper_last"], c["kobo_max"],
                                                 c["next"], c["next_date"], c["next_price"], c["align"], p.get("isbn", ""),
                                                 c["kobo_title"], c["kobo_url"], c["author"])) + "\n")
    from collections import Counter
    return Counter(c["class"] for c in seen.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0=全部")
    a = ap.parse_args()
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    I = {k: i for i, k in enumerate(idx["f"])}
    sc = (yaml.safe_load(open(os.path.join(ROOT, "data", "seeds", "status-corrections.yml"), encoding="utf-8")) or {}).get("corrections", {})
    verified = {k for k, v in sc.items() if (v or {}).get("status") == "completed"}
    pub2stem = {v: k for k, v in json.load(open(os.path.join(ROOT, ".cache", "prod-page-slugs.json"), encoding="utf-8")).items()}
    cut = time.strftime("%Y-%m", time.localtime(time.time() - 183 * 86400))
    done = json.load(open(DONE, encoding="utf-8")) if os.path.exists(DONE) else {}
    rows = [d for d in idx["d"] if (d[I["max_edition_volumes"]] or 0) >= 2 and d[I["slug"]] not in verified
            and "2012" <= str(d[I["latest_date"]] or "")[:4] and str(d[I["latest_date"]] or "")[:7] <= cut]
    total = len(rows)
    rows = [d for d in rows if d[I["slug"]] not in done]
    rows.sort(key=lambda d: str(d[I["latest_date"]] or ""), reverse=True)
    if a.limit:
        rows = rows[: a.limit]
    print(f"対象 {total} 作 / 済 {len(done)} / 今回 {len(rows)}", flush=True)
    cf = open(CAND, "a", encoding="utf-8", newline="\n")
    n = n_c = 0
    try:
        for d in rows:
            slug, title = d[I["slug"]], d[I["title"]]
            pm = int(d[I["max_edition_volumes"]] or 0)
            authors_n = [kd.norm(str(x).split("\t")[0]) for x in (d[I["authors"]] or [])]
            r = kobo_retry({"title": title, "sort": "-releaseDate"})
            kv = kobo_vols(r.get("Items") or [], title, authors_n)
            if kv and max(kv) > pm:
                for pg in range(2, min(int(r.get("pageCount") or 1), 6) + 1):   # 照合用に古い巻も(最大6頁=180件)
                    r2 = kobo_retry({"title": title, "sort": "-releaseDate", "page": pg})
                    for k, v in kobo_vols(r2.get("Items") or [], title, authors_n).items():
                        kv.setdefault(k, v)
                pv = paper_vols(pub2stem.get(slug, slug))
                cls, info = classify(title, pm, kv, pv)
                rec = {"slug": slug, "title": title, "class": cls, "paper_max": pm, "paper_last": d[I["latest_date"]],
                       **info, "at": time.strftime("%Y-%m-%d")}
                cf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                cf.flush()
                n_c += 1
                print(f"  [{cls}] {title} 紙{pm}→電子{info['kobo_max']} 次{info['next']}巻 {info['next_date']} "
                      f"{info['next_price']}円 照合{info['align']}", flush=True)
            done[slug] = {"paper": pm, "kobo": max(kv) if kv else None}
            n += 1
            if n % 50 == 0:
                json.dump(done, open(DONE, "w", encoding="utf-8"), ensure_ascii=False)
                print(f"  …{n}/{len(rows)} 済(候補 {n_c})", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"★中断(同じコマンドで続きから): {e}", flush=True)
    finally:
        json.dump(done, open(DONE, "w", encoding="utf-8"), ensure_ascii=False)
        cnt = write_tsv()
        print(f"今回 {n}作 / 候補 {n_c} → {TSV}\n累計の仕分け: {dict(cnt)}", flush=True)


if __name__ == "__main__":
    main()
