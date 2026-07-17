#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""試し読みリンク収集エンジン (BookLive title_id)。skill tameshiyomi-harvest の実体。

設計方針(弱いモデル運転前提): 判断はscriptに焼く。AIの仕事は --review で出る保留の裁定のみ。
  1. 対象選定 = 人気順上位のうち未収集・未保留の作品 (--limit N)
  2. TinyFish検索 site:booklive.jp <題> <著者> → title_id をURLから正規表現抽出
  3. ゲート: 題の正規化一致(部分不可・完全一致のみ) + 著者姓一致 → 不一致は自動採用しない(保留)
  4. 検証: bviewer cid=<title_id>_001 を HEAD 200 確認(失敗=保留)
  5. 出力: data/seeds/tameshiyomi-booklive.jsonl に純粋追加(証拠込み、= シリーズ単位のanchor)。
     保留= docs/production-diagnostics/tameshiyomi-holds.tsv
  再開可能(収集済み/保留済みはskip)。429/失敗は即中断。

★全巻展開 (= 2026-07-12発見。ユーザ指摘「ドラゴンボールなら42巻分取らないとダメ」で判明):
  BookLiveのtitle_idは**シリーズ/版単位**で、vol_no(product頁)やcid末尾3桁(bviewerの巻番号)を
  変えるだけで**同一title_idのまま全巻に到達できる**(TinyFish検索不要・HEADチェックのみ)。
  実証: title_id/582763(チェンソーマン)でvol_no/001→1巻、/002→2巻。
        title_id/185409(BLEACHモノクロ版)で_001/_025/_100相当のcidが全部HEAD200。
  帰結: アンカー(シリーズ→title_id)さえ集めれば、巻数分の追加検索は不要、
  cid=f"{title_id}_{vol:03d}" をmax_edition_volumes分HEAD検証するだけで全巻リンクが揃う。

使い方:
  python scripts/_tameshiyomi-harvest.py --limit 50          # 上位50作のtitle_id(アンカー)を収集
  python scripts/_tameshiyomi-harvest.py --expand --expand-limit 100  # アンカー済みシリーズを全巻展開(検索不要・高速)
  python scripts/_tameshiyomi-harvest.py --review            # 保留一覧を表示(AIが裁定)
  python scripts/_tameshiyomi-harvest.py --accept slug=ID    # 保留を手動採用(裁定後)
  python scripts/_tameshiyomi-harvest.py --stats             # 進捗
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.request
from _idx_authors import au_name  # ★索引v2 authorsパック対応(2026-07-14)

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
SEED = os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive.jsonl")
VOLSEED = os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive-volumes.jsonl")
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
        out.append((r[isl], r[it], [au_name(a) for a in (r[ia] or [])]))
    return out


def head_ok(cid):
    try:
        req = urllib.request.Request(f"https://booklive.jp/bviewer/s/?cid={cid}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=20).status == 200
    except Exception:
        return False


def load_volumes_done():
    """slug -> set(volume已検証)"""
    done = {}
    if os.path.exists(VOLSEED):
        for line in open(VOLSEED, encoding="utf-8"):
            r = json.loads(line)
            done.setdefault(r["slug"], set()).add(r["volume"])
    return done


def volume_target_n():
    li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = li["f"]
    isl = f.index("slug")
    itv = f.index("total_volumes")
    imv = f.index("max_edition_volumes")
    out = {}
    for r in li["d"]:
        n = max(r[itv] or 0, r[imv] or 0)
        if n:
            out[r[isl]] = n
    return out


def expand_volumes(expand_limit, workers=8):
    """アンカー済み(title_id確定)シリーズを対象に、TinyFish検索なしでHEADのみ全巻展開する。
    ★HEADは並列8本(2026-07-13)。BookLive=大手CDNの軽いHEADのみなので安全。
    楽天/NDL/TinyFishの逐次レート則はここには適用されない(別ホスト・別性質)。"""
    from concurrent.futures import ThreadPoolExecutor

    anchors, _ = load_done()
    n_by_slug = volume_target_n()
    vol_done = load_volumes_done()
    targets = []
    for slug, rec in anchors.items():
        n = n_by_slug.get(slug)
        if not n:
            continue
        have = vol_done.get(slug, set())
        if len(have) >= n:
            continue  # 展開済み
        targets.append((slug, rec["title_id"], n, have))
    targets = targets[:expand_limit]
    print(f"展開対象 {len(targets)} シリーズ(アンカー済み・未全巻展開) / HEAD {workers}並列", flush=True)
    out = open(VOLSEED, "a", encoding="utf-8")
    total_new = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for slug, tid, n, have in targets:
            todo = [v for v in range(1, n + 1) if v not in have]
            results = list(pool.map(lambda v: (v, head_ok(f"{tid}_{v:03d}")), todo))
            added = 0
            for vol, ok in results:
                if ok:
                    rec = {"slug": slug, "volume": vol, "title_id": tid, "cid": f"{tid}_{vol:03d}",
                           "verified": "head200", "at": time.strftime("%Y-%m-%d")}
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    added += 1
            out.flush()
            total_new += added
            print(f"  {slug}: +{added}/{n}巻", flush=True)
            time.sleep(0.2)
    print(f"展開完了 +{total_new}巻 (seed={os.path.relpath(VOLSEED, ROOT)})")


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
            # ★[:200]切り詰め禁止(2026-07-18実害: 9,674保留の候補が評価不能化していた)。タブ/改行だけ潰して全量書く
            holds.write(f"{slug}\t{title}\t{au}\t{reason}\t{json.dumps(cand, ensure_ascii=False).replace(chr(9),' ').replace(chr(10),' ')}\n")
            holds.flush()
            n_hold += 1
        time.sleep(1.0)
    print(f"収集 {n_ok} / 保留 {n_hold} (seed={os.path.relpath(SEED, ROOT)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--accept", help="slug=title_id 形式で保留を手動採用")
    ap.add_argument("--accept-file", help="一括採用TSV(slug<TAB>title_id)。裁定済み前提・HEADゲート同等")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--expand", action="store_true", help="アンカー済みシリーズを全巻展開(検索不要)")
    ap.add_argument("--expand-limit", type=int, default=50, help="--expand で処理するシリーズ数上限")
    a = ap.parse_args()
    if a.stats:
        done, holds = load_done()
        vol_done = load_volumes_done()
        n_by_slug = volume_target_n()
        vol_rows = sum(len(v) for v in vol_done.values())
        expanded_full = sum(1 for slug, vs in vol_done.items() if len(vs) >= n_by_slug.get(slug, 1 << 30))
        print(f"収集済(アンカー) {len(done)} / 保留 {len(holds)}")
        print(f"全巻展開 = {vol_rows}巻 ({len(vol_done)}シリーズ着手、うち{expanded_full}シリーズ完了)")
        return
    if a.expand:
        expand_volumes(a.expand_limit)
        return
    if a.review:
        if os.path.exists(HOLDS):
            print(open(HOLDS, encoding="utf-8").read())
        return
    if a.accept_file:
        # ★一括採用(2026-07-18 保留裁定バッチ用): TSV(slug<TAB>title_id)を1行ずつ --accept と同じ保証で処理
        #   (HEAD200ゲート/seed追記/保留行除去)。裁定自体はAIが済ませた前提=このscriptは検証と簿記のみ。
        import concurrent.futures as _cf
        pairs = []
        seen_seed = set()
        if os.path.exists(SEED):
            for l in open(SEED, encoding="utf-8"):
                try: seen_seed.add(json.loads(l)["slug"])
                except Exception: pass
        for l in open(a.accept_file, encoding="utf-8"):
            c = l.rstrip("\n").split("\t")
            if len(c) >= 2 and c[0] and not c[0].startswith("#") and c[0] not in seen_seed:
                pairs.append((c[0], c[1]))
        print(f"一括採用: 対象{len(pairs)}(seed既存はskip済)")
        ok_pairs, ng = [], 0
        with _cf.ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(head_ok, f"{t}_001"): (s, t) for s, t in pairs}
            for fu in _cf.as_completed(futs):
                s, t = futs[fu]
                try:
                    if fu.result(): ok_pairs.append((s, t))
                    else: ng += 1
                except Exception: ng += 1
        with open(SEED, "a", encoding="utf-8") as f:
            for s, t in ok_pairs:
                f.write(json.dumps({"slug": s, "title_id": t, "cid1": f"{t}_001",
                                    "verified": "head200+manual", "at": time.strftime("%Y-%m-%d")},
                                   ensure_ascii=False) + "\n")
        done = {s for s, _ in ok_pairs}
        if os.path.exists(HOLDS):
            lines = [l for l in open(HOLDS, encoding="utf-8") if l.split("\t", 1)[0] not in done]
            open(HOLDS, "w", encoding="utf-8").writelines(lines)
        print(f"採用 {len(ok_pairs)} / HEAD失敗 {ng} (失敗分は保留のまま)")
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
