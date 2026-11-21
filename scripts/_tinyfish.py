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

def fish_fetch(urls, fmt="markdown", live=False):
    """魚(TinyFish)だけで取る(旧 fetch の中身)。★Fetch は無料 1,000URL/日(2026-11-21実測)。"""
    if isinstance(urls, str):
        urls = [urls]
    body = {"urls": urls[:10], "format": fmt}
    if live:
        body["ttl"] = 0
    return _post("https://api.fetch.tinyfish.ai", body)


# ---------------------------------------------------------------------------
# ★2026-11-21: 魚の Fetch に 1日1,000URL の無料上限が入った → 「直接 → Jina → 魚」の順で取る。
#   返り値の形は魚と同じ {results:[{url,final_url,title,text,via}], errors:[{url,error,status}]}。
#   魚まで落ちて魚が失敗(枠切れ等)した時は従来どおり SystemExit を投げる(呼び出し側の中断契約を守る)。
#   404/410 は直接取得の時点で確定扱い(魚の枠を使わない)。
# ---------------------------------------------------------------------------
MIN_TEXT = 200          # これ未満の本文 = JS組み立て頁/壁の疑い → 次の手段へ
UA = "Mozilla/5.0 (compatible; MANGAL-fetch/1.0)"
_SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "head", "nav", "footer", "form", "button", "select"}
_BLOCK = {"p", "div", "section", "article", "main", "aside", "ul", "ol", "dl", "dt", "dd", "table", "tbody", "thead",
          "blockquote", "pre", "figure", "figcaption", "header", "hr", "address"}


def _html_to_text(html):
    """依存なしの HTML→Markdown風テキスト(見出し=#・li=- ・表=| 区切り・段落=空行)。"""
    from html.parser import HTMLParser
    import re as _re

    class P(HTMLParser):
        def __init__(s):
            super().__init__(convert_charrefs=True)
            s.out, s.skip, s.title, s.in_title = [], 0, "", False

        def handle_starttag(s, tag, attrs):
            if tag == "title":
                s.in_title = True
            if tag in _SKIP:
                s.skip += 1
                return
            if s.skip:
                return
            if tag in _BLOCK:
                s.out.append("\n\n")
            elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                s.out.append("\n\n" + "#" * int(tag[1]) + " ")
            elif tag == "li":
                s.out.append("\n- ")
            elif tag == "br":
                s.out.append("\n")
            elif tag == "tr":
                s.out.append("\n")
            elif tag in ("td", "th"):
                s.out.append(" | ")

        def handle_endtag(s, tag):
            if tag == "title":
                s.in_title = False
            if tag in _SKIP:
                s.skip = max(0, s.skip - 1)
                return
            if not s.skip and (tag in _BLOCK or tag in ("h1", "h2", "h3", "h4", "h5", "h6")):
                s.out.append("\n\n")

        def handle_data(s, d):
            if s.in_title:
                s.title += d
            if not s.skip:
                s.out.append(d)

    p = P()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    t = "".join(p.out)
    t = _re.sub(r"[ \t　]+", " ", t)
    t = _re.sub(r" *\n *", "\n", t)
    t = _re.sub(r"\n{3,}", "\n\n", t).strip()
    return p.title.strip(), t


def _decode(raw, ctype):
    import re as _re
    cands = []
    m = _re.search(r"charset=([\w\-]+)", ctype or "", _re.I)
    if m:
        cands.append(m.group(1))
    m = _re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", raw[:4096], _re.I)
    if m:
        cands.append(m.group(1).decode("ascii", "ignore"))
    cands += ["utf-8", "cp932", "euc-jp"]
    for c in cands:
        c = {"shift_jis": "cp932", "sjis": "cp932", "x-sjis": "cp932", "windows-31j": "cp932"}.get(c.lower(), c)
        try:
            return raw.decode(c)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def _direct(url):
    """→ ("ok", rec) / ("gone", status) / ("next", 理由)。"""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.5",
                                               "Accept-Language": "ja,en;q=0.7"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            ctype = r.headers.get("Content-Type", "")
            raw = r.read(5_000_000)
            final = r.geturl()
    except urllib.error.HTTPError as e:
        return ("gone", e.code) if e.code in (404, 410) else ("next", f"HTTP {e.code}")
    except Exception as e:
        return "next", type(e).__name__
    body = _decode(raw, ctype)
    if "text/plain" in ctype or url.rstrip("/").endswith("robots.txt"):
        return "ok", {"url": url, "final_url": final, "title": "", "text": body, "via": "direct"}
    if "html" not in ctype and "xml" not in ctype:
        return "next", f"type {ctype[:40]}"
    title, text = _html_to_text(body)
    if len(text) < MIN_TEXT:
        return "next", f"本文{len(text)}字(JS頁の疑い)"
    return "ok", {"url": url, "final_url": final, "title": title, "text": text, "via": "direct"}


def _jina_key():
    k = os.environ.get("JINA_API_KEY")
    if k:
        return k.strip()
    envp = os.path.join(ROOT, ".env")
    if os.path.exists(envp):
        for ln in open(envp, encoding="utf-8"):
            if ln.startswith("JINA_API_KEY"):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _jina(url, live=False):
    """Jina Reader(r.jina.ai)。キー無し=約20req/分 → 3.2秒間隔。→ ("ok", rec) / ("next", 理由)。"""
    import urllib.request
    try:
        import _rate_gate
        k = _jina_key()
        _rate_gate.wait("jina", 0.6 if k else 3.2)
    except ImportError:
        k = _jina_key()
    h = {"Accept": "application/json", "User-Agent": UA}
    if k:
        h["Authorization"] = f"Bearer {k}"
    if live:
        h["X-No-Cache"] = "true"
    req = urllib.request.Request("https://r.jina.ai/" + url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return "next", f"jina HTTP {e.code}"
    except Exception as e:
        return "next", f"jina {type(e).__name__}"
    data = d.get("data") or {}
    text = (data.get("content") or "").strip()
    if len(text) < MIN_TEXT and not url.rstrip("/").endswith("robots.txt"):
        return "next", f"jina 本文{len(text)}字"
    return "ok", {"url": url, "final_url": data.get("url") or url, "title": data.get("title") or "", "text": text, "via": "jina"}


def _stat(via, n=1):
    """日別の経路別件数 = .cache/fetch-route-stats.json(魚の枠をどれだけ節約できたかを見る)。"""
    import time
    p = os.path.join(ROOT, ".cache", "fetch-route-stats.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        d = {}
    day = time.strftime("%Y-%m-%d", time.gmtime())  # 魚の枠は 00:00 UTC で切り替わる
    d.setdefault(day, {})
    d[day][via] = d[day].get(via, 0) + n
    try:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def fetch(urls, fmt="markdown", live=False, route="auto"):
    """URL(str or list)→ {results, errors}。route="auto"=直接→Jina→魚 / "fish"=魚だけ(旧挙動)。"""
    if isinstance(urls, str):
        urls = [urls]
    urls = urls[:10]
    if route == "fish":
        return fish_fetch(urls, fmt, live)
    results, errors, rest = [], [], []
    for u in urls:
        st, v = _direct(u)
        if st == "ok":
            results.append(v); _stat("direct"); continue
        if st == "gone":
            errors.append({"url": u, "error": "not_found", "status": v, "via": "direct"}); _stat("gone"); continue
        st2, v2 = _jina(u, live)
        if st2 == "ok":
            results.append(v2); _stat("jina"); continue
        rest.append(u)
    if rest:
        res = fish_fetch(rest, fmt, live)  # 失敗(枠切れ等)は SystemExit = 従来どおり呼び出し側で中断
        _stat("fish", len(rest))
        for r in res.get("results") or []:
            r.setdefault("via", "fish")
            results.append(r)
        errors += res.get("errors") or []
    return {"results": results, "errors": errors}

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
