#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本番疎通確認 (2026-07-10 弱モデル耐性: URL手打ち誤検証=2026-07-04 /data/事故 の根絶)。

  python scripts/_prod-smoke.py             # 全チェック(contact POST含む)
  python scripts/_prod-smoke.py --no-post   # contact送信をskip(デプロイ直後以外の練習/検証用)
  python scripts/_prod-smoke.py --base https://... # ドメイン差し替え

チェック(skill weekly-distill 手順5の機械化。FAILが1つでも exit 1):
  / , /manga/urusei-yatsura , /contact , /about → 200(HTMLは ?v= でedge cacheバイパス)
  作品頁: 題を含む + ¥ 非含有(価格静的表示の禁止)
  ★索引はルート直下 /manga-list-index.json → 200 かつ 5MB超(preview索引66k化事故ガード)
  /data/anniversaries.json → 200
  POST /api/contact {"body":"smoke"} → {"ok":true}
"""
import json, sys, time, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://mangal-db.com"
results = []


def req(path, method="GET", body=None, bypass=False):
    url = BASE + path + (("&" if "?" in path else "?") + f"v={int(time.time())}" if bypass else "")
    r = urllib.request.Request(url, method=method,
                               data=json.dumps(body).encode() if body else None,
                               headers={"Content-Type": "application/json", "User-Agent": "mangal-smoke"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, b"", {}
    except Exception as e:
        return None, str(e).encode(), {}


def check(name, cond, detail=""):
    results.append(cond)
    print(("  PASS " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def main():
    global BASE
    if "--base" in sys.argv:
        BASE = sys.argv[sys.argv.index("--base") + 1].rstrip("/")
    do_post = "--no-post" not in sys.argv
    print(f"本番疎通: {BASE}")

    for path in ("/", "/contact", "/about"):
        st, _, _ = req(path, bypass=True)
        check(f"GET {path} = 200", st == 200, f"got {st}")

    st, body, _ = req("/manga/urusei-yatsura", bypass=True)
    check("GET /manga/urusei-yatsura = 200", st == 200, f"got {st}")
    if st == 200:
        html = body.decode("utf-8", "replace")
        check("作品頁に題(うる星やつら)がある", "うる星やつら" in html)
        check("作品頁に ¥ が無い(価格静的表示禁止)", "¥" not in html,
              f"¥ 出現 {html.count('¥')} 回(動的取得に直すまで公開不可)")

    # ★索引=ルート直下(/data/ ではない)+5MBガード
    st, body, hdr = req("/manga-list-index.json")
    size = int(hdr.get("Content-Length") or len(body))
    check("GET /manga-list-index.json = 200 (★ルート直下)", st == 200, f"got {st}")
    check(f"索引サイズ {size/1e6:.1f}MB > 5MB(preview索引化ガード)", size > 5_000_000)

    st, _, _ = req("/data/anniversaries.json")
    check("GET /data/anniversaries.json = 200", st == 200, f"got {st}")

    if do_post:
        st, body, _ = req("/api/contact", method="POST", body={"body": "smoke"})
        okj = False
        try:
            okj = json.loads(body.decode("utf-8")).get("ok") is True
        except Exception:
            pass
        check('POST /api/contact → {"ok":true}', st == 200 and okj, f"got {st} {body[:80]!r}")
    else:
        print("  SKIP POST /api/contact (--no-post)")

    ng = results.count(False)
    print(f"\n結果: PASS {results.count(True)} / FAIL {ng}")
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
