#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配信HTMLの中身ゲート。

★結線の実態(2026-09-18 実地確認。旧docstringは「週次preflight/機能蒸留で回す」と書いていたが**嘘だった**):
  現在この番人を呼んでいるのは `_monthly-distill.py` の DETECTORS("ssr-content")**だけ**。
  週次(= 本番へ出す唯一の定期ルート)の `_weekly-preflight.py` は
  index-hygiene / shell-wiring / isbn-loss しか回しておらず、**ここは通らない**。
  → 正しい差し込み位置は週次の **手順3.5(build後・r2-sync前)** = out/ が新しく、かつ配信前。
     preflight(ビルド**前**)に入れると、太りを直すビルド自体を止めてしまう
     ([[shell_wiring_gates]] の検査4が WARN 止まりなのと同じ理由)。
  ★ただし結線は **/tokushu 等5頁を直してから**。今入れると次の週次が即 abort する。

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
  検査1 = 本文の実在   : <body> から **共通シェル(実測)を差し引いた頁固有の文字数** が床を超えるか
                        (クライアント専用描画の検出)。★2026-09-18 是正: 旧は床150を本文全体に
                        掛けており、シェルだけで363字あるため空頁が一件も落ちなかった。下の
                        CONTENT_FLOOR の節に経緯。
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

# ★2026-09-18 是正: 旧 `BODY_FLOOR = 150` は **共通シェルより低い床** だったため、
#   中身が完全にゼロの頁でも必ず通っていた(= この番人は原理的に空頁を検出できなかった)。
#   実測: 共通シェル(ヘッダ+左レール+フッタ)だけで **363字**(prefix 68 + suffix 295)。
#   /tokushu は本文394字 = シェル除外でわずか31字なのに「150字超」で緑になっていた。
#   実害: /tokushu /color-manga /tokusouban /sansedai-archive /aizouban の5コーナーが
#   「読み込み中…」だけの配信HTMLのまま公開され、番人は FAIL 0 を出し続けていた。
#
# 対策 = 床を **シェルを実測して差し引いた「頁固有の本文」** に対して掛ける。
#   シェル長は毎回 out/ から実測する(ハードコードしない = シェルが太っても自動追従する。
#   旧実装が壊れた原因そのものを機構で潰す)。
#
# 床はクラス別。★数字の根拠 = 2026-09-18 の実測(頁固有文字数の最小値。括弧内が床):
#   manga/      最小 277字(n=1,500)          → 150  … 余裕1.8倍
#   author/     最小  50字(n=1,500・中央83) →  40  … 1作品だけの著者頁が50字前後で正当。
#                                                    描画が壊れた著者頁は著者名だけ=20〜30字になる
#   art-books/  最小  90字(163頁全数)        →  60  … 画集1冊の個票(題・作者・出版年・Amazon導線)
#   既定(ハブ/コーナー) 正当な最小は /contact 165字・/browse 182字 → 150
# ★床を上げ下げする時は必ずこの実測を取り直す(定数だけ動かさない)。
CONTENT_FLOOR = 150
CONTENT_FLOOR_BY_PREFIX = {"art-books/": 60, "author/": 40}
# シェル長の実測に使うサンプル数(共通prefix/suffixを取るだけなので少数で十分)
SHELL_SAMPLE = 60

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


def measure_shell(paths: list[str], sample: int = SHELL_SAMPLE, seed: int = 7) -> tuple[int, str, str]:
    """全頁に共通して現れる本文の前置き/後置き(= 共通シェル)の長さを実測して返す。

    ヘッダ・ナビ・左レール・フッタは全頁で完全に同一文字列なので、
    本文テキストの **最長共通prefix + 最長共通suffix** がそのままシェルになる。
    ★ハードコードしない理由: 旧実装は床を定数150にしていたが、その後シェルが363字に太り、
      床がシェルより低くなって空頁を一件も検出できなくなっていた。実測なら自動追従する。
    ★サンプルに別構造の頁が混じるとprefix/suffixは**短くなる**=シェルを過小評価=床が厳しくなる。
      偽陽性(騒がしい)側に倒れるので、黙って見逃す方向には壊れない。
    """
    if not paths:
        return 0, "", ""
    rnd = random.Random(seed)
    texts = []
    for p in rnd.sample(paths, min(sample, len(paths))):
        try:
            texts.append(body_text(open(p, encoding="utf-8", errors="replace").read()))
        except OSError:
            pass
    if not texts:
        return 0, "", ""
    pre = texts[0]
    for t in texts[1:]:
        i = 0
        while i < len(pre) and i < len(t) and pre[i] == t[i]:
            i += 1
        pre = pre[:i]
    suf = texts[0]
    for t in texts[1:]:
        i = 0
        while i < len(suf) and i < len(t) and suf[len(suf) - 1 - i] == t[len(t) - 1 - i]:
            i += 1
        suf = suf[len(suf) - i:]
    return len(pre) + len(suf), pre, suf


def floor_for(rp: str) -> int:
    for pref, v in CONTENT_FLOOR_BY_PREFIX.items():
        if rp.startswith(pref):
            return v
    return CONTENT_FLOOR


def h1_texts(h: str) -> list[str]:
    return [re.sub(r"\s+", " ", _html.unescape(RE_TAG.sub("", x))).strip()
            for x in re.findall(r"<h1[^>]*>(.*?)</h1>", h, re.S)]


def inspect(path: str, shell: int = 0) -> list[str]:
    """1頁を検査して、問題の説明リストを返す(空=正常)。
    shell = 共通シェルの文字数(measure_shell の実測値)。本文からこれを引いた分に床を掛ける。"""
    try:
        h = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return [f"読めない({e.__class__.__name__})"]
    bad = []
    txt = body_text(h)
    content = max(0, len(txt) - shell)
    fl = floor_for(rel(path))
    if content < fl:
        bad.append(f"本文が空同然(頁固有{content}字 < 床{fl} / 本文{len(txt)}−シェル{shell})=クライアント専用描画の疑い")
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

    # ★共通シェルを毎回実測して床の基準にする(定数にしない = シェルが太っても追従する)
    shell, pre, suf = measure_shell(targets)
    print(f"  共通シェル実測 {shell:,}字(先頭{len(pre)}+末尾{len(suf)})/ 床 {CONTENT_FLOOR}字"
          + "".join(f" ・{k}={v}字" for k, v in CONTENT_FLOOR_BY_PREFIX.items()))
    if shell == 0:
        print("  ★WARN: シェルを実測できなかった(共通部分ゼロ)。床は本文全体に掛かる=厳しめに出る")

    fails = []
    for i, p in enumerate(targets, 1):
        bad = inspect(p, shell)
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
