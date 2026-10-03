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
import json, os, re, sys, argparse, datetime, statistics, urllib.request

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
    # ★2026-10-03 追加: 「(その他ブラウザ)・デスクトップ」として人間側に 2.8万件混ざっていたSEO/AIクローラ
    ("crawl", "SERankingBacklinksBot", "SERankingBacklinksBot(SEO)"), ("crawl", "ShapBot", "ShapBot"),
    ("crawl", "KeenableBot", "KeenableBot(keenable.ai)"),
    ("auto", "HeadlessChrome", "HeadlessChrome(自動化ブラウザ)"),
]
# ★名前を登録していない bot の汎用拾い(2026-10-03): 名乗りに bot/spider/crawler を含むものは人間に数えない。
# 「…bot」で終わるが bot ではない名乗り(スマホのメーカー名 CUBOT 等)
_NOT_BOT = {"cubot"}
_GENERIC_BOT = re.compile(r"(?i)\b([\w.-]*(?:bot|spider|crawler))\b")


def _classify(ua):
    """→ (category, label)。 category: crawl/ai/social/scan/human_other/None(=通常ブラウザ)"""
    for cat, sig, label in _BOT_SIGNATURES:
        if sig in ua:
            return cat, label
    if ua.startswith("http://") or ua.startswith("https://") or "wp-admin" in ua or "install.php" in ua:
        return "scan", "(URL型UA=脆弱性探索プローブ)"
    if ua.startswith("NetworkingExtension") or ua.startswith("com.apple"):
        return "human_other", "Apple Private Relay/iOSシステム通信"
    m = _GENERIC_BOT.search(ua)
    if m and m.group(1).lower() not in _NOT_BOT:
        return "crawl", f"{m.group(1)}(未登録bot)"
    if "Mozilla" not in ua or ua.strip() in ("Mozilla/5.0", "Mozilla/5.0 (compatible)"):
        return "human_other", "(UA欠落/簡略=未分類)"
    return None, None  # 通常ブラウザUAとみなす(下でbrowser/device分類)


# ★古い版に固定した Chrome の大量アクセス = 自動化ブラウザの疑い(2026-10-03 実踏)。
#   10/01 の山(Worker 9.2万req)は「Windows版 Chrome/131.0.0.0」ただ1種類が 36,146件 = 同じ日の本物のEdgeは154。
#   JSを実行するので Web Analytics の「訪問」にも 1,229 と数えられ、人気1位 /browse を作っていた。
#   判定 = その日の最新Chrome系(Chrome/・Edg/)の版より OLD_MAJOR_GAP 以上古い かつ その日の全体の AUTO_SHARE 以上。
#   ★名乗りベース=詐称は見抜けない。 古い版の人間が少数いても割合の床で弾かれない。
OLD_MAJOR_GAP = 12      # Chrome は約4週ごとに版が上がる = 12版 ≒ 1年
AUTO_SHARE = 0.05
_CHROME_MAJOR = re.compile(r"(?:Chrome|Edg)/(\d+)\.")


def _outdated_chrome(rows):
    """[(count, ua)] → {ua: 理由ラベル}。 最新版から OLD_MAJOR_GAP 以上古く、全体の AUTO_SHARE 以上のUA。"""
    majors = [int(m.group(1)) for _c, ua in rows for m in [_CHROME_MAJOR.search(ua)] if m]
    if not majors:
        return {}
    newest = max(majors)
    grand = sum(c for c, _ua in rows) or 1
    out = {}
    for c, ua in rows:
        m = _CHROME_MAJOR.search(ua)
        if m and newest - int(m.group(1)) >= OLD_MAJOR_GAP and c / grand >= AUTO_SHARE:
            out[ua] = f"古い版で固定のChrome(版{m.group(1)}・その日の最新{newest}・全体の{c / grand:.0%})"
    return out


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
    # ★訪問が普段(中央値)の5倍を超えた日に印(2026-10-03: 10/01 の訪問1,229 は古いChrome固定の自動化ブラウザだった。
    #   ビーコン計測もJSを実行する bot は数えてしまう)。 印の日は `bots --date <日>` で名乗りを見る。
    med = statistics.median([r["sum"]["visits"] for r in a["daily"]]) if a["daily"] else 0
    spikes = []
    for r in a["daily"]:
        v = r["sum"]["visits"]
        flag = "  ★山(普段の5倍超)" if med and v > med * 5 and v >= 100 else ""
        if flag:
            spikes.append(r["dimensions"]["date"])
        print(f"{r['dimensions']['date']:<12}{r['count']:>7,}{v:>7,}{flag}")
    if spikes:
        print("  → ★山の日は自動化ブラウザのことが多い。 確認: " + " / ".join(f"bots --date {d}" for d in spikes))
    print("\n人気ページ (閲覧数順):")
    for r in a["pages"]:
        print(f"  {r['count']:>5,}  {r['dimensions']['requestPath']}")
    print("\n国: " + " / ".join(f"{r['dimensions']['countryName']} {r['count']:,}" for r in a["geo"]))
    print("流入元: " + " / ".join(f"{r['dimensions']['refererHost'] or '(直接)'} {r['count']:,}" for r in a["ref"]))
    print("※ビーコン計測=JS実行ブラウザのみ(bot/クローラは原則含まれない)。設置=2026-07-05以降のデータ。")


# ★★ httpRequestsAdaptiveGroups の罠(2026-09-17 実踏・1時間溶かした)★★
#   このデータセットには clientRequestHTTPProtocol == "UNK" のレコードが大量に混ざる
#   (実測 85,166件中 54,408件=64%)。UNK 行は **method / edgeResponseStatus が実在しない値**
#   で埋まっており、「SemrushBot が /browse に PUT して 204」「GET が 504」等の
#   ありえない組み合わせを作る。これを真に受けると「サイトの29.6%が504」という
#   完全な誤診断になる(実際にやった)。
#   ★検算の型: UNK を除くと合計が Worker invocations と一致する
#     (実測 30,758 ≒ 30,254)。UNK 除外後の 504 は **0件**。
#   → 以後この定数で常に除外する。素の件数は約3倍に膨らむので、過去の記録と
#     食い違ったら「UNK込みで数えていないか」をまず疑う。
REAL_ONLY = ', clientRequestHTTPProtocol_neq: "UNK"'


def bots(date):
    """ゾーンレベル httpRequestsAdaptiveGroups を User-Agent別に集計(★Freeプランは1日幅までしかクエリ不可)。"""
    d0 = date or datetime.date.today().isoformat()
    geq = d0 + "T00:00:00Z"
    leq = d0 + "T23:59:59Z"
    q = """query($zone: string!, $geq: Time!, $leq: Time!) {
      viewer { zones(filter: {zoneTag: $zone}) {
        ua: httpRequestsAdaptiveGroups(limit: 100, filter: {datetime_geq: $geq, datetime_leq: $leq""" + REAL_ONLY + """}, orderBy: [count_DESC]) {
          count
          dimensions { userAgent }
        } } } }"""
    d = _api("https://api.cloudflare.com/client/v4/graphql",
             {"query": q, "variables": {"zone": ZONE_TAG, "geq": geq, "leq": leq}})
    if d.get("errors"):
        raise SystemExit(f"GraphQLエラー: {json.dumps(d['errors'], ensure_ascii=False)[:300]}")
    rows = d["data"]["viewer"]["zones"][0]["ua"]
    cat_total = {"crawl": {}, "ai": {}, "social": {}, "scan": {}, "auto": {}, "human_other": {}}
    browser_total = {}
    grand = 0
    stale = _outdated_chrome([(r["count"], r["dimensions"]["userAgent"]) for r in rows])
    for r in rows:
        c, ua = r["count"], r["dimensions"]["userAgent"]
        grand += c
        cat, label = _classify(ua)
        if not cat and ua in stale:
            cat, label = "auto", stale[ua]
        if cat:
            cat_total[cat][label] = cat_total[cat].get(label, 0) + c
        else:
            b = _classify_browser(ua)
            browser_total[b] = browser_total.get(b, 0) + c
    cat_names = {"crawl": "検索/SEOクローラ", "ai": "AI検索エージェント", "social": "SNS/共有プレビューbot",
                 "scan": "攻撃・脆弱性探索プローブ", "auto": "★自動化ブラウザの疑い(人間に数えない)",
                 "human_other": "人間だが非標準UA"}
    print(f"UA分類・{d0}のtop{len(rows)}UA={grand:,}件中:")
    for cat in ("crawl", "ai", "social", "scan", "auto", "human_other"):
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


# ---- paths: 「そのbotが実際にどのURLを取ったか」 -----------------------------
# ★bots が「誰が来たか」、paths が「何を取ったか」。GSC/BWT は後者を答えない
#   (= 検索エンジンが何を知っているかしか言わない) ので、クロール配分の診断はここでしかできない。
_PATH_BUCKETS = [
    ("/_next/", "JS/CSS資産(_next)"),
    ("/manga/", "★作品頁"),
    ("/author/", "著者頁"),
    ("/zenshuu/", "全集コーナー"),
    ("/genre/", "ハブ(ジャンル)"),
    ("/magazine", "ハブ(雑誌)"),
    ("/publisher", "ハブ(出版社)"),
    ("/year", "ハブ(年)"),
    ("/titles", "索引(題名)"),
    ("/authors", "索引(著者)"),
    ("/shinkan", "新刊"),
    ("/art-books/", "画集"),
    ("/tokushu", "特集"),
    ("/column-ai-league/", "AI書評"),
    ("/browse", "一覧(browse)"),
    ("/list", "一覧(list)"),
    ("/sitemap", "クロール制御(sitemap)"),
    ("/robots.txt", "クロール制御(robots)"),
]


def _bucket(path):
    if path == "/" or path == "":
        return "ホーム"
    for pref, label in _PATH_BUCKETS:
        if path.startswith(pref):
            return label
    return "その他"


def _zone_group(geq, leq, dims, ua=None, limit=200):
    """httpRequestsAdaptiveGroups を任意 dimension で集計。ua 指定時はその UA に絞る。
    ★REAL_ONLY で protocol=UNK の偽レコードを必ず除外する(上の罠コメント参照)。"""
    filt = "datetime_geq: $geq, datetime_leq: $leq" + REAL_ONLY
    varsdef = "$zone: string!, $geq: Time!, $leq: Time!"
    variables = {"zone": ZONE_TAG, "geq": geq, "leq": leq}
    if ua is not None:
        filt += ", userAgent: $ua"
        varsdef += ", $ua: string!"
        variables["ua"] = ua
    q = ("query(" + varsdef + ") { viewer { zones(filter: {zoneTag: $zone}) {"
         f" g: httpRequestsAdaptiveGroups(limit: {limit}, filter: {{{filt}}}, orderBy: [count_DESC])"
         " { count dimensions { " + " ".join(dims) + " } }"
         " } } }")
    d = _api("https://api.cloudflare.com/client/v4/graphql", {"query": q, "variables": variables})
    if d.get("errors"):
        raise SystemExit("GraphQLエラー(dims=" + ",".join(dims) + "): "
                         + json.dumps(d["errors"], ensure_ascii=False)[:400])
    return d["data"]["viewer"]["zones"][0]["g"]


def paths(date, targets):
    """指定botが実際に取得したパスを集計。★Freeプランは1日幅・top N のみ=ロングテールは出ない。"""
    d0 = date or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    geq, leq = d0 + "T00:00:00Z", d0 + "T23:59:59Z"
    uas = [r["dimensions"]["userAgent"] for r in _zone_group(geq, leq, ["userAgent"], limit=100)]
    print(f"パス取得の実態・{d0} (ゾーン上位100UAから対象botのUA変種を拾って集計)\n")
    for sig in targets:
        mine = [u for u in uas if sig.lower() in u.lower()]
        if not mine:
            print(f"=== {sig} === 上位100UAに出現せず(この日のリクエストが少ない)\n")
            continue
        buckets, status, raw = {}, {}, {}
        for ua in mine:
            for r in _zone_group(geq, leq, ["clientRequestPath"], ua=ua, limit=200):
                p, c = r["dimensions"]["clientRequestPath"], r["count"]
                buckets[_bucket(p)] = buckets.get(_bucket(p), 0) + c
                raw[p] = raw.get(p, 0) + c
            for r in _zone_group(geq, leq, ["edgeResponseStatus"], ua=ua, limit=20):
                s = r["dimensions"]["edgeResponseStatus"]
                status[s] = status.get(s, 0) + r["count"]
        tot = sum(buckets.values())
        stot = sum(status.values())
        print(f"=== {sig} === UA変種{len(mine)}件 / 集計リクエスト {tot:,}")
        print("  ■ ステータス")
        for s, c in sorted(status.items(), key=lambda x: -x[1]):
            print(f"     {s}  {c:>7,}  ({c / stot * 100:>5.1f}%)")
        print("  ■ パス分類")
        for b, c in sorted(buckets.items(), key=lambda x: -x[1]):
            print(f"     {b:<22}{c:>7,}  ({c / tot * 100:>5.1f}%)")
        print("  ■ 実パス上位15")
        for p, c in sorted(raw.items(), key=lambda x: -x[1])[:15]:
            print(f"     {c:>6,}  {p[:96]}")
        print()
    print("※上位N件のみ=ロングテール未計上。Freeプランは1日幅までしかクエリ不可。UA詐称は見抜けない。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["verify", "report", "web", "bots", "paths"])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--script", default=DEFAULT_SCRIPT)
    ap.add_argument("--date", default=None, help="bots/paths用: YYYY-MM-DD (paths既定=昨日)")
    ap.add_argument("--bot", default="Googlebot,bingbot,OAI-SearchBot",
                    help="paths用: UAに含まれる文字列をカンマ区切り")
    a = ap.parse_args()
    if a.cmd == "verify":
        verify()
    elif a.cmd == "web":
        web(a.days)
    elif a.cmd == "bots":
        bots(a.date)
    elif a.cmd == "paths":
        paths(a.date, [s.strip() for s in a.bot.split(",") if s.strip()])
    else:
        report(a.days, a.script)


if __name__ == "__main__":
    main()
