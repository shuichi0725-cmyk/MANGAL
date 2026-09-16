#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Search Console API (2026-09-15 script化。認証/endpointの正はここ=再実装禁止)。

使い方:
  python scripts/_gsc.py verify                       # 認証確認 + プロパティ一覧
  python scripts/_gsc.py traffic [--days 28]          # 日別 クリック/表示/CTR/平均掲載順位
  python scripts/_gsc.py queries [--days 28] [--top 30]   # クエリ別
  python scripts/_gsc.py pages   [--days 28] [--top 30]   # ページ別
  python scripts/_gsc.py device  [--days 28]          # デバイス別
  python scripts/_gsc.py sitemaps                     # サイトマップの送信状況
  python scripts/_gsc.py inspect --url <URL>          # URL単位のインデックス状況(1日2,000件まで)
  python scripts/_gsc.py summary [--days 28]          # 上を一望(既定)

認証: .env.local の GSC_SA_JSON = サービスアカウントJSONの**パス**(鍵本体はrepo外・git管理外)。
  Search Console 側で そのサービスアカウントのメールを「ユーザーと権限」に追加しておくこと
  (制限付きで十分)。追加が無いと sites が 0件で返る(403ではないので気づきにくい)。

★依存は `rsa` のみ(pip install rsa)。google-auth/google-api-python-client は使わない
  (通信は標準の urllib = 他のMANGALスクリプトと同じ作法)。
★サービスアカウント鍵は PKCS#8(`BEGIN PRIVATE KEY`)で降ってくるが rsa は PKCS#1 しか
  読めないため、_pkcs8_to_pkcs1() で DER の OCTET STRING を剥がしてから渡す。

★このAPIで取れないもの(画面専用。2026-09-15時点):
  ・「インデックス作成」レポートの内訳(登録済み/未登録のページ数と理由別)
    → URL単位の inspect か、画面のCSVエクスポートで代替
  ・リンクレポート(被リンク一覧)
  ・Core Web Vitals(別途 CrUX API)
"""
import argparse
import base64
import datetime
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ★プロパティはURLプレフィックスでなく**ドメインプロパティ**(2026-09-15 verifyで確認)。
#   `https://mangal-db.com/` を渡すと 403 になる。正しい識別子は `sc-domain:` 接頭辞つき。
SITE = "sc-domain:mangal-db.com"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
API = "https://www.googleapis.com/webmasters/v3"
INSPECT_API = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"


def load_env() -> dict:
    env = {}
    p = os.path.join(ROOT, ".env.local")
    if os.path.exists(p):
        for ln in io.open(p, encoding="utf-8"):
            if "=" in ln and not ln.startswith("#"):
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _tlv(b: bytes, i: int):
    """DER の1要素を読む → (tag, value, 次のindex)。"""
    tag = b[i]; i += 1
    n = b[i]; i += 1
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(b[i:i + k], "big"); i += k
    return tag, b[i:i + n], i + n


def _pkcs8_to_pkcs1(pem: str) -> bytes:
    """`-----BEGIN PRIVATE KEY-----`(PKCS#8) から中身のPKCS#1 DERを取り出す。"""
    body = "".join(l for l in pem.splitlines() if "-----" not in l)
    der = base64.b64decode(body)
    _, seq, _ = _tlv(der, 0)
    i = 0
    _, _, i = _tlv(seq, i)            # version
    _, _, i = _tlv(seq, i)            # AlgorithmIdentifier
    tag, val, _ = _tlv(seq, i)        # privateKey OCTET STRING
    if tag != 0x04:
        raise ValueError(f"PKCS#8 の解析に失敗(tag={tag:#x})")
    return val


_TOKEN = {"v": None, "exp": 0}


def token(env: dict) -> str:
    """サービスアカウントJWT → アクセストークン(1時間・プロセス内キャッシュ)。"""
    if _TOKEN["v"] and time.time() < _TOKEN["exp"] - 60:
        return _TOKEN["v"]
    p = env.get("GSC_SA_JSON")
    if not p or not os.path.exists(p):
        print("★abort: .env.local の GSC_SA_JSON が無い/ファイルが見つからない")
        raise SystemExit(2)
    import rsa
    sa = json.load(io.open(p, encoding="utf-8"))
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")  # noqa: E731
    now = int(time.time())
    hdr = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    clm = b64(json.dumps({"iss": sa["client_email"], "scope": SCOPE, "aud": sa["token_uri"],
                          "iat": now, "exp": now + 3600}).encode())
    si = hdr + b"." + clm
    key = rsa.PrivateKey.load_pkcs1(_pkcs8_to_pkcs1(sa["private_key"]), format="DER")
    jwt = si + b"." + b64(rsa.sign(si, key, "SHA-256"))
    data = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": jwt.decode()}).encode()
    r = urllib.request.urlopen(urllib.request.Request(sa["token_uri"], data=data), timeout=40)
    d = json.loads(r.read())
    _TOKEN["v"] = d["access_token"]; _TOKEN["exp"] = now + int(d.get("expires_in", 3600))
    return _TOKEN["v"]


def api(env, path, method="GET", body=None, base=API):
    url = base + path if path.startswith("/") else path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token(env)}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _range(days):
    # GSCのデータは2〜3日遅れる。終端を3日前にして「直近が0」の誤読を避ける。
    end = datetime.date.today() - datetime.timedelta(days=3)
    return (end - datetime.timedelta(days=days - 1)).isoformat(), end.isoformat()


def query(env, site, days, dims, limit=25000):
    lo, hi = _range(days)
    body = {"startDate": lo, "endDate": hi, "dimensions": dims, "rowLimit": limit}
    return api(env, f"/sites/{urllib.parse.quote(site, safe='')}/searchAnalytics/query",
               "POST", body).get("rows", []), lo, hi


def cmd_verify(env, site, days, top):
    d = api(env, "/sites")
    entries = d.get("siteEntry", [])
    print(f"✅ 認証OK / プロパティ {len(entries)}件")
    for s in entries:
        print(f"   {s.get('siteUrl')}  権限={s.get('permissionLevel')}")
    if not entries:
        print("   ★0件 = Search Console の『ユーザーと権限』にサービスアカウントが未追加です")
    return 0


def cmd_traffic(env, site, days, top):
    rows, lo, hi = query(env, site, days, ["date"])
    rows.sort(key=lambda r: r["keys"][0])
    tc = sum(r["clicks"] for r in rows); ti = sum(r["impressions"] for r in rows)
    print(f"=== 検索トラフィック({lo} 〜 {hi}) ===")
    print(f"  合計クリック {tc:,.0f} / 表示 {ti:,.0f} / CTR {tc / ti * 100:.2f}%" if ti else "  データ無し")
    mx = max((r["impressions"] for r in rows), default=1) or 1
    for r in rows:
        bar = "#" * int(r["impressions"] / mx * 34)
        print(f"   {r['keys'][0]}  クリック{r['clicks']:>4.0f}  表示{r['impressions']:>6.0f}"
              f"  順位{r['position']:>5.1f}  {bar}")
    return 0


def _table(rows, label, top, width=60):
    print(f"  {'表示':>7} {'クリック':>7} {'CTR':>7} {'平均順位':>8}  {label}")
    for r in rows[:top]:
        k = r["keys"][0]
        k = k if len(k) <= width else k[:width - 1] + "…"
        print(f"  {r['impressions']:>7,.0f} {r['clicks']:>7,.0f} {r['ctr'] * 100:>6.1f}%"
              f" {r['position']:>8.1f}  {k}")


def cmd_queries(env, site, days, top):
    rows, lo, hi = query(env, site, days, ["query"])
    rows.sort(key=lambda r: -r["impressions"])
    print(f"=== クエリ別({lo} 〜 {hi} / {len(rows):,}語) ===")
    _table(rows, "クエリ", top)
    z = [r for r in rows if r["clicks"] == 0 and r["impressions"] >= 20]
    if z:
        print(f"\n  ★表示20回以上でクリック0 = {len(z)}語(title/descriptionの改善余地)")
        for r in z[:12]:
            print(f"     表示{r['impressions']:>6,.0f}  平均順位{r['position']:>5.1f}  {r['keys'][0]}")
    return 0


def cmd_pages(env, site, days, top):
    rows, lo, hi = query(env, site, days, ["page"])
    rows.sort(key=lambda r: -r["impressions"])
    print(f"=== ページ別({lo} 〜 {hi} / {len(rows):,}頁) ===")
    _table(rows, "URL", top, width=64)
    return 0


def cmd_device(env, site, days, top):
    rows, lo, hi = query(env, site, days, ["device"])
    rows.sort(key=lambda r: -r["impressions"])
    print(f"=== デバイス別({lo} 〜 {hi}) ===")
    _table(rows, "デバイス", 10)
    return 0


def cmd_sitemaps(env, site, days, top):
    d = api(env, f"/sites/{urllib.parse.quote(site, safe='')}/sitemaps")
    sm = d.get("sitemap", [])
    print(f"=== サイトマップ {len(sm)}件 ===")
    for s in sm:
        c = (s.get("contents") or [{}])[0]
        print(f"   {s.get('path')}")
        print(f"     最終送信={str(s.get('lastSubmitted'))[:10]} 最終DL={str(s.get('lastDownloaded'))[:10]}"
              f" 警告={s.get('warnings')} エラー={s.get('errors')} 種別={c.get('type')} 送信URL={c.get('submitted')}")
    if not sm:
        print("   ★0件 = サイトマップ未送信")
    return 0


def cmd_inspect(env, site, url):
    d = api(env, INSPECT_API, "POST", {"inspectionUrl": url, "siteUrl": site}, base="")
    r = (d.get("inspectionResult") or {}).get("indexStatusResult") or {}
    print(f"=== URL検査: {url} ===")
    for k, label in (("verdict", "判定"), ("coverageState", "カバレッジ"), ("robotsTxtState", "robots"),
                     ("indexingState", "インデックス"), ("lastCrawlTime", "最終クロール"),
                     ("googleCanonical", "Google正規URL"), ("userCanonical", "申告正規URL"),
                     ("pageFetchState", "取得")):
        if r.get(k):
            print(f"   {label:12}: {r[k]}")
    return 0


def _sample_urls(n, seed):
    """本番索引から層別サンプリング。層 = 最新刊の新しさ × 巻数 × catch有無 (2x2x2=8層)。
    ★仮説検証用: 「薄い頁ほど登録されない」なら catch無/1巻の層で登録率が有意に低いはず。
    ★2026-09-17 修正: 巻数の列名を volumes_total(存在しない)→ total_volumes に。
      旧コードは常に nv=0 で全件が「_1巻」層に落ち、巻数の効きが測れていなかった。"""
    import random
    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = idx["f"]
    si = f.index("slug")
    ci = json.load(io.open(os.path.join(ROOT, "data", "manga-catch-index.json"), encoding="utf-8"))
    # ★2026-09-17 修正: catch索引は {slug: catch} の素のdict。 {"f","d"} 形式を仮定していたため
    #   has が常に空になり、全件が「catch無」層に落ちて catch の効きが測れていなかった。
    has = set(r[0] for r in ci["d"]) if isinstance(ci, dict) and "d" in ci else (set(ci) if isinstance(ci, dict) else set())
    vi = f.index("total_volumes") if "total_volumes" in f else None
    li = f.index("latest_date") if "latest_date" in f else None
    strata = {}
    for r in idx["d"]:
        slug = r[si]
        nv = (r[vi] if vi is not None else 0) or 0
        lt = str((r[li] if li is not None else "") or "")
        k = ("新刊" if lt >= "2020" else "旧作") \
            + ("_1巻" if nv <= 1 else "_複数巻") \
            + ("_catch有" if slug in has else "_catch無")
        strata.setdefault(k, []).append(slug)
    rnd = random.Random(seed)
    per = max(1, n // max(1, len(strata)))
    out = []
    for k in sorted(strata):
        v = strata[k]
        pick = rnd.sample(v, min(per, len(v)))
        out += [(k, "https://mangal-db.com/manga/" + s) for s in pick]
        print(f"  層 {k:22s} 母数 {len(v):>6,} → 抽出 {len(pick)}")
    return out


def cmd_coverage(env, site, days, top, sample=160, seed=42, extra=()):
    """URL検査APIでインデックス状況を層別に実測。
    ★結果は .cache/gsc-coverage.jsonl に逐次保存(冪等再開=1日2,000件の枠を無駄撃ちしない)。"""
    import collections
    cache_p = os.path.join(ROOT, ".cache", "gsc-coverage.jsonl")
    os.makedirs(os.path.dirname(cache_p), exist_ok=True)
    done = {}
    if os.path.exists(cache_p):
        for ln in io.open(cache_p, encoding="utf-8"):
            try:
                d = json.loads(ln)
                done[d["url"]] = d
            except Exception:
                pass
    targets = list(extra) + _sample_urls(sample, seed)
    todo = [(k, u) for k, u in targets if u not in done]
    print("")
    print(f"  検査対象 {len(targets)}件 / 済み {len(targets) - len(todo)}件 → 今回 {len(todo)}件")
    fo = io.open(cache_p, "a", encoding="utf-8", newline="\n")
    for i, (k, u) in enumerate(todo, 1):
        try:
            d = api(env, INSPECT_API, "POST", {"inspectionUrl": u, "siteUrl": site}, base="")
            r = (d.get("inspectionResult") or {}).get("indexStatusResult") or {}
            row = {"url": u, "stratum": k, "verdict": r.get("verdict"),
                   "coverage": r.get("coverageState"), "robots": r.get("robotsTxtState"),
                   "lastCrawl": r.get("lastCrawlTime"), "fetch": r.get("pageFetchState"),
                   "googleCanonical": r.get("googleCanonical")}
        except urllib.error.HTTPError as e:
            row = {"url": u, "stratum": k, "verdict": "HTTP" + str(e.code),
                   "coverage": e.read().decode("utf-8", "replace")[:120]}
            if e.code == 429:
                print("  ★1日の枠(2,000)を使い切った → 明日再開(結果は保存済み)")
                break
        fo.write(json.dumps(row, ensure_ascii=False) + "\n")
        fo.flush()
        done[u] = row
        if i % 20 == 0:
            print(f"   …{i}/{len(todo)}", flush=True)
        time.sleep(0.3)
    fo.close()

    rows = [done[u] for k, u in targets if u in done]
    print("")
    print(f"=== インデックス状況(実測 {len(rows)}件) ===")
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r["stratum"]][r.get("coverage") or "(不明)"] += 1
    INDEXED = ("Submitted and indexed", "Indexed, not submitted in sitemap")
    for st in sorted(by):
        tot = sum(by[st].values())
        ok = sum(by[st][s] for s in INDEXED)
        print("")
        print(f"  【{st}】 {tot}件 / インデックス済 {ok} ({ok / tot * 100:.0f}%)")
        for s, c in by[st].most_common():
            print(f"     {c:>4}  {s}")
    return 0


def cmd_summary(env, site, days, top):
    cmd_verify(env, site, days, top); print()
    cmd_traffic(env, site, days, top); print()
    cmd_queries(env, site, days, 15); print()
    cmd_pages(env, site, days, 12); print()
    cmd_device(env, site, days, top); print()
    cmd_sitemaps(env, site, days, top)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="summary",
                    choices=["verify", "traffic", "queries", "pages", "device", "sitemaps",
                             "inspect", "coverage", "summary"])
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--url", default=None, help="inspect用の検査URL")
    ap.add_argument("--sample", type=int, default=160, help="coverage用: 検査件数")
    ap.add_argument("--seed", type=int, default=42, help="coverage用: 抽出の再現性")
    a = ap.parse_args()
    env = load_env()
    try:
        if a.cmd == "inspect":
            if not a.url:
                print("★--url が必要"); return 2
            return cmd_inspect(env, a.site, a.url)
        if a.cmd == "coverage":
            hubs = [("ハブ頁", u) for u in (
                "https://mangal-db.com/", "https://mangal-db.com/shinkan",
                "https://mangal-db.com/list", "https://mangal-db.com/browse",
                "https://mangal-db.com/genre/action")]
            return cmd_coverage(env, a.site, a.days, a.top, a.sample, a.seed, hubs)
        fn = {"verify": cmd_verify, "traffic": cmd_traffic, "queries": cmd_queries,
              "pages": cmd_pages, "device": cmd_device, "sitemaps": cmd_sitemaps,
              "summary": cmd_summary}[a.cmd]
        return fn(env, a.site, a.days, a.top)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        print(f"★HTTP {e.code}: {body}")
        if e.code == 403:
            print("  → Search Console の『ユーザーと権限』にサービスアカウントが追加されているか確認")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
