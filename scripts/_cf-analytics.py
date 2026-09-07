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
キー: .env の CF_ANALYTICS_API_TOKEN(Analytics Read・絶対commitしない。旧名CLOUDFLARE_API_TOKENはwranglerが誤用するため改名)。RUM REST(site_info)は403=scope外だが
GraphQL rumデータセットは通る(siteTagは集計から発見済=下の定数)。
"""
import json, os, sys, argparse, datetime, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNT = "774e95ed884a48e76ffb5aa78ae7e037"
DEFAULT_SCRIPT = "mangal-r2"
SITE_TAG = "806671887a234f4882f85ba92058da5f"   # Web Analytics site (mangal-db.com)
ZONE_TAG = "5db1699deb11a837a0eb66c096e333b6"   # Zone (mangal-db.com)。 #analytics:read 権限あり(2026-09-07確認)

# 名乗りUAから既知クローラを分類(表示名だけ・厳密なbot判定はしない=UA詐称は見抜けない)
# category: crawl=検索/SEOクローラ / ai=AI検索エージェント / social=リンクプレビューbot / scan=攻撃・脆弱性探索
_BOT_SIGNATURES = [
    ("crawl", "Googlebot", "Googlebot"), ("crawl", "bingbot", "Bingbot"), ("crawl", "Applebot", "Applebot"),
    ("crawl", "SemrushBot", "SemrushBot"), ("crawl", "AhrefsBot", "AhrefsBot"), ("crawl", "MJ12bot", "MJ12bot(Majestic)"),
    ("crawl", "Amazonbot", "Amazonbot"), ("crawl", "YisouSpider", "YisouSpider(易搜/中国)"),
    ("crawl", "DotBot", "DotBot(Moz)"), ("crawl", "PetalBot", "PetalBot(Huawei)"), ("crawl", "Bytespider", "Bytespider(TikTok/ByteDance)"),
    ("crawl", "YandexBot", "YandexBot"), ("crawl", "DuckDuckBot", "DuckDuckBot"),
    ("crawl", "CCBot", "CCBot(Common Crawl)"), ("crawl", "SeznamBot", "SeznamBot"),
    ("crawl", "Sogou", "Sogou(捜狗/中国)"), ("crawl", "Baiduspider", "Baiduspider(百度/中国)"),
    ("ai", "GPTBot", "GPTBot(OpenAI/学習用)"), ("ai", "OAI-SearchBot", "OAI-SearchBot(OpenAI検索)"),
    ("ai", "ChatGPT-User", "ChatGPT-User(ユーザ代理取得)"), ("ai", "ClaudeBot", "ClaudeBot(Anthropic/学習用)"),
    ("ai", "Claude-Web", "Claude-Web(Anthropic)"), ("ai", "Claude-User", "Claude-User(ユーザ代理取得)"),
    ("ai", "PerplexityBot", "PerplexityBot(検索)"), ("ai", "Perplexity-User", "Perplexity-User(ユーザ代理取得)"),
    ("ai", "GrokBot", "GrokBot(xAI)"), ("ai", "Amzn-SearchBot", "Amzn-SearchBot(Alexa+/Rufus)"),
    ("social", "facebookexternalhit", "Facebook(共有プレビュー)"), ("social", "meta-externalagent", "Meta(共有プレビュー/学習)"),
    ("social", "Twitterbot", "Twitterbot(X共有プレビュー)"), ("social", "Discordbot", "Discordbot"),
    ("social", "LinkedInBot", "LinkedInBot"), ("social", "Slackbot", "Slackbot"),
    ("social", "TelegramBot", "TelegramBot"), ("social", "WhatsApp", "WhatsApp(共有プレビュー)"),
]


def _classify(ua):
    """→ (category, label)。 category: crawl/ai/social/scan/human_other/None(=通常ブラウザ)"""
    for cat, sig, label in _BOT_SIGNATURES:
        if sig in ua:
            return cat, label
    if ua.startswith("http://") or ua.startswith("https://") or "wp-admin" in ua or "install.php" in ua:
        return "scan", "(URL型UA=脆弱性探索プローブ)"
    if ua.startswith("NetworkingExtension") or ua.startswith("com.apple"):
        return "human_other", "Apple Private Relay/iOSシステム通信"
    if "Mozilla" not in ua or ua.strip() in ("Mozilla/5.0", "Mozilla/5.0 (compatible)"):
        return "human_other", "(UA欠落/簡略=未分類)"
    return None, None  # 通常ブラウザUAとみなす(下でbrowser/device分類)


def _classify_browser(ua):
    if "EdgA/" in ua or "EdgiOS/" in ua or "Edg/" in ua:
        b = "Edge"
    elif "CriOS/" in ua:
        b = "Chrome(iOS)"
    elif "FxiOS/" in ua:
        b = "Firefox(iOS)"
    elif "Firefox/" in ua:
        b = "Firefox"
    elif "Chrome/" in ua:
        b = "Chrome"
    elif "Safari/" in ua and ("Version/" in ua or "iPhone" in ua or "iPad" in ua or "Macintosh" in ua):
        b = "Safari"
    else:
        b = "(その他ブラウザ)"
    if "iPhone" in ua or "iPad" in ua or ("Android" in ua and "Mobile" in ua):
        dev = "モバイル"
    elif "Android" in ua:
        dev = "タブレット/その他Android"
    else:
        dev = "デスクトップ"
    return f"{b}・{dev}"


def _token():
    # 2026-07-29 改名: CLOUDFLARE_API_TOKEN だと wrangler が deploy 認証に誤用する(.env自動読込)
    for name in ("CF_ANALYTICS_API_TOKEN", "CLOUDFLARE_API_TOKEN"):
        k = os.environ.get(name)
        if k:
            return k.strip()
    envp = os.path.join(ROOT, ".env")
    if os.path.exists(envp):
        for ln in open(envp, encoding="utf-8"):
            if ln.startswith(("CF_ANALYTICS_API_TOKEN", "CLOUDFLARE_API_TOKEN")):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("CF_ANALYTICS_API_TOKEN が .env に無い")


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


def bots(date):
    """ゾーンレベル httpRequestsAdaptiveGroups を User-Agent別に集計(★Freeプランは1日幅までしかクエリ不可)。"""
    d0 = date or datetime.date.today().isoformat()
    geq = d0 + "T00:00:00Z"
    leq = d0 + "T23:59:59Z"
    q = """query($zone: string!, $geq: Time!, $leq: Time!) {
      viewer { zones(filter: {zoneTag: $zone}) {
        ua: httpRequestsAdaptiveGroups(limit: 100, filter: {datetime_geq: $geq, datetime_leq: $leq}, orderBy: [count_DESC]) {
          count
          dimensions { userAgent }
        } } } }"""
    d = _api("https://api.cloudflare.com/client/v4/graphql",
             {"query": q, "variables": {"zone": ZONE_TAG, "geq": geq, "leq": leq}})
    if d.get("errors"):
        raise SystemExit(f"GraphQLエラー: {json.dumps(d['errors'], ensure_ascii=False)[:300]}")
    rows = d["data"]["viewer"]["zones"][0]["ua"]
    cat_total = {"crawl": {}, "ai": {}, "social": {}, "scan": {}, "human_other": {}}
    browser_total = {}
    grand = 0
    for r in rows:
        c, ua = r["count"], r["dimensions"]["userAgent"]
        grand += c
        cat, label = _classify(ua)
        if cat:
            cat_total[cat][label] = cat_total[cat].get(label, 0) + c
        else:
            b = _classify_browser(ua)
            browser_total[b] = browser_total.get(b, 0) + c
    cat_names = {"crawl": "検索/SEOクローラ", "ai": "AI検索エージェント", "social": "SNS/共有プレビューbot",
                 "scan": "攻撃・脆弱性探索プローブ", "human_other": "人間だが非標準UA"}
    print(f"UA分類・{d0}のtop{len(rows)}UA={grand:,}件中:")
    for cat in ("crawl", "ai", "social", "scan", "human_other"):
        items = cat_total[cat]
        if not items:
            continue
        print(f"\n■ {cat_names[cat]}")
        for label, c in sorted(items.items(), key=lambda x: -x[1]):
            print(f"  {c:>7,}  {label}")
    print(f"\n■ 人間(通常ブラウザ)= {sum(browser_total.values()):,}")
    for label, c in sorted(browser_total.items(), key=lambda x: -x[1]):
        print(f"  {c:>7,}  {label}")
    print("\n※上位100UAのみ集計(ロングテールは未計上)。UA詐称までは見抜けない=名乗りベース。Freeプランは1日幅までしかクエリ不可。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["verify", "report", "web", "bots"])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--script", default=DEFAULT_SCRIPT)
    ap.add_argument("--date", default=None, help="bots用: YYYY-MM-DD (省略=今日)")
    a = ap.parse_args()
    if a.cmd == "verify":
        verify()
    elif a.cmd == "web":
        web(a.days)
    elif a.cmd == "bots":
        bots(a.date)
    else:
        report(a.days, a.script)


if __name__ == "__main__":
    main()
