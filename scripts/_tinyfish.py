#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TinyFish Web Fetch/Search ヘルパ (= APIの無い/WebFetchが弾かれるサイト用。2026-07-08)。

用途: usio.co.jp(潮出版社公式)等、NDL/楽天APIに無く標準WebFetchも返らないサイトの取得。
キー: .env の TINYFISH_API_KEY(git追跡外)。Fetch/Searchは無料枠(150URL/分)。

使い方:
  python scripts/_tinyfish.py fetch <URL> [<URL>...]   # ページ→Markdown(最大10URL)
  python scripts/_tinyfish.py search "<クエリ>"          # Web検索(構造化)
コード内: from _tinyfish import fetch, search
"""
import os, sys, json

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _key():
    # .env から TINYFISH_API_KEY を読む(git追跡外)。env varも許容。
    k = os.environ.get("TINYFISH_API_KEY")
    if k:
        return k.strip()
    envp = os.path.join(ROOT, ".env")
    if os.path.exists(envp):
        for ln in open(envp, encoding="utf-8"):
            if ln.startswith("TINYFISH_API_KEY"):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("TINYFISH_API_KEY が .env に無い")

def _post(url, body):
    import urllib.request
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
        headers={"X-API-Key": _key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"TinyFish HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")

def _get(url, params):
    import urllib.request, urllib.parse
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, method="GET", headers={"X-API-Key": _key()})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"TinyFish HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")

def fetch(urls, fmt="markdown", live=False):
    """URL(str or list)→ [{url,title,text,...}]。live=Trueでキャッシュ無視。"""
    if isinstance(urls, str):
        urls = [urls]
    body = {"urls": urls[:10], "format": fmt}
    if live:
        body["ttl"] = 0
    return _post("https://api.fetch.tinyfish.ai", body)

def search(query, purpose=None, location="US"):
    """Web検索(GET) → {query, results:[{title,url,snippet,...}], total_results}。"""
    p = {"query": query, "location": location}
    if purpose:
        p["purpose"] = purpose[:2000]
    return _get("https://api.search.tinyfish.ai", p)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "fetch":
        res = fetch(sys.argv[2:])
        for r in res.get("results", []):
            print(f"=== {r.get('title') or '(no title)'} | {r.get('final_url') or r.get('url')} ===")
            txt = r.get("text")
            print(txt if isinstance(txt, str) else json.dumps(txt, ensure_ascii=False, indent=1))
        for e in res.get("errors", []):
            print(f"[error] {e.get('url')}: {e.get('error')} (status={e.get('status')})", file=sys.stderr)
    elif cmd == "search":
        print(json.dumps(search(sys.argv[2]), ensure_ascii=False, indent=1))
    else:
        print(f"unknown cmd: {cmd}", file=sys.stderr); sys.exit(1)
