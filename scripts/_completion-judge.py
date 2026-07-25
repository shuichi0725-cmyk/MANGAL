#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完結判定パイプライン (= 2026-07-16 ユーザ設計。チェンソーマン24巻「堂々完結!!」型)

連載中(status!=completed)の頁の**最新巻の楽天caption**を読み、完結明示文言を拾って
status-corrections.yml(既存のpromote結線済みseed)へ適用するための3段構え:

  Sonnet(アイドル): --queue / --backlog → worksheet記入(明示文言のみtrue) → --collect
  Opus+(週次前)   : candidates TSV を再判定 → --apply → reflect --only <touched>

modes:
  --queue            日次の新刊巻タッチ分(zokkan-touched/backward a-touched)だけ判定キューへ(caption無しは翌日再試行)
  --backlog --limit N  連載中全頁のbacklog一括スイープ(resume=judgedレジャー。caption無しも記帳=一回きり)
  --collect          Sonnet記入済みworksheet → completion-candidates.tsv へ(true行のみ)+judged記帳
  --apply [--slugs a,b|--all]  候補TSV → status-corrections.yml へ純粋追加(既存キーskip)+touched出力
  --stats            現在地

caption源: ①preorders-latest-full(harvest) ②rakuten-isbn-delta.jsonl(cache) ③live楽天(1.2s/req・429即中断)。
判定規律(worksheet記入者向け): 明示文言のみ completed=true(堂々完結/ついに完結/最終巻/最終回/完結巻/大団円/閉幕)。
  偽陽性=false: 最終章突入/クライマックス/第一部完/アニメ完結/完結記念(既刊宣伝)/「完結間近」。曖昧=false(fail-closed)。
"""
import argparse, glob, json, os, re, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()

LEDGER = os.path.join(ROOT, "data", "seeds", "completion-judged.jsonl")   # isbn単位のresumeレジャー(git)
WORK = os.path.join(ROOT, ".cache", "completion")
WS = os.path.join(WORK, "worksheet.jsonl")
CAND = os.path.join(ROOT, "docs", "production-diagnostics", "completion-candidates.tsv")
CORR = os.path.join(ROOT, "data", "seeds", "status-corrections.yml")
os.makedirs(WORK, exist_ok=True)

KEYW = re.compile(r"完結|最終巻|最終回|フィナーレ|大団円|閉幕|最終章|完結編|最終\d+巻|堂々完|ついに…?終|終幕")


def load_ledger():
    done = {}
    if os.path.exists(LEDGER):
        for ln in open(LEDGER, encoding="utf-8"):
            try:
                d = json.loads(ln)
                done[d["isbn"]] = d.get("r", "")
            except Exception:
                pass
    return done


def mark(isbn, r):
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"isbn": isbn, "r": r, "at": TODAY}, ensure_ascii=False) + "\n")


def latest_vol(page):
    best = None
    for e in page.get("editions") or []:
        pools = [e.get("volumes") or []] + [v.get("volumes") or [] for v in e.get("versions") or []]
        for vol_list in pools:
            for v in vol_list:
                if not v.get("isbn13"):
                    continue
                key = (v.get("number") or 0, str(v.get("release_date") or ""))
                if best is None or key > best[0]:
                    best = (key, v)
    return best[1] if best else None


def caption_sources(need):
    """need={isbn} → {isbn: caption}。cache2系を1passずつ。"""
    out = {}
    p1 = os.path.join(ROOT, ".cache", "preorders", "preorders-latest-full.jsonl")
    if os.path.exists(p1):
        for ln in open(p1, encoding="utf-8"):
            try:
                d = json.loads(ln)
            except Exception:
                continue
            ib = re.sub(r"\D", "", str(d.get("isbn", "")))
            if ib in need and d.get("caption") and ib not in out:
                out[ib] = d["caption"]
    p2 = os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl")
    if os.path.exists(p2) and len(out) < len(need):
        for ln in open(p2, encoding="utf-8"):
            if not any(x in ln for x in need):
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            ib = re.sub(r"\D", "", str(d.get("isbn", "")))
            cap = (d.get("item") or {}).get("itemCaption")
            if ib in need and cap and ib not in out:
                out[ib] = cap
    return out


def fetch_live(isbn):
    from _lookup import rakuten_live_retry, _env
    items = rakuten_live_retry(_env(), isbn=isbn, hits=3)  # ★長時間柱=429をbackoff吸収
    for it in items:
        if it.get("itemCaption"):
            return it["itemCaption"]
    return None


def emit_targets(targets, live_budget, mark_nocaption):
    """targets=[(slug, vol_no, isbn, date)] → worksheet追記+no-hit/judged記帳"""
    done = load_ledger()
    targets = [t for t in targets if t[2] not in done]
    if not targets:
        print("対象0(全て判定済み)"); return 0
    caps = caption_sources({t[2] for t in targets})
    ws_rows, live_used = [], 0
    for slug, vol, isbn, date in targets:
        cap = caps.get(isbn)
        if cap is None and live_budget and live_used < live_budget:
            try:
                cap = fetch_live(isbn); live_used += 1
            except SystemExit:
                print("★楽天429→中断(進捗は保存済)"); break
            except Exception:
                cap = None
        if not cap:
            if mark_nocaption:
                mark(isbn, "nocaption")
            continue
        if not KEYW.search(cap):
            mark(isbn, "nohit")
            continue
        ws_rows.append({"slug": slug, "vol": vol, "isbn": isbn, "date": date,
                        "caption": cap[:600],
                        "TODO": {"completed": None, "quote": "", "note": ""}})
    with open(WS, "a", encoding="utf-8") as f:
        for r in ws_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"worksheet追記 {len(ws_rows)} / no-hit記帳 {len(targets)-len(ws_rows)}件相当 / live照会 {live_used}")
    if ws_rows:
        print(f"→ Sonnet: {WS} のTODOを記入(明示文言のみtrue・quote必須) → --collect")
    return len(ws_rows)


def mode_queue(args):
    slugs = set()
    p = os.path.join(ROOT, ".cache", "preorders", "zokkan-touched.json")
    if os.path.exists(p):
        slugs |= set(json.load(open(p)))
    for p in glob.glob(os.path.join(ROOT, ".cache", "backward", "*", "a-touched.json")):
        slugs |= set(json.load(open(p)))
    targets = []
    for s in sorted(slugs):
        fp = os.path.join(ROOT, "data", "manga.v2", f"{s}.yml")
        if not os.path.exists(fp):
            continue
        d = yaml.safe_load(open(fp, encoding="utf-8"))
        if d.get("status") == "completed":
            continue
        v = latest_vol(d)
        if v:
            targets.append((s, v.get("number"), str(v["isbn13"]), str(v.get("release_date") or "")))
    print(f"queue対象(新刊タッチ頁・連載中): {len(targets)}")
    emit_targets(targets, live_budget=args.live, mark_nocaption=False)


def mode_backlog(args):
    done = load_ledger()
    targets = []
    for fp in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
        if len(targets) >= args.limit:
            break
        d = yaml.safe_load(open(fp, encoding="utf-8"))
        if d.get("status") == "completed":
            continue
        v = latest_vol(d)
        if not v or str(v["isbn13"]) in done:
            continue
        targets.append((d.get("slug") or os.path.basename(fp)[:-4], v.get("number"), str(v["isbn13"]), str(v.get("release_date") or "")))
    print(f"backlog対象(連載中・未判定): {len(targets)} (limit={args.limit})")
    emit_targets(targets, live_budget=args.live, mark_nocaption=True)


def mode_collect(args):
    if not os.path.exists(WS):
        print("worksheet無し"); return
    rows = [json.loads(l) for l in open(WS, encoding="utf-8") if l.strip()]
    unfilled = [r for r in rows if r.get("TODO", {}).get("completed") is None]
    if unfilled:
        print(f"★未記入 {len(unfilled)} 行あり → 記入後に --collect"); return
    new = 0
    if not os.path.exists(CAND):
        open(CAND, "w", encoding="utf-8").write("slug\tvol\tisbn\tdate\tquote\tnote\n")
    with open(CAND, "a", encoding="utf-8") as f:
        for r in rows:
            t = r["TODO"]
            if t.get("completed") is True:
                if not str(t.get("quote", "")).strip():
                    print(f"  ★quote無しのtrue={r['slug']} → skip(根拠必須)"); continue
                f.write(f"{r['slug']}\t{r['vol']}\t{r['isbn']}\t{r['date']}\t{t['quote']}\t{t.get('note','')}\n")
                mark(r["isbn"], "candidate")
                new += 1
            else:
                mark(r["isbn"], "judged-false")
    os.remove(WS)
    print(f"候補追記 {new} → {CAND} / worksheetクリア")
    if new:
        print("→ 週次前(Opus+)に「完結適用して」= --apply で status-corrections へ")


def mode_apply(args):
    if not os.path.exists(CAND):
        print("候補TSV無し"); return
    rows = [l.rstrip("\n").split("\t") for l in open(CAND, encoding="utf-8") if l.strip()][1:]
    sel = None if args.all else {s.strip() for s in (args.slugs or "").split(",") if s.strip()}
    if not args.all and not sel:
        print("--apply には --all か --slugs a,b を指定(Opus+の再判定を経てから)"); return
    doc = yaml.safe_load(open(CORR, encoding="utf-8")) or {"corrections": {}}
    corr = doc.setdefault("corrections", {})
    touched, kept = [], []
    for r in rows:
        slug, vol, isbn, date, quote = r[0], r[1], r[2], r[3], r[4] if len(r) > 4 else ""
        if sel is not None and slug not in sel:
            kept.append(r); continue
        if slug in corr:
            print(f"  既存キーskip: {slug}"); continue
        y = re.match(r"(\d{4})", date or "")
        corr[slug] = {"status": "completed", "year_ended": int(y.group(1)) if y else None,
                      "source": "rakuten-caption", "evidence": quote[:120], "vol": int(vol) if str(vol).isdigit() else vol,
                      "added_at": TODAY}
        touched.append(slug)
    yaml.dump(doc, open(CORR, "w", encoding="utf-8"), allow_unicode=True, sort_keys=True, width=200)
    with open(CAND, "w", encoding="utf-8") as f:
        f.write("slug\tvol\tisbn\tdate\tquote\tnote\n")
        for r in kept:
            f.write("\t".join(r) + "\n")
    print(f"status-corrections追加 {len(touched)} / TSV残 {len(kept)}")
    if touched:
        print("次: python scripts/_reflect-targeted.py --only " + ",".join(touched) + " --push")


def mode_stats(args):
    done = load_ledger()
    from collections import Counter
    c = Counter(done.values())
    ws = len([1 for _ in open(WS, encoding="utf-8")]) if os.path.exists(WS) else 0
    cand = max(0, len(open(CAND, encoding="utf-8").read().splitlines()) - 1) if os.path.exists(CAND) else 0
    print(f"judged {len(done)} ({dict(c)}) / worksheet {ws} / candidates {cand}")


ap = argparse.ArgumentParser()
ap.add_argument("--queue", action="store_true")
ap.add_argument("--backlog", action="store_true")
ap.add_argument("--collect", action="store_true")
ap.add_argument("--apply", action="store_true")
ap.add_argument("--stats", action="store_true")
ap.add_argument("--limit", type=int, default=300)
ap.add_argument("--live", type=int, default=100, help="live楽天照会の上限/回")
ap.add_argument("--slugs")
ap.add_argument("--all", action="store_true")
a = ap.parse_args()
if a.queue:
    mode_queue(a)
elif a.backlog:
    mode_backlog(a)
elif a.collect:
    mode_collect(a)
elif a.apply:
    mode_apply(a)
else:
    mode_stats(a)
