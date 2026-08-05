# -*- coding: utf-8 -*-
"""JPRO出版権検索ハーベスト (= アイドル運転の柱⑫。2026-08-05 ユーザ裁定で新設)

出版社が自分で登録する権利DB(jpro2.jpo.or.jp)から、巻抜け未解決slugの題名検索結果を
**無判断で全量取得**して台帳に貯める。人気作は関連本込みで100行超だが、そのまま保存
(= 取れる情報は全部取る。抜けの判定・適用は後段のOpus「JPRO判定して」の専権)。

運転(Sonnet):
  python scripts/_jpro-harvest.py --build-queue   # queue再算出(巻抜け台帳の未解決slug。Opus作業)
  python scripts/_jpro-harvest.py --limit 100     # 1バッチ(~4分)。再起動で続き
  python scripts/_jpro-harvest.py --stats         # 現在地

- 成果 = data/seeds/jpro-harvest.jsonl に1slug1行追記(逐次保存・停止しても残る)
- 進捗 = .cache/jpro-harvest/done.json(冪等再開)
- レート = 2.0秒/req(1slug=1POST。セッションは50reqごとに取り直し)
- 失敗/429 = backoffで数回吸収→ダメなら進捗保存して終了(再起動で続き)
"""
import argparse
import glob
import http.cookiejar
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from yaml import CSafeLoader as _L
except ImportError:
    from yaml import SafeLoader as _L

URL = "https://jpro2.jpo.or.jp/limit/pubrights/Index"
QUEUE = os.path.join(ROOT, ".cache", "jpro-queue.json")
DONE = os.path.join(ROOT, ".cache", "jpro-harvest", "done.json")
LEDGER = os.path.join(ROOT, "data", "seeds", "jpro-harvest.jsonl")
RATE = 2.0


def _opener():
    # このPCのPython素の証明書ストアでは検証が通らない(certifi未導入)。
    # 読み取り専用・認証情報を送らない前提で検証を外す(JPRO記憶メモ参照)。
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                     urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]
    return op


def _session(op):
    html = op.open(URL, timeout=30).read().decode("utf-8", "replace")
    m = re.search(r'name="_token" value="([^"]+)"', html)
    if not m:
        raise RuntimeError("JPRO: _token取得失敗(画面構造変化?)")
    return m.group(1)


def _search(op, token, title):
    data = urllib.parse.urlencode([("_token", token), ("media", "0"), ("product_id", ""),
                                   ("title_text", title), ("contributorName", ""),
                                   ("submit_pubrights_search", "検索"), ("torikyo-flag", "0")]).encode()
    res = op.open(urllib.request.Request(URL, data=data), timeout=45).read().decode("utf-8", "replace")
    body = re.sub(r"<script.*?</script>", "", res, flags=re.S)
    hits = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S)]
        # [媒体, ebookflag, キーコード, 出版物名, 発行元出版社, 出版権]
        if len(cells) >= 5 and re.match(r"97[89]-", cells[2] or ""):
            hits.append({"isbn13": re.sub(r"[^0-9Xx]", "", cells[2]),
                         "title": cells[3], "publisher": cells[4], "media": cells[0]})
    return hits


def build_queue():
    tsv = os.path.join(ROOT, "docs", "production-diagnostics", "preview-volgap-local.tsv")
    slugs = {}
    for ln in io.open(tsv, encoding="utf-8"):
        c = ln.rstrip("\n").split("\t")
        if len(c) >= 4 and (c[3].startswith("手掛かりなし") or c[3].startswith("種2在")):
            slugs.setdefault(c[0], []).append(c[2])
    path_of = {}
    for fp in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")) + glob.glob(os.path.join(ROOT, ".preview-data", "manga", "*.yml")):
        path_of.setdefault(os.path.basename(fp)[:-4], fp)
    flat = {k.replace("-", ""): k for k in path_of}
    q = []
    miss = 0
    for slug, vols in sorted(slugs.items()):
        real = slug if slug in path_of else flat.get(slug.replace("-", ""))
        if not real:
            miss += 1
            continue
        d = yaml.load(io.open(path_of[real], encoding="utf-8"), Loader=_L)
        t = d.get("title")
        if t:
            q.append({"slug": real, "title": str(t), "missing": vols})
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    json.dump(q, io.open(QUEUE, "w", encoding="utf-8"), ensure_ascii=False)
    # done rotate(再周回): queue再算出時にdoneをリセットしない(取得済みは素材が既に台帳に在る)
    print(f"queue: {len(q)}slug (頁不明skip {miss})")


def stats():
    q = json.load(io.open(QUEUE, encoding="utf-8")) if os.path.exists(QUEUE) else []
    done = set(json.load(io.open(DONE, encoding="utf-8"))) if os.path.exists(DONE) else set()
    n = sum(1 for _ in io.open(LEDGER, encoding="utf-8")) if os.path.exists(LEDGER) else 0
    print(f"queue {len(q)} / 済 {len(done)} / 残 {len([x for x in q if x['slug'] not in done])} / 台帳 {n}行")


def run(limit):
    q = json.load(io.open(QUEUE, encoding="utf-8"))
    done = set(json.load(io.open(DONE, encoding="utf-8"))) if os.path.exists(DONE) else set()
    todo = [x for x in q if x["slug"] not in done][:limit]
    if not todo:
        print("消化済み(自然停止)")
        return
    os.makedirs(os.path.dirname(DONE), exist_ok=True)
    op = _opener()
    token = _session(op)
    n_req = 0
    n_ok = 0
    for i, item in enumerate(todo, 1):
        if n_req and n_req % 50 == 0:
            op = _opener()
            token = _session(op)
        hits = None
        for attempt, wait in enumerate((0, 5, 20, 60)):
            if wait:
                time.sleep(wait)
            try:
                hits = _search(op, token, item["title"])
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg and "HTTP Error 429" not in msg:
                    pass  # 偽429対策: HTTPError.code以外の"429"は無視して再試行
                if attempt == 3:
                    print(f"  ★連続失敗→中断保存 ({item['slug']}: {msg[:80]})", flush=True)
                    json.dump(sorted(done), io.open(DONE, "w", encoding="utf-8"))
                    return
                op = _opener()
                try:
                    token = _session(op)
                except Exception:
                    pass
        n_req += 1
        with io.open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps({"slug": item["slug"], "query": item["title"],
                                "missing": item.get("missing"), "n_hits": len(hits),
                                "hits": hits, "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
        done.add(item["slug"])
        n_ok += 1
        if i % 10 == 0:
            json.dump(sorted(done), io.open(DONE, "w", encoding="utf-8"))
            print(f"  …{i}/{len(todo)} (hits直近={len(hits)})", flush=True)
        time.sleep(RATE)
    json.dump(sorted(done), io.open(DONE, "w", encoding="utf-8"))
    print(f"バッチ完了: {n_ok}slug取得 (台帳へ追記済)。再起動で続き")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-queue", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    a = ap.parse_args()
    if a.build_queue:
        build_queue()
    elif a.stats:
        stats()
    else:
        run(a.limit)
