#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数字kana素材ハーベスト (= アイドル運転⑧。 2026-07-23 新設)

フリガナに数字が残る残置頁(~535)の「読み」素材を wiki live + 楽天 live から収集する。
★収集のみ(Sonnet安全)。裁定・seed適用は上位モデルが別途行う(found.jsonl を読んで
furigana-corrections.yml へ = 2026-07-23 の検証器v2/手動裁定と同じ手順)。

使い方:
  python scripts/_kana-digit-harvest.py --build-queue   # 索引から対象を再算出(冪等)
  python scripts/_kana-digit-harvest.py --limit 30      # 30頁ぶん収集(1頁=wiki1-2req+楽天≤2req)
性質: 逐次保存(1頁ごと) / 冪等(done集合) / 自然停止(queue枯れ) / 429=exit2(即中断)。
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
_lookup = importlib.import_module("_lookup")
from _wiki_host import acquire, cooldown_check, cooldown_set, release
import _rate_gate  # ★wiki/楽天のプロセス間グローバル・レートゲート

HDIR = os.path.join(ROOT, ".cache", "kana-digit-harvest")
QUEUE = os.path.join(HDIR, "queue.json")
DONE = os.path.join(HDIR, "done.json")
FOUND = os.path.join(HDIR, "found.jsonl")


def build_queue():
    import glob
    import yaml
    idx = json.load(open(os.path.join(ROOT, "data/manga-list-index.json"), encoding="utf-8"))
    fi = idx["f"]
    SI, TI, KI = fi.index("slug"), fi.index("title"), fi.index("title_kana")
    targets = []
    for r in idx["d"]:
        k = str(r[KI] or "")
        if re.search(r"[0-9０-９]", k) or "&#" in k:
            targets.append((str(r[SI]), str(r[TI]), k))
    stem_files = {os.path.basename(p)[:-4]: p for p in glob.glob(os.path.join(ROOT, "data/manga.v2/*.yml"))}
    q = []
    for slug, title, kana in targets:
        p = stem_files.get(slug)
        ibs = []
        if p:
            d = yaml.safe_load(open(p, encoding="utf-8"))
            for e in d.get("editions") or []:
                for v in e.get("volumes") or []:
                    ib = str(v.get("isbn13") or "")
                    if len(ib) == 13 and ib not in ibs:
                        ibs.append(ib)
        q.append({"slug": slug, "title": title, "kana": kana, "isbns": ibs[:2]})
    os.makedirs(HDIR, exist_ok=True)
    json.dump(q, open(QUEUE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"queue {len(q)}頁 → {QUEUE}")


def _retry_after_min(e, default=30):
    """429のRetry-Afterヘッダ(秒)を分に。 無ければdefault分。 5〜60分にクランプ。"""
    try:
        sec = int((e.headers.get("Retry-After") or "").strip())
        return max(5, min(60, -(-sec // 60)))  # 切り上げ
    except Exception:
        return default


def wiki_lead(title):
    """記事wikitext冒頭を取り、『…』（よみ）候補を抽出。(lead抜粋, yomi候補) を返す。
    ★2変種(plain / '(漫画)')を1リクエストに束ねる=wiki負荷半減で429被曝を下げる。"""
    p = {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
         "format": "json", "formatversion": "2", "redirects": "1",
         "titles": f"{title}|{title} (漫画)"}
    req = urllib.request.Request("https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p))
    req.add_header("User-Agent", "MANGAL-kana-harvest/1.0 (contact: shuichi0725@gmail.com)")
    _rate_gate.wait("wiki", 1.2)  # ★wikiグローバル間隔(⑤material-harvestと共有=合算頻度を抑え429を減らす)
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            cooldown_set(_retry_after_min(e, 30), by="kana-digit"); sys.exit(2)  # ★Retry-After尊重・既定30分
        return "", ""
    except Exception:
        return "", ""
    best_lead = ""
    for pg in (d.get("query") or {}).get("pages") or []:
        if pg.get("missing"):
            continue
        try:
            text = pg["revisions"][0]["slots"]["main"]["content"]
        except Exception:
            continue
        head = text[:2500].replace("\n", " ")
        m = re.search(r"『'''.{0,80}?'''』\s*（([^）]{1,60})）", head)
        if m:
            return head[:400], m.group(1)   # yomiが取れたら即採用
        if not best_lead:
            best_lead = head[:400]           # yomi無しでもleadは保持(最初の実在頁)
    return best_lead, ""


def run(limit):
    cooldown_check()          # 冷却中なら即exit(3)=待機せず他の柱へ
    acquire("kana-digit")     # ⑤wiki-fetchと同ホスト排他(使用中なら即exit(3))
    try:
        _run_locked(limit)
    finally:
        release("kana-digit")


def _run_locked(limit):
    if not os.path.exists(QUEUE):
        print("queueが無い → 先に --build-queue"); sys.exit(1)
    q = json.load(open(QUEUE, encoding="utf-8"))
    done = set(json.load(open(DONE, encoding="utf-8"))) if os.path.exists(DONE) else set()
    env = _lookup._env()
    todo = [it for it in q if it["slug"] not in done][:limit]
    if not todo:
        print("queue枯れ=完了(全対象収集済)。裁定は上位モデルへ"); return
    print(f"残 {sum(1 for it in q if it['slug'] not in done)} / 今回 {len(todo)}頁")
    for it in todo:
        lead, yomi = wiki_lead(it["title"])
        rk = []
        for ib in it["isbns"]:
            items = _lookup.rakuten_live_retry(env, isbn=ib, hits=3)  # ★長時間柱=429をbackoff吸収(即exitさせない)
            for x in items:
                tk = (x.get("titleKana") or "").strip()
                if tk:
                    rk.append({"isbn": ib, "titleKana": tk})
                break
        rec = {"slug": it["slug"], "title": it["title"], "kana": it["kana"],
               "wiki_yomi": yomi, "wiki_lead": lead if yomi == "" else "", "rakuten": rk}
        with open(FOUND, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        done.add(it["slug"])
        json.dump(sorted(done), open(DONE, "w", encoding="utf-8"))
        tag = "wiki✓" if yomi else ("楽天✓" if rk else "―")
        print(f"  {it['title'][:24]}: {tag}")
    print(f"今回{len(todo)}頁保存 → {FOUND}(裁定待ち)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-queue", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    if a.build_queue:
        build_queue()
    else:
        run(a.limit)
