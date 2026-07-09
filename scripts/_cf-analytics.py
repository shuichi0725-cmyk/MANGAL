#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cloudflare Workerアクセス解析 (2026-07-10 script化。endpoint/認証/GraphQLの正はここ=再実装禁止)。

使い方:
  python scripts/_cf-analytics.py verify              # トークン生存確認
  python scripts/_cf-analytics.py report [--days 7] [--script mangal-r2]
                                                      # Worker: 日別 requests/errors + 合計/エラー率
  python scripts/_cf-analytics.py web [--days 7]      # ★Web Analytics(RUM): 訪問者/人気ページ/国/流入元

2系統の使い分け:
  report = Workerインフラ視点(クロール込み総リクエスト・エラー率=配信健康)
  web    = 人間の訪問者視点(ビーコン計測=閲覧/訪問/人気ページ/国/referer。2026-07-05設置・自動セットアップ)
★reportのリクエスト数≠訪問者(R2配信は1頁=複数ファイル取得・クロール支配)。訪問者はwebで見る。
キー: .env の CLOUDFLARE_API_TOKEN(Analytics Read・絶対commitしない)。RUM REST(site_info)は403=scope外だが
GraphQL rumデータセットは通る(siteTagは集計から発見済=下の定数)。
"""
import json, os, sys, argparse, datetime, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNT = "774e95ed884a48e76ffb5aa78ae7e037"
DEFAULT_SCRIPT = "mangal-r2"
SITE_TAG = "806671887a234f4882f85ba92058da5f"   # Web Analytics site (mangal-db.com)


def _token():
    k = os.environ.get("CLOUDFLARE_API_TOKEN")
    if k:
        return k.strip()
    envp = os.path.join(ROOT, ".env")
    if os.path.exists(envp):
        for ln in open(envp, encoding="utf-8"):
            if ln.startswith("CLOUDFLARE_API_TOKEN"):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("CLOUDFLARE_API_TOKEN が .env に無い")


def _api(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET",
                                 headers={"Authorization": f"Bearer {_token()}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def verify():
    d = _api("https://api.cloudflare.com/client/v4/user/tokens/verify")
    st = (d.get("result") or {}).get("status")
    print(f"token: {st}" + ("" if st == "active" else f" / {d}"))
    sys.exit(0 if st == "active" else 1)


def report(days, script):
    today = datetime.date.today()
    geq = (today - datetime.timedelta(days=days - 1)).isoformat() + "T00:00:00Z"
    leq = today.isoformat() + "T23:59:59Z"
    q = """query($acct: String!, $geq: Time!, $leq: Time!, $script: String!) {
      viewer { accounts(filter: {accountTag: $acct}) {
        workersInvocationsAdaptive(limit: 400,
          filter: {scriptName: $script, datetime_geq: $geq, datetime_leq: $leq},
          orderBy: [date_ASC]) {
          sum { requests errors subrequests }
          dimensions { date }
        } } } }"""
    d = _api("https://api.cloudflare.com/client/v4/graphql",
             {"query": q, "variables": {"acct": ACCOUNT, "geq": geq, "leq": leq, "script": script}})
    if d.get("errors"):
        raise SystemExit(f"GraphQLエラー: {json.dumps(d['errors'], ensure_ascii=False)[:300]}")
    rows = d["data"]["viewer"]["accounts"][0]["workersInvocationsAdaptive"]
    print(f"Worker {script} / 直近{days}日 (日別)")
    print(f"{'date':<12}{'requests':>10}{'errors':>8}{'subreq':>10}")
    tr = te = ts = 0
    for r in rows:
        s, dt = r["sum"], r["dimensions"]["date"]
        print(f"{dt:<12}{s['requests']:>10,}{s['errors']:>8,}{s['subrequests']:>10,}")
        tr += s["requests"]; te += s["errors"]; ts += s["subrequests"]
    er = (te / tr * 100) if tr else 0.0
    print(f"{'合計':<12}{tr:>10,}{te:>8,}{ts:>10,}   エラー率 {er:.3f}%")
    print("※requests≠訪問者(1頁=複数ファイル・クロール支配)。人気ページ/訪問者はWeb Analytics未設置=取れない。")


def web(days):
    """Web Analytics(RUM=ビーコン計測): 訪問者/人気ページ/国/流入元。"""
    geq = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
    grp = "rumPageloadEventsAdaptiveGroups"
    q = ("query($acct: String!, $geq: Date!, $site: string!) {"
         " viewer { accounts(filter: {accountTag: $acct}) {"
         f" daily: {grp}(limit: 400, filter: {{date_geq: $geq, siteTag: $site}}, orderBy: [date_ASC])"
         " { count sum { visits } dimensions { date } }"
         f" pages: {grp}(limit: 15, filter: {{date_geq: $geq, siteTag: $site}}, orderBy: [count_DESC])"
         " { count sum { visits } dimensions { requestPath } }"
         f" geo: {grp}(limit: 8, filter: {{date_geq: $geq, siteTag: $site}}, orderBy: [count_DESC])"
         " { count dimensions { countryName } }"
         f" ref: {grp}(limit: 8, filter: {{date_geq: $geq, siteTag: $site}}, orderBy: [count_DESC])"
         " { count dimensions { refererHost } }"
         " } } }")
    d = _api("https://api.cloudflare.com/client/v4/graphql",
             {"query": q, "variables": {"acct": ACCOUNT, "geq": geq, "site": SITE_TAG}})
    if d.get("errors"):
        raise SystemExit(f"GraphQLエラー: {json.dumps(d['errors'], ensure_ascii=False)[:300]}")
    a = d["data"]["viewer"]["accounts"][0]
    tv = sum(r["sum"]["visits"] for r in a["daily"])
    tc = sum(r["count"] for r in a["daily"])
    print(f"Web Analytics (mangal-db.com) / 直近{days}日 = 閲覧 {tc:,} / 訪問 {tv:,}")
    print(f"\n{'date':<12}{'閲覧':>7}{'訪問':>7}")
    for r in a["daily"]:
        print(f"{r['dimensions']['date']:<12}{r['count']:>7,}{r['sum']['visits']:>7,}")
    print("\n人気ページ (閲覧数順):")
    for r in a["pages"]:
        print(f"  {r['count']:>5,}  {r['dimensions']['requestPath']}")
    print("\n国: " + " / ".join(f"{r['dimensions']['countryName']} {r['count']:,}" for r in a["geo"]))
    print("流入元: " + " / ".join(f"{r['dimensions']['refererHost'] or '(直接)'} {r['count']:,}" for r in a["ref"]))
    print("※ビーコン計測=JS実行ブラウザのみ(bot/クローラは原則含まれない)。設置=2026-07-05以降のデータ。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["verify", "report", "web"])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--script", default=DEFAULT_SCRIPT)
    a = ap.parse_args()
    if a.cmd == "verify":
        verify()
    elif a.cmd == "web":
        web(a.days)
    else:
        report(a.days, a.script)


if __name__ == "__main__":
    main()
