#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""試し読み保留の裁定装置 (= 2026-07-18。snippet頼みをやめ、BookLive商品ページの実題・実著者で突合)

ユーザ裁定「枯れるまでやって。無理にマッチはしなくてよいけどきちんと調べて」の実装:
  1. fetch-meta  保留の全候補tidの商品頁(vol_no/001)を直GET→実題+著者を .cache に貯める(再開可能・6並列)
  2. compare     実題×頁題+著者で決定的突合 → accept/mismatch(調査済み台帳)/ambiguous(AI目視行き) に三分
  3. (採用は既存の _tameshiyomi-harvest.py --accept-file で。HEADゲート込み)

★無理マッチ防止: 完全一致(巻尾のみ許容)+著者一致だけを accept。分冊版/カラー版/お試し版は自動採用しない。
★調査済み台帳 .cache/tameshiyomi-adjudication.jsonl = mismatch確定slugを記録(次回round はskip=枯れ判定に使う)。
"""
import concurrent.futures as cf
import io
import json
import os
import re
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOLDS = os.path.join(ROOT, "docs", "production-diagnostics", "tameshiyomi-holds.tsv")
META = os.path.join(ROOT, ".cache", "tameshiyomi-tid-meta.jsonl")
LEDGER = os.path.join(ROOT, ".cache", "tameshiyomi-adjudication.jsonl")
UA = {"User-Agent": "Mozilla/5.0"}

BAD_EDITION = re.compile(r"分冊|カラー版|モノクロ版|無料お試し|期間限定|合本|セット|【単話】|話売り|フルカラー")


def load_holds():
    rows = []
    for l in io.open(HOLDS, encoding="utf-8"):
        c = l.rstrip("\n").split("\t")
        if len(c) >= 5:
            try:
                cand = json.loads(c[4])
            except Exception:
                # ★旧[:200]切り詰め行の救済(2026-07-18): 壊れJSONからtidだけregex回収。
                #   compareはmeta(商品頁実取得)で判定するのでev欠落は問題ない。
                cand = {tid: {} for tid in re.findall(r'"(\d{3,9})":', c[4])}
            rows.append({"slug": c[0], "title": c[1], "author": c[2], "reason": c[3], "cand": cand})
    return rows


def norm(t):
    t = str(t or "")
    t = re.sub(r"[\s　【】\[\]()（）!！?？・:：、。~〜･'’\"”-]", "", t)
    return t.lower()


def strip_vol_tail(t):
    """BookLive題の末尾巻表示を剥がす: 「超人X 1」「よわよわ先生（10）」「上」等"""
    t = re.sub(r"\s*[|｜]\s*ブックライブ.*$", "", t)
    for _ in range(3):
        t = re.sub(r"[\s　]*(?:[0-9０-９]{1,3}|VOL\.?[0-9０-９]{1,3}|[（(][0-9０-９]{1,3}[)）]|上|下|巻)$", "", t).rstrip()
    return t


def fetch_one(tid):
    url = f"https://booklive.jp/product/index/title_id/{tid}/vol_no/001"
    try:
        req = urllib.request.Request(url, headers=UA)
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    except Exception as e:
        return {"tid": tid, "http": f"err:{str(e)[:40]}"}
    m = re.search(r'property="og:title" content="([^"]+)"', html) or re.search(r"<title>([^<]+)</title>", html)
    title = (m.group(1) if m else "").strip()
    authors = []
    for a in re.findall(r'/author/[^"]*"[^>]*>([^<]+)<', html):
        a = a.strip()
        if a and "おすすめ" not in a and a not in authors:
            authors.append(a)
    return {"tid": tid, "http": "200", "bl_title": title, "bl_authors": authors[:6]}


def cmd_fetch_meta(limit=0):
    have = {json.loads(l)["tid"] for l in io.open(META, encoding="utf-8")} if os.path.exists(META) else set()
    tids = []
    for r in load_holds():
        for tid in r["cand"]:
            if tid not in have:
                tids.append(tid)
    tids = sorted(set(tids))
    if limit:
        tids = tids[:limit]
    print(f"fetch-meta: 未取得 {len(tids):,} (取得済 {len(have):,})")
    n = 0
    with io.open(META, "a", encoding="utf-8") as f, cf.ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(fetch_one, tids):
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            n += 1
            if n % 500 == 0:
                f.flush(); print(f"  ...{n}/{len(tids)}")
    print(f"fetch-meta 完了: +{n}")


def cmd_compare():
    meta = {}
    for l in io.open(META, encoding="utf-8"):
        d = json.loads(l)
        if d.get("http") == "200":
            meta[d["tid"]] = d
    ledger = {json.loads(l)["slug"] for l in io.open(LEDGER, encoding="utf-8")} if os.path.exists(LEDGER) else set()
    acc, amb, mis, nodata = [], [], [], 0
    led_new = []
    for r in load_holds():
        slug, title, author = r["slug"], r["title"], r["author"]
        if slug in ledger or not r["cand"]:
            continue
        nt = norm(title)
        page_aus = {norm(a) for a in re.split(r"[/、,・]", author or "") if a.strip()}
        exact_hits, close_hits = [], []
        seen_meta = 0
        for tid in r["cand"]:
            m = meta.get(tid)
            if not m:
                continue
            seen_meta += 1
            bt_raw = m.get("bl_title", "")
            bt = norm(strip_vol_tail(bt_raw))
            bl_aus = {norm(a) for a in m.get("bl_authors", [])}
            au_ok = (not page_aus) or bool(page_aus & bl_aus) or any(p and any(p in b or b in p for b in bl_aus) for p in page_aus)
            if not bt or not au_ok:
                continue
            if BAD_EDITION.search(bt_raw):
                close_hits.append((tid, bt_raw)); continue
            if bt == nt:
                exact_hits.append((tid, bt_raw))
            elif bt.startswith(nt) or nt.startswith(bt):
                close_hits.append((tid, bt_raw))
        if not seen_meta:
            nodata += 1
        elif len({t for t, _ in exact_hits}) == 1:
            acc.append((slug, exact_hits[0][0], title, exact_hits[0][1]))
        elif exact_hits:
            amb.append((slug, title, author, "複数exact", json.dumps(exact_hits[:4], ensure_ascii=False)))
        elif close_hits:
            amb.append((slug, title, author, "近似のみ", json.dumps(close_hits[:4], ensure_ascii=False)))
        else:
            mis.append(slug)
            led_new.append({"slug": slug, "verdict": "mismatch_confirmed", "at": time.strftime("%Y-%m-%d"),
                            "note": "全候補の実題/著者が不一致(商品頁実取得で確認)"})
    with io.open(os.path.join(ROOT, ".cache", "tameshiyomi-accept-batch2.tsv"), "w", encoding="utf-8") as f:
        for s, tid, t, bt in acc:
            f.write(f"{s}\t{tid}\n")
    with io.open(os.path.join(ROOT, ".cache", "tameshiyomi-ambiguous.tsv"), "w", encoding="utf-8") as f:
        for row in amb:
            f.write("\t".join(row) + "\n")
    with io.open(LEDGER, "a", encoding="utf-8") as f:
        for d in led_new:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"compare: accept {len(acc):,} / ambiguous(目視行き) {len(amb):,} / 不一致確定 {len(mis):,} / meta未取得 {nodata:,}")
    print("  accept → .cache/tameshiyomi-accept-batch2.tsv (採用は --accept-file で)")
    print("  目視   → .cache/tameshiyomi-ambiguous.tsv")
    # 目視サンプル
    import random
    random.seed(11)
    for s, tid, t, bt in random.sample(acc, min(20, len(acc))):
        print(f"  OK例: {t[:22]!r} == {bt[:40]!r}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "compare"
    if cmd == "fetch-meta":
        lim = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        cmd_fetch_meta(lim)
    else:
        cmd_compare()
