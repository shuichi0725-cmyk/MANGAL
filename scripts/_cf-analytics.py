#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cloudflare Workerアクセス解析 (2026-07-10 script化。endpoint/認証/GraphQLの正はここ=再実装禁止)。

使い方:
  python scripts/_cf-analytics.py verify              # トークン生存確認
  python scripts/_cf-analytics.py report [--days 7] [--script mangal-r2]
                                                      # 日別 requests/errors/subrequests + 合計/エラー率

出来ること: Worker(mangal-r2)のリクエスト数/エラー/サブリクエストの日別推移。
出来ないこと(2026-07-09確定): 訪問者数・人気ページ・流入国(Web Analyticsビーコン未設置のため)。
★リクエスト数≠訪問者(R2配信は1頁=複数ファイル取得・クロール支配)。
キー: .env の CLOUDFLARE_API_TOKEN(Analytics Read・絶対commitしない)。
"""
import json, os, sys, argparse, datetime, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNT = "774e95ed884a48e76ffb5aa78ae7e037"
DEFAULT_SCRIPT = "mangal-r2"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["verify", "report"])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--script", default=DEFAULT_SCRIPT)
    a = ap.parse_args()
    if a.cmd == "verify":
        verify()
    else:
        report(a.days, a.script)


if __name__ == "__main__":
    main()
