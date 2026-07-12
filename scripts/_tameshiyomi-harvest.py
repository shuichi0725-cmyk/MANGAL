#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""試し読みリンク収集エンジン (BookLive title_id)。skill tameshiyomi-harvest の実体。

設計方針(弱いモデル運転前提): 判断はscriptに焼く。AIの仕事は --review で出る保留の裁定のみ。
  1. 対象選定 = 人気順上位のうち未収集・未保留の作品 (--limit N)
  2. TinyFish検索 site:booklive.jp <題> <著者> → title_id をURLから正規表現抽出
  3. ゲート: 題の正規化一致(部分不可・完全一致のみ) + 著者姓一致 → 不一致は自動採用しない(保留)
  4. 検証: bviewer cid=<title_id>_001 を HEAD 200 確認(失敗=保留)
  5. 出力: data/seeds/tameshiyomi-booklive.jsonl に純粋追加(証拠込み)。保留= docs/production-diagnostics/tameshiyomi-holds.tsv
  再開可能(収集済み/保留済みはskip)。429/失敗は即中断。

使い方:
  python scripts/_tameshiyomi-harvest.py --limit 50          # 上位50作を収集
  python scripts/_tameshiyomi-harvest.py --review            # 保留一覧を表示(AIが裁定)
  python scripts/_tameshiyomi-harvest.py --accept slug=ID    # 保留を手動採用(裁定後)
  python scripts/_tameshiyomi-harvest.py --stats             # 進捗
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
SEED = os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive.jsonl")
HOLDS = os.path.join(ROOT, "docs", "production-diagnostics", "tameshiyomi-holds.tsv")


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = re.sub(r"[ァ-ヶ]", lambda m: chr(ord(m.group(0)) - 0x60), s)
    return re.sub(r"[\s　・!！?？:：〜~ー\-。、．.「」『』()（）☆★♥]", "", s)


def load_done():
    done, holds = {}, set()
    if os.path.exists(SEED):
        for line in open(SEED, encoding="utf-8"):
            r = json.loads(line)
            done[r["slug"]] = r
    if os.path.exists(HOLDS):
        for line in open(HOLDS, encoding="utf-8"):
            holds.add(line.split("\t")[0])
    return done, holds


def targets(limit):
    li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = li["f"]
    isl, it, ia, ipop = f.index("slug"), f.index("title"), f.index("authors"), f.index("popularity")
    rows = sorted(li["d"], key=lambda r: -(r[ipop] or 0))
    done, holds = load_done()
    out = []
    for r in rows:
        if len(out) >= limit:
            break
        if r[isl] in done or r[isl] in holds or not (r[ipop] or 0):
            continue
        out.append((r[isl], r[it], [a.get("name") for a in (r[ia] or [])]))
    return out


def head_ok(cid):
    try:
        req = urllib.request.Request(f"https://booklive.jp/bviewer/s/?cid={cid}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=20).status == 200
    except Exception:
        return False


def harvest(limit):
    from _tinyfish import search
    done, _ = load_done()
    todo = targets(limit)
    print(f"対象 {len(todo)} 作(人気順・未収集)", flush=True)
    seed = open(SEED, "a", encoding="utf-8")
    holds = open(HOLDS, "a", encoding="utf-8")
    n_ok = n_hold = 0
    for k, (slug, title, authors) in enumerate(todo):
        au = (authors[0] if authors else "")
        try:
            res = search(f"site:booklive.jp {title} {au}")
        except Exception as e:
            print(f"★検索失敗で中断(再実行で再開可): {e}")
            break
        tn = norm(title)
        cand = {}
        for h in (res.get("results") or []):
            m = re.search(r"title_id/(\d+)", h.get("url", ""))
            if not m:
                continue
            ht = norm(re.sub(r"[|｜].*$", "", h.get("title", "")))
            ht = re.sub(r"(【[^】]*】|\d+巻?$|第\d+巻)", "", ht)
            exact = (ht == tn) or ht.startswith(tn + "1") or (tn == re.sub(r"\d+$", "", ht))
            au_ok = (not au) or (norm(au)[:4] and norm(au)[:4] in norm(h.get("title", "") + h.get("snippet", "")))
            cand.setdefault(m.group(1), {"exact": False, "au": False, "ev": h.get("title", "")[:60]})
            if exact:
                cand[m.group(1)]["exact"] = True
            if au_ok:
                cand[m.group(1)]["au"] = True
        strong = [tid for tid, c in cand.items() if c["exact"] and c["au"]]
        if len(strong) == 1 and head_ok(f"{strong[0]}_001"):
            rec = {"slug": slug, "title": title, "title_id": strong[0],
                   "cid1": f"{strong[0]}_001", "verified": "head200",
                   "evidence": cand[strong[0]]["ev"], "at": time.strftime("%Y-%m-%d")}
            seed.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seed.flush()
            n_ok += 1
            print(f"  OK {slug} → {strong[0]}", flush=True)
        else:
            reason = "候補0" if not cand else ("完全一致なし" if not strong else ("複数候補" if len(strong) > 1 else "HEAD失敗"))
            holds.write(f"{slug}\t{title}\t{au}\t{reason}\t{json.dumps(cand, ensure_ascii=False)[:200]}\n")
            holds.flush()
            n_hold += 1
        time.sleep(1.0)
    print(f"収集 {n_ok} / 保留 {n_hold} (seed={os.path.relpath(SEED, ROOT)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--accept", help="slug=title_id 形式で保留を手動採用")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.stats:
        done, holds = load_done()
        print(f"収集済 {len(done)} / 保留 {len(holds)}")
        return
    if a.review:
        if os.path.exists(HOLDS):
            print(open(HOLDS, encoding="utf-8").read())
        return
    if a.accept:
        slug, tid = a.accept.split("=", 1)
        if not head_ok(f"{tid}_001"):
            print("★HEAD失敗=採用しない")
            sys.exit(1)
        with open(SEED, "a", encoding="utf-8") as f:
            f.write(json.dumps({"slug": slug, "title_id": tid, "cid1": f"{tid}_001",
                                "verified": "head200+manual", "at": time.strftime("%Y-%m-%d")},
                               ensure_ascii=False) + "\n")
        # 保留行を除去
        if os.path.exists(HOLDS):
            lines = [l for l in open(HOLDS, encoding="utf-8") if not l.startswith(slug + "\t")]
            open(HOLDS, "w", encoding="utf-8").writelines(lines)
        print("採用:", slug, tid)
        return
    harvest(a.limit)


if __name__ == "__main__":
    main()
