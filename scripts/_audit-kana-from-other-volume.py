#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坊っちゃん型ヨミ取り違え検出器 (2026-07-10)。

症状: 部題・テーマ題シリーズで、頁の title_kana が「自頁の別の巻の題」の読みに化ける
(『坊っちゃん』の時代のヨミ=アキノマイヒメ[第2部『秋の舞姫』の読み] で発見)。

判定(当て字情報に依存しない設計):
  1. 頁の巻真題(isbn-title-map)の基底題が2種以上=テーマ題持ち頁だけ対象
  2. 頁kana ≒ いずれかの巻題の機械読み(pykakasi) かつ その巻題≠頁題
  3. かつ 頁題自身の機械読み≠頁kana (頁題と読みが合っているなら正常)
  当て字(SS=サイボーグサラリーマン等)は「自巻題の機械読み」と一致しないので誤爆しない。
  全巻が同一基底(latin題頁のカナ巻題等)は対象外=title表記差クラスに委ねる。

使い方: python scripts/_audit-kana-from-other-volume.py
出力: docs/production-diagnostics/kana-from-other-volume.tsv
"""
import glob, json, os, re, sys, unicodedata
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import yaml
from _preorder_draft_lib import _to_kata_reading


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"[\s　・、。,\.:：!！?？「」『』（）()\[\]〔〕★☆=＝\-〜~ー]", "", s)


def strip_vol(t):
    t = re.sub(r"[（(]\s*[0-9０-９上下]+\s*[）)]\s*(＜完＞|完)?\s*$", "", str(t or ""))
    t = re.sub(r"[\s　]+[0-9０-９]+\s*(巻)?\s*$", "", t)
    t = re.sub(r"(新装版|ワイド版|愛蔵版|文庫版|完全版)\s*$", "", t)
    return t.strip()


def main():
    tmap = json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8"))
    rows, scanned, themed = [], 0, 0
    for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        scanned += 1
        try:
            d = yaml.safe_load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        kana = norm(d.get("title_kana"))
        if not kana or re.search(r"[a-zA-Z一-鿿]", kana):
            continue                              # kana無し/壊れ別クラスは対象外
        title_n = norm(d.get("title"))
        bases = {}
        for e in d.get("editions") or []:
            for v in e.get("volumes") or []:
                t = tmap.get(v.get("isbn13") or "")
                if t:
                    b = strip_vol(t)
                    if b:
                        bases[norm(b)] = b
        if len(bases) < 2:
            continue                              # 基底題が単一=テーマ題頁でない
        themed += 1
        # 頁題自身の読みがkanaと概ね合っていれば正常(連濁/長音のpykakasiブレは類似度で吸収)
        own = norm(_to_kata_reading(d.get("title")))
        if own and SequenceMatcher(None, own, kana).ratio() >= 0.75:
            continue
        if not own:
            continue                              # latin題=読み不能は別クラス(表記差)に委ねる
        for bn, braw in bases.items():
            if bn == title_n or title_n in bn or bn in title_n:
                continue                          # 頁題と同系の巻題は除外
            r = norm(_to_kata_reading(braw))
            if not (r and len(r) >= 3 and (r == kana or r.startswith(kana) or kana.startswith(r))):
                continue
            # ★坊っちゃん署名: 犯人巻題の読みが頁題の読みと「別物」である時だけ(表記変種を除外)
            if SequenceMatcher(None, own, r).ratio() >= 0.5:
                continue
            rows.append((os.path.splitext(os.path.basename(p))[0], d.get("title"),
                         d.get("title_kana"), braw, r))
            break
    out = os.path.join(ROOT, "docs", "production-diagnostics", "kana-from-other-volume.tsv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write("slug\tpage_title\tpage_kana\tculprit_vol_title\tvol_reading\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"走査 {scanned} 頁 / テーマ題持ち {themed} 頁 / ★ヨミ取り違え検出: {len(rows)} → {os.path.relpath(out, ROOT)}")
    for r in rows:
        print(f"  {r[0]}: 題={r[1]!r} ヨミ={r[2]!r} ← 犯人巻題={r[3]!r}")


if __name__ == "__main__":
    main()
