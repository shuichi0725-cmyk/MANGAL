#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任意サイトを魚(TinyFish)で取りに行く前の共通ゲート (= 2026-10-08 新設。 skill element-harvest)

背景: BookLive 規制事故(2026-08-29)と BOOK☆WALKER の robots 全面拒否(2026-09-04)。
「大手だから平気」は根拠にならない = 取る前に 止め札 → robots.txt → サイト別間隔 を機械で通す。
★運転者(Haiku/Sonnet)に可否を判断させない。 拒否されたURLを別の手段で取りに行かない。

使い方:
    import _site_gate
    v = _site_gate.check(url)     # {"ok": bool, "kind": "ok|deny|robots|robots-unknown", "why": str}
    if v["ok"]:
        _site_gate.pace(url)      # サイト別の最小間隔(プロセス間で有効 = _rate_gate)
        ... 取得 ...

CLI:
    python scripts/_site_gate.py <URL> [<URL>...]   # 可否だけ表示(頁は取得しない)
    python scripts/_site_gate.py --selftest         # robots 解釈の自己検査

robots.txt の扱い(fail-closed):
  200            → 中身を解釈(ClaudeBot と一般クローラ(*) の両方に許されているパスだけ可)
  404/410 ほか4xx → robots なし = 制限なし
  401/403        → 確認できない = 今回は取らない(1日だけ覚える)
  429/5xx/timeout → 確認できない = 今回は取らない(覚えない = 次回また確かめる)
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _rate_gate  # noqa: E402

UA = "MangalBot/1.0 (+https://mangal.shuichi0725.workers.dev)"
RDIR = os.path.join(ROOT, ".cache", "site-gate", "robots")
TTL_OK = 7 * 86400
TTL_UNKNOWN = 86400
MIN_INTERVAL = 5.0   # 同じサイトへは最短5秒に1回
MAX_DELAY = 30.0     # Crawl-delay を尊重する上限(これより長い指定は30秒に丸める)

# ★止め札(ユーザ裁定・事故由来)。 ここに在るサイトは robots を見るまでもなく取らない。 足す/外すはユーザ裁定。
DENY = {
    "booklive.jp": "BookLive は 2026-08-29 に規制事故。 scripts/_booklive.py 経由の専用柱だけが触る",
    "bookwalker.jp": "robots.txt が ClaudeBot を全面 Disallow(2026-09-04 確認)",
    "amazon.co.jp": "Amazon は PA-API 以外で取らない(既裁定)",
    "amazon.com": "Amazon は PA-API 以外で取らない(既裁定)",
}

_delay = {}  # host -> Crawl-delay(check が拾い、pace が使う)


def host_of(url):
    h = urllib.parse.urlsplit(url).netloc.lower()
    h = h.split("@")[-1].split(":")[0]
    return h[4:] if h.startswith("www.") else h


def _q(s):
    """パス/パターンを同じ形に揃える(非ASCIIを%XX化・16進は大文字)。"""
    s = urllib.parse.quote(s, safe="/%?=&*$~:@!'(),;+-._#[]")
    return re.sub(r"%[0-9a-fA-F]{2}", lambda m: m.group(0).upper(), s)


def _parse(body):
    """robots.txt → [(agents[list], rules[(allow, pattern)], crawl_delay)]"""
    groups, agents, rules, delay, last_agent = [], [], [], None, False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            if agents and not last_agent:  # 規則の後に来た User-agent = 新しい組
                groups.append((agents, rules, delay))
                agents, rules, delay = [], [], None
            agents.append(v.lower())
            last_agent = True
        elif k in ("allow", "disallow"):
            last_agent = False
            if agents:
                rules.append((k == "allow", v))
        elif k == "crawl-delay":
            last_agent = False
            try:
                delay = float(v)
            except ValueError:
                pass
    if agents:
        groups.append((agents, rules, delay))
    return groups


def _split(groups):
    """→ (全クローラ(*)向けの規則, Claude/Anthropic 名指しの組ごとの規則[list], Crawl-delay)。
    ★保守側: * と Claude名指しの「両方」に許されたパスだけ可にする(名指しで許して * で拒む型も取らない)。
    名指しは claude* / anthropic* で始まる全トークン(ClaudeBot / Claude-Web / anthropic-ai / Claude-User …)。"""
    star, claude, delays = [], [], []
    for agents, rules, delay in groups:
        hit = False
        if "*" in agents:
            star += rules
            hit = True
        if any(a.startswith(("claude", "anthropic")) for a in agents):
            claude.append(rules)
            hit = True
        if hit and delay:
            delays.append(delay)
    return star, claude, (max(delays) if delays else None)


def _pat_re(p):
    end = p.endswith("$")
    if end:
        p = p[:-1]
    rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in p)
    return re.compile("^" + rx + ("$" if end else ""))


def _allowed(rules, path):
    """最長一致の規則が勝つ。 同じ長さなら Allow。 当たる規則が無ければ可。"""
    best = (-1, True)
    for allow, pat in rules:
        if pat == "":  # 空の Disallow = 制限なし
            continue
        if _pat_re(_q(pat)).match(path):
            n = len(pat)
            if n > best[0] or (n == best[0] and allow):
                best = (n, allow)
    return best[1]


def _robots_via_fish(host, scheme):
    """魚で robots.txt を読む。 → 本文(robots無しは "") / None(確かめられない)。"""
    try:
        import _tinyfish
        _rate_gate.wait("tinyfish", 1.5)
        res = _tinyfish.fetch([f"{scheme}://{host}/robots.txt"])
    except BaseException:  # 魚の枠切れ等(SystemExit)も「確かめられない」に倒す
        return None
    for e in res.get("errors") or []:
        return "" if e.get("status") in (404, 410) else None
    for r in res.get("results") or []:
        t = r.get("text")
        if isinstance(t, str):
            return t if re.search(r"(?im)^\s*user-agent\s*:", t) else ""
    return None


def _robots(host, scheme="https"):
    """→ ("ok", 本文) / ("unknown", 理由)。 本文は .cache に7日。"""
    os.makedirs(RDIR, exist_ok=True)
    cp = os.path.join(RDIR, re.sub(r"[^a-z0-9.-]", "_", host) + ".json")
    try:
        c = json.load(open(cp, encoding="utf-8"))
        age = time.time() - c.get("at", 0)
        if c.get("state") == "ok" and age < TTL_OK:
            return "ok", c.get("body", "")
        if c.get("state") == "unknown" and age < TTL_UNKNOWN:
            return "unknown", c.get("why", "")
    except Exception:
        pass
    _rate_gate.wait("site-robots", 1.0)
    req = urllib.request.Request(f"{scheme}://{host}/robots.txt", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(600_000).decode("utf-8", "replace")
        state, why = "ok", ""
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            state, why, body = "unknown", f"robots.txt が HTTP {e.code}", ""
        elif e.code == 429 or e.code >= 500:
            return "unknown", f"robots.txt が HTTP {e.code}(一時的)"
        else:
            state, why, body = "ok", "", ""  # 404 等 = robots なし
    except Exception as e:  # timeout / DNS / TLS
        # ★このPCのPythonが証明書の鎖を検証できないサイトがある(紀伊國屋で実踏 2026-10-08)。
        #   その時だけ robots.txt を魚経由で読む(robots を読むこと自体は常に許されている)。 それも駄目なら不明=取らない。
        got = _robots_via_fish(host, scheme) if "CERTIFICATE_VERIFY_FAILED" in repr(e) else None
        if got is None:
            return "unknown", f"robots.txt に届かない({type(e).__name__})"
        state, why, body = "ok", "", got
    try:
        json.dump({"at": time.time(), "state": state, "why": why, "body": body},
                  open(cp, "w", encoding="utf-8"), ensure_ascii=False)
    except OSError:
        pass
    return (state, body) if state == "ok" else (state, why)


def check(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        return {"ok": False, "kind": "deny", "why": "http(s) のURLではない"}
    host = host_of(url)
    for d, why in DENY.items():
        if host == d or host.endswith("." + d):
            return {"ok": False, "kind": "deny", "why": f"止め札 {d}: {why}"}
    # ★robots は URL の実ホスト(www. 付きのまま)に取りに行く。 www を外した名前は引けないサイトがある
    state, body = _robots(u.netloc.lower().split("@")[-1], u.scheme)
    if state != "ok":
        return {"ok": False, "kind": "robots-unknown", "why": f"{body} = 可否を確かめられないので今回は取らない"}
    star, claude, dl = _split(_parse(body))
    path = _q((u.path or "/") + (("?" + u.query) if u.query else ""))
    if not _allowed(star, path):
        return {"ok": False, "kind": "robots", "why": f"{host} の robots.txt が全クローラ(*)にこのパスを許していない"}
    if any(not _allowed(r, path) for r in claude):
        return {"ok": False, "kind": "robots", "why": f"{host} の robots.txt が Claude を名指しで拒んでいる"}
    _delay[host] = dl
    return {"ok": True, "kind": "ok", "why": ""}


def pace(url, interval=MIN_INTERVAL):
    host = host_of(url)
    d = min(_delay.get(host) or 0, MAX_DELAY)
    _rate_gate.wait("site-" + re.sub(r"[^a-z0-9.-]", "_", host), max(interval, d))


def _selftest():
    bw = "User-agent: ClaudeBot\nDisallow: /\n\nUser-agent: *\nDisallow: /de*/?sample=*\nAllow: /\n"
    star, claude, _ = _split(_parse(bw))
    assert _allowed(star, "/series/1/") and not _allowed(star, "/deabc/?sample=1")
    assert len(claude) == 1 and not _allowed(claude[0], "/series/1/")
    r, c, d = _split(_parse("User-agent: *\nDisallow: /a/\nAllow: /a/b\nDisallow: /*.pdf$\nCrawl-delay: 10\n"))
    assert d == 10.0 and c == []
    assert not _allowed(r, "/a/x") and _allowed(r, "/a/b/c") and _allowed(r, "/z")
    assert not _allowed(r, "/x/y.pdf") and _allowed(r, "/x/y.pdf?x=1")
    # 複数名の組 / 規則の後の User-agent は新しい組 / 空の Disallow は制限なし
    r, c, _ = _split(_parse("User-agent: GPTBot\nUser-agent: anthropic-ai\nDisallow: /p\n\nUser-agent: *\nDisallow:\n"))
    assert _allowed(r, "/p/1") and len(c) == 1 and not _allowed(c[0], "/p/1") and _allowed(c[0], "/q")
    r, c, _ = _split(_parse("User-agent: Googlebot\nDisallow: /\n"))
    assert r == [] and c == [] and _allowed(r, "/any")
    assert _split(_parse(""))[0] == []
    # ★稼働中の実ルール(自サイトの robots)を評価ケースに入れる = これが落ちたら道具が壊れている
    r, _, _ = _split(_parse("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /browse?\nDisallow: /shinkan/*.json$\n"))
    assert not _allowed(r, "/browse?author=x") and _allowed(r, "/browse") and not _allowed(r, "/api/like")
    assert not _allowed(r, "/shinkan/2026-10.json") and _allowed(r, "/shinkan/2026-10") and _allowed(r, "/manga/x")
    assert _q("/a/やは") == "/a/%E3%82%84%E3%81%AF" and _q("/a/%e3%82%84") == "/a/%E3%82%84"
    assert host_of("https://www.Example.co.jp:443/x") == "example.co.jp"
    assert not check("https://booklive.jp/product/1")["ok"] and not check("https://www.bookwalker.jp/de1/")["ok"]
    print("selftest OK")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    if sys.argv[1] == "--selftest":
        _selftest(); sys.exit(0)
    for url in sys.argv[1:]:
        v = check(url)
        print(("可  " if v["ok"] else "不可 ") + url + ("" if v["ok"] else f"\n     {v['why']}"))
