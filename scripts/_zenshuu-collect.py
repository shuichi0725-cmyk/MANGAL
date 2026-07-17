#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全集 情報収集 (= 2026-07-18 全集コーナー構想の素材集め。★収集のみ・本番/種には一切書かない)

Wikipedia(全巻リスト) + NDL(ISBN/刊行日 ground-truth) から主要全集の書誌を素材庫へ貯める。
まとめ(種4生成・頁結線・コーナー)は別途ユーザGOで。

  python scripts/_zenshuu-collect.py wiki   # ja.wikipedia 記事wikitextを保存+巻行を粗parse
  python scripts/_zenshuu-collect.py ndl    # NDL SRU 作者束縛+ページングで全巻回収(1.3s/req)
  python scripts/_zenshuu-collect.py report # 収集物 vs 本番(ISBN索引)の被覆サマリ

出力: .cache/enrich-material/zenshuu/
"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".cache", "enrich-material", "zenshuu")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib.util
_spec = importlib.util.spec_from_file_location("_lookup", os.path.join(ROOT, "scripts", "_lookup.py"))
_lookup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lookup)

UA = "MANGAL-zenshuu-collect/1.0"

# 対象全集 (= key / wikipedia記事名 / NDL CQL)
TARGETS = [
    ("tezuka",    "手塚治虫漫画全集",        'creator="手塚治虫" AND title="手塚治虫漫画全集"'),
    ("fujiko-f",  "藤子・F・不二雄大全集",   'creator="藤子・F・不二雄" AND title="藤子・F・不二雄大全集"'),
    ("ishinomori","石ノ森萬画大全集",  'creator="石ノ森章太郎" AND title="萬画大全集"'),
]


def cmd_wiki():
    for key, article, _ in TARGETS:
        p = {"action": "parse", "page": article, "prop": "wikitext", "format": "json",
             "formatversion": "2", "redirects": "1"}
        req = urllib.request.Request("https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p),
                                     headers={"User-Agent": UA})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
            wt = (d.get("parse") or {}).get("wikitext") or ""
        except Exception as e:
            print(f"{key}: wiki取得失敗 {str(e)[:80]}")
            continue
        io.open(os.path.join(OUT, f"wiki-{key}.txt"), "w", encoding="utf-8").write(wt)
        # 粗parse: 巻番号らしき行(表の行/リスト行)を数える(raw保存が主・parseは目安)
        rows = re.findall(r"^\|?\s*\d{1,3}\s*(?:\|\||\|)\s*.+$", wt, re.M)
        print(f"{key}: wikitext {len(wt):,}字 保存 / 巻らしき行 {len(rows)}")


def cmd_ndl():
    for key, _, cql in TARGETS:
        out_p = os.path.join(OUT, f"ndl-{key}.jsonl")
        recs_all, start = [], 1
        while True:
            recs = _lookup.ndl_live(cql, maximum=200, start=start)
            recs_all.extend(recs)
            print(f"  {key}: start={start} +{len(recs)}")
            if len(recs) < 200:
                break
            start += 200
        with io.open(out_p, "w", encoding="utf-8") as f:
            for r in recs_all:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        n_isbn = sum(1 for r in recs_all if r.get("isbn"))
        print(f"{key}: NDL {len(recs_all)}レコード(ISBN有 {n_isbn}) → {os.path.basename(out_p)}")


def cmd_rakuten():
    """楽天Books title検索で巻ISBN回収 (= NDLがセット親+内容細目方式でISBNを持たない全集の代替経路。
    石ノ森萬画大全集で実証。ページング・1.2s/req・outOfStockFlag=1)"""
    env = _lookup._env()
    for key, q in (("ishinomori", "石ノ森章太郎萬画大全集"), ("tezuka", "手塚治虫漫画全集"), ("fujiko-f", "藤子・F・不二雄大全集")):
        out_p = os.path.join(OUT, f"rakuten-{key}.jsonl")
        rows, page = [], 1
        while page <= 34:
            p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env.get("RAKUTEN_ACCESS_KEY", ""),
                 "format": "json", "formatVersion": "2", "title": q, "hits": 30, "page": page,
                 "booksGenreId": "001001", "outOfStockFlag": 1}
            url = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p)
            req = urllib.request.Request(url, headers={"Referer": env.get("RAKUTEN_REFERER", ""),
                                                       "Origin": env.get("RAKUTEN_REFERER", "")})
            try:
                d = json.load(urllib.request.urlopen(req, timeout=30))
            except Exception as e:
                print(f"  {key}: p{page} 失敗 {str(e)[:60]} = 中断")
                break
            items = d.get("Items") or []
            for it in items:
                rows.append({"isbn": str(it.get("isbn") or ""), "title": it.get("title"),
                             "salesDate": it.get("salesDate"), "author": it.get("author"),
                             "pub": it.get("publisherName"), "series": it.get("seriesName")})
            total_pages = d.get("pageCount") or 1
            if page >= total_pages:
                break
            page += 1
            time.sleep(1.2)
        with io.open(out_p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{key}: 楽天 {len(rows)}件 → {os.path.basename(out_p)}")
        time.sleep(1.2)


def cmd_report():
    idx_p = os.path.join(ROOT, ".cache", "isbn-page-index.json")
    idx = json.load(io.open(idx_p, encoding="utf-8")) if os.path.exists(idx_p) else {}
    for key, article, _ in TARGETS:
        p = os.path.join(OUT, f"ndl-{key}.jsonl")
        if not os.path.exists(p):
            print(f"{key}: NDL未収集")
            continue
        rows = [json.loads(l) for l in io.open(p, encoding="utf-8")]
        isbns = {r["isbn"] for r in rows if r.get("isbn")}
        have = {i for i in isbns if i in idx}
        print(f"{key}({article}): NDL {len(rows)}行 / ユニークISBN {len(isbns)} / 本番既収 {len(have)} / 未収 {len(isbns - have)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"wiki": cmd_wiki, "ndl": cmd_ndl, "rakuten": cmd_rakuten, "report": cmd_report}[cmd]()
