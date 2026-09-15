#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配信HTMLの中身ゲート。★週次preflight / 機能蒸留の前検査で回す。

なぜ要るか (= 2026-09-15 実害):
  `/column-ai-league` の静的HTMLが **h1も h2も本文もゼロ** だった。原因は
  AiLeagueClient が公開節数を **クライアントの現在時刻** から計算しており
  (`useState<number|null>(null)` → `if (now===null) return null`)、
  サーバー描画では必ず null を返していたこと。ブラウザでは正常に見えるので
  目視では絶対に気づけない。同じ型は `/browse` でも起きている
  ([[browse_ssr_shell_and_seo]])。
  ★typecheck も vitest も「描画結果が空」は見ない = 全緑のまま本番へ出る。
  ★同じビルドで、`/column-ai-league/[setsu]` は title が既定値のままだった
  (generateMetadata が canonical しか返していなかった) = Bing Webmaster の
  「同一のメタディスクリプションが多すぎる」の実体の一部。

この番人が見るもの (= 前回ビルドの out/ を読むだけ。ビルドはしない):
  検査1 = 本文の実在   : <body> のテキスト量が床を超えるか(クライアント専用描画の検出)
  検査2 = 見出し       : h1 がちょうど1個(0=空/構造欠け、2以上=重複)
  検査3 = title        : 既定値 "MANGAL — 日本の漫画データベース" のままでないか
  検査4 = description  : 存在し、layout の既定文のままでないか

  ハブ/コーナー頁(manga・author 以外 = 約1,700)は **全数**。
  大量層(manga 69,240 / author 20,203)は **サンプリング**(既定 各400・--full で全数)。

使い方:
  python scripts/_check-ssr-content.py             # FAIL があれば exit 1
  python scripts/_check-ssr-content.py --sample 800
  python scripts/_check-ssr-content.py --full      # manga/author も全数(数分)
  python scripts/_check-ssr-content.py --list      # FAIL明細を全部出す(既定は先頭20件)
"""
from __future__ import annotations

import argparse
import html as _html
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

# layout.tsx の既定値(ここが出ていたら頁側の metadata 未設定)。変えたらここも直す。
DEFAULT_TITLE = "MANGAL — 日本の漫画データベース"
DEFAULT_DESC_HEAD = "出版年・著者・出版社・分野・ジャンルから日本の漫画を絞り込めるデータベース"

# 本文テキストの床。RSCのJSONペイロードを除いた「人が読める文字数」。
# 実測: 最小級の /contact でも 200字を超える。空描画は 0〜数十字になる。
BODY_FLOOR = 150

# 検査から外す頁(実験/内部用。公開SEO対象でない)。
SKIP_PREFIX = ("404", "home-design-", "nav-lab", "nav-pack", "obi-design", "tab-design",
               "search-proto", "adult-triage", "audit-date-order", "column-sample")

RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
RE_DESC = re.compile(r'<meta name="description" content="(.*?)"', re.S)
RE_BODY = re.compile(r"<body[^>]*>(.*?)</body>", re.S)
RE_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.S)
RE_STYLE = re.compile(r"<style[^>]*>.*?</style>", re.S)
RE_TAG = re.compile(r"<[^>]+>")


def rel(p: str) -> str:
    return os.path.relpath(p, OUT).replace(os.sep, "/")


def body_text(h: str) -> str:
    m = RE_BODY.search(h)
    b = m.group(1) if m else h
    b = RE_SCRIPT.sub(" ", b)          # ★RSCペイロードを本文と数えない(ここが肝)
    b = RE_STYLE.sub(" ", b)
    return re.sub(r"\s+", " ", _html.unescape(RE_TAG.sub(" ", b))).strip()


def h1_texts(h: str) -> list[str]:
    return [re.sub(r"\s+", " ", _html.unescape(RE_TAG.sub("", x))).strip()
            for x in re.findall(r"<h1[^>]*>(.*?)</h1>", h, re.S)]


def inspect(path: str) -> list[str]:
    """1頁を検査して、問題の説明リストを返す(空=正常)。"""
    try:
        h = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return [f"読めない({e.__class__.__name__})"]
    bad = []
    txt = body_text(h)
    if len(txt) < BODY_FLOOR:
        bad.append(f"本文が空同然({len(txt)}字 < 床{BODY_FLOOR})=クライアント専用描画の疑い")
    hs = h1_texts(h)
    if len(hs) != 1:
        bad.append(f"h1が{len(hs)}個" + (f" {hs[:2]}" if hs else ""))
    mt = RE_TITLE.search(h)
    t = _html.unescape(mt.group(1)).strip() if mt else ""
    if not t:
        bad.append("titleが無い")
    elif t == DEFAULT_TITLE:
        bad.append("titleが既定のまま(頁側 metadata 未設定)")
    md = RE_DESC.search(h)
    d = _html.unescape(md.group(1)).strip() if md else ""
    if not d:
        bad.append("descriptionが無い")
    elif d.startswith(DEFAULT_DESC_HEAD):
        bad.append("descriptionが既定のまま(頁側 metadata 未設定)")
    return bad


def collect(sample: int, full: bool, seed: int) -> tuple[list[str], dict]:
    heavy = {"manga": [], "author": []}
    others = []
    for r, _d, fs in os.walk(OUT):
        if "_next" in r:
            continue
        for f in fs:
            if not f.endswith(".html"):
                continue
            p = os.path.join(r, f)
            rp = rel(p)
            if rp.startswith(SKIP_PREFIX):
                continue
            top = rp.split("/")[0]
            if top in heavy and "/" in rp:
                heavy[top].append(p)
            else:
                others.append(p)
    rnd = random.Random(seed)
    targets = list(others)
    picked = {}
    for k, v in heavy.items():
        take = v if full else rnd.sample(v, min(sample, len(v)))
        picked[k] = (len(take), len(v))
        targets += take
    picked["ハブ/コーナー"] = (len(others), len(others))
    return targets, picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=400, help="manga/author の抽出件数(既定400)")
    ap.add_argument("--full", action="store_true", help="manga/author も全数検査(数分)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--list", action="store_true", help="FAIL明細を全部出す")
    a = ap.parse_args()

    if not os.path.isdir(OUT):
        print("★out/ が無い = まだビルドしていない。週次蒸留/機能蒸留のビルド後に回す")
        return 0

    targets, picked = collect(a.sample, a.full, a.seed)
    print(f"検査対象 {len(targets):,}頁")
    for k, (n, tot) in picked.items():
        print(f"  {k:12} {n:>6,} / {tot:,}" + ("" if n == tot else "  (サンプリング)"))

    fails = []
    for i, p in enumerate(targets, 1):
        bad = inspect(p)
        if bad:
            fails.append((rel(p), bad))
        if i % 20000 == 0:
            print(f"   …{i:,}/{len(targets):,}", flush=True)

    # 症状ごとに畳んで出す(頁名の羅列より「型」が見えるように)
    import collections
    kinds = collections.Counter(b.split("(")[0].split("=")[0] for _p, bs in fails for b in bs)
    print(f"\n配信HTMLの中身: FAIL {len(fails)} / 検査 {len(targets):,}")
    for k, v in kinds.most_common():
        print(f"  {v:>6,}  {k}")
    if fails:
        print()
        show = fails if a.list else fails[:20]
        for p, bs in show:
            print(f"  FAIL /{p[:-5] if p.endswith('.html') else p}")
            for b in bs:
                print(f"       {b}")
        if len(fails) > len(show):
            print(f"  …他 {len(fails) - len(show)}件 (--list で全部)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
