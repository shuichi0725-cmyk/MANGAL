#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bing Webmaster Tools API (2026-09-14 script化。endpoint/認証の正はここ=再実装禁止)。

使い方:
  python scripts/_bwt.py verify                      # キー生存確認 + 登録サイト
  python scripts/_bwt.py traffic [--days 30]         # 日別 クリック/表示回数
  python scripts/_bwt.py queries [--top 30]          # クエリ別 クリック/表示/平均掲載位置
  python scripts/_bwt.py pages   [--top 30]          # ページ別 クリック/表示/平均掲載位置
  python scripts/_bwt.py crawl   [--days 14]         # クロール統計 + クロール問題
  python scripts/_bwt.py quota                       # URL送信クォータ(日/月)
  python scripts/_bwt.py links                       # 被リンク数(LinkCounts)
  python scripts/_bwt.py summary [--days 30]         # 上を一望(既定)

キー: .env.local の BING_WEBMASTER_API_KEY (絶対commitしない。.gitignore の .env*.local で除外済)。
  発行元 = Bing Webmaster Tools → 設定 → API アクセス → APIキー。

★Google Search Console と違い、Bing は**APIキー1本**で読める(OAuth不要)。
★この API で取れないもの: 「Top Recommendations」カードそのもの(画面専用)。
  ただしカードの中身(メタdesc・被リンク・IndexNow)は下記の生データで裏が取れる。

注意:
  ・日付は `/Date(エポックミリ秒)/` 形式で返る → _d() で YYYY-MM-DD に直す。
  ・AvgClickPosition == -1 は「クリックが無いので平均クリック位置が算出できない」の意味(順位ではない)。
  ・GetActiveSitemaps は 404(このテナントでは未提供)。サイトマップ状況は画面側で見る。
  ・GetQueryStats/GetPageStats は siteUrl 単位で直近分をまとめて返す(期間指定パラメータ無し)。
"""
import argparse
import collections
import datetime
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://ssl.bing.com/webmaster/api.svc/json/"
DEFAULT_SITE = "https://mangal-db.com/"
_RE_DATE = re.compile(r"/Date\((-?\d+)\)/")


def load_key() -> str:
    p = os.path.join(ROOT, ".env.local")
    if os.path.exists(p):
        for ln in io.open(p, encoding="utf-8"):
            if ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            if k.strip() == "BING_WEBMASTER_API_KEY":
                return v.strip()
    print("★abort: .env.local に BING_WEBMASTER_API_KEY が無い")
    raise SystemExit(2)


def call(method: str, key: str, **params):
    q = dict(params)
    q["apikey"] = key
    url = BASE + method + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("d")


def _d(v) -> str:
    """`/Date(1787270400000)/` → `YYYY-MM-DD`(UTC)。"""
    m = _RE_DATE.search(str(v or ""))
    if not m:
        return str(v or "")
    return datetime.datetime.fromtimestamp(int(m.group(1)) / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")


def _pos(v):
    """平均掲載位置。-1 は算出不能(クリック0)なので '-' で出す。"""
    return "-" if v in (None, -1) else f"{v:.1f}" if isinstance(v, float) else str(v)


def cmd_verify(key, site):
    sites = call("GetUserSites", key) or []
    print(f"✅ キー生存OK / 登録サイト {len(sites)}件")
    for s in sites:
        print(f"   {s.get('Url')}  認証済み={s.get('IsVerified')}")
    return 0


def cmd_traffic(key, site, days):
    rows = call("GetRankAndTrafficStats", key, siteUrl=site) or []
    rows = sorted(({"date": _d(r.get("Date")), "c": r.get("Clicks") or 0, "i": r.get("Impressions") or 0}
                   for r in rows), key=lambda x: x["date"])[-days:]
    tc = sum(r["c"] for r in rows)
    ti = sum(r["i"] for r in rows)
    print(f"=== 検索トラフィック(直近{len(rows)}日) ===")
    print(f"  合計クリック {tc:,} / 表示回数 {ti:,} / CTR {tc / ti * 100:.2f}%" if ti else "  データ無し")
    for r in rows:
        bar = "#" * min(40, r["i"] // max(1, ti // (len(rows) * 20) or 1))
        print(f"   {r['date']}  クリック{r['c']:>4}  表示{r['i']:>6}  {bar}")
    return 0


def _agg(rows, label_key):
    """日別に分かれた行を label 単位で畳む(表示回数の加重で平均位置を出す)。"""
    g = collections.defaultdict(lambda: {"c": 0, "i": 0, "ps": 0.0})
    for r in rows:
        k = r.get(label_key)
        if not k:
            continue
        i = r.get("Impressions") or 0
        g[k]["c"] += r.get("Clicks") or 0
        g[k]["i"] += i
        p = r.get("AvgImpressionPosition")
        if p not in (None, -1):
            g[k]["ps"] += p * i
    out = []
    for k, v in g.items():
        out.append({"k": k, "c": v["c"], "i": v["i"], "p": (v["ps"] / v["i"]) if v["i"] and v["ps"] else None})
    return sorted(out, key=lambda x: (-x["i"], -x["c"]))


def cmd_queries(key, site, top):
    rows = _agg(call("GetQueryStats", key, siteUrl=site) or [], "Query")
    tc, ti = sum(r["c"] for r in rows), sum(r["i"] for r in rows)
    print(f"=== クエリ別(集計 {len(rows)}語 / クリック {tc:,} / 表示 {ti:,}) ===")
    print(f"  {'表示':>7} {'クリック':>7} {'CTR':>7} {'平均位置':>7}  クエリ")
    for r in rows[:top]:
        ctr = f"{r['c'] / r['i'] * 100:.1f}%" if r["i"] else "-"
        print(f"  {r['i']:>7,} {r['c']:>7,} {ctr:>7} {_pos(r['p']):>7}  {r['k']}")
    zero = [r for r in rows if r["c"] == 0 and r["i"] >= 10]
    if zero:
        print(f"\n  ★表示10回以上あるのにクリック0 = {len(zero)}語(title/descriptionの改善余地)")
        for r in zero[:10]:
            print(f"     表示{r['i']:>5}  平均位置{_pos(r['p']):>5}  {r['k']}")
    return 0


def cmd_pages(key, site, top):
    rows = _agg(call("GetPageStats", key, siteUrl=site) or [], "Query")  # Pageも Query フィールドで返る
    print(f"=== ページ別(集計 {len(rows)}頁) ===")
    print(f"  {'表示':>7} {'クリック':>7} {'CTR':>7} {'平均位置':>7}  URL")
    for r in rows[:top]:
        ctr = f"{r['c'] / r['i'] * 100:.1f}%" if r["i"] else "-"
        print(f"  {r['i']:>7,} {r['c']:>7,} {ctr:>7} {_pos(r['p']):>7}  {r['k']}")
    return 0


def cmd_crawl(key, site, days):
    rows = call("GetCrawlStats", key, siteUrl=site) or []
    rows = sorted(rows, key=lambda r: _d(r.get("Date")))[-days:]
    print(f"=== クロール統計(直近{len(rows)}日) ===")
    tot = collections.Counter()
    print(f"  {'日付':10} {'クロール':>8} {'2xx':>7} {'301':>5} {'4xx':>5} {'5xx':>5} {'robots':>7} {'timeout':>8}")
    for r in rows:
        tot["crawled"] += r.get("CrawledPages") or 0
        for k in ("Code2xx", "Code301", "Code4xx", "Code5xx", "BlockedByRobotsTxt", "ConnectionTimeout"):
            tot[k] += r.get(k) or 0
        print(f"  {_d(r.get('Date')):10} {(r.get('CrawledPages') or 0):>8,} {(r.get('Code2xx') or 0):>7,}"
              f" {(r.get('Code301') or 0):>5} {(r.get('Code4xx') or 0):>5} {(r.get('Code5xx') or 0):>5}"
              f" {(r.get('BlockedByRobotsTxt') or 0):>7} {(r.get('ConnectionTimeout') or 0):>8}")
    print(f"  合計: クロール{tot['crawled']:,} / 2xx {tot['Code2xx']:,} / 301 {tot['Code301']:,}"
          f" / 4xx {tot['Code4xx']:,} / 5xx {tot['Code5xx']:,}"
          f" / robots遮断 {tot['BlockedByRobotsTxt']:,} / timeout {tot['ConnectionTimeout']:,}")
    issues = call("GetCrawlIssues", key, siteUrl=site) or []
    print(f"\n=== クロール問題: {len(issues)}件 ===")
    for x in issues[:20]:
        print(f"   {x.get('Url')}  {x.get('Issues')} http={x.get('HttpCode')}")
    return 0


def cmd_quota(key, site, _=None):
    q = call("GetUrlSubmissionQuota", key, siteUrl=site) or {}
    print(f"=== URL送信クォータ ===\n  1日 {q.get('DailyQuota')} / 月 {q.get('MonthlyQuota')}")
    print("  ※IndexNow(_indexnow.py)はこのクォータとは別枠")
    return 0


def cmd_links(key, site, _=None):
    d = call("GetLinkCounts", key, siteUrl=site, page=0) or {}
    links = d.get("Links") or []
    print(f"=== 被リンク(LinkCounts) ===\n  対象ページ数 {d.get('TotalPages', 0):,} / 明細 {len(links)}件")
    for x in links[:20]:
        print(f"   {x.get('Url')}  被リンク {x.get('Count')}")
    if not links:
        print("  ★明細ゼロ = Bingが認識している被リンクが無い(『高品質ドメインからのインバウンドリンク不足』の実体)")
    return 0


def cmd_summary(key, site, days):
    cmd_traffic(key, site, days); print()
    cmd_queries(key, site, 15); print()
    cmd_pages(key, site, 10); print()
    cmd_crawl(key, site, 7); print()
    cmd_links(key, site); print()
    cmd_quota(key, site)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="summary",
                    choices=["verify", "traffic", "queries", "pages", "crawl", "quota", "links", "summary"])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--site", default=DEFAULT_SITE)
    a = ap.parse_args()
    key = load_key()
    fn = {"verify": cmd_verify, "traffic": cmd_traffic, "queries": cmd_queries, "pages": cmd_pages,
          "crawl": cmd_crawl, "quota": cmd_quota, "links": cmd_links, "summary": cmd_summary}[a.cmd]
    arg = a.top if a.cmd in ("queries", "pages") else a.days
    try:
        return fn(key, a.site, arg) if a.cmd != "verify" else fn(key, a.site)
    except urllib.error.HTTPError as e:
        print(f"★HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
