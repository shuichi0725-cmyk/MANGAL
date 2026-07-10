#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""漫画全巻ドットコム(mangazenkan.com) 巡回harvest(2026-07-09)。

連載状況(完結/連載中)の本命ソース。tags=完結/連載中 の一覧をページ送りで全巡回し、
各作の 作品名/巻数(1-N全巻)/作者/出版社 を客観抽出(レビュー・価格・星は除外)。
MANGALと題×著者で照合し 連載状況+全巻数 を確定する土台。

TinyFish fetch(無料)で取得。1.1秒/req厳守。空ページ or max到達で停止。resumable(cursor)。

使い方:
  python scripts/_mangazenkan-harvest.py --tag 完結 --test 3      # 3ページだけ試験
  python scripts/_mangazenkan-harvest.py --tag 完結               # 全ページ(空まで)
  python scripts/_mangazenkan-harvest.py --tag 連載中             # 連載中一覧
出力: .cache/mangazenkan-<tag>.jsonl (1作1行) / cursor: .cache/mangazenkan-<tag>.cursor
"""
import argparse, json, os, re, sys, time, urllib.parse

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from _tinyfish import fetch

RATE = 1.1

# 1商品ブロック: 「作品名 (1-N巻 全巻)」に続いて表で 作者/出版社
_TITLE = re.compile(r"([^\n|（(【]{1,60}?)\s*[（(]\s*([\d]+(?:-[\d]+)?)\s*巻\s*全巻\s*[)）]")


def parse_page(text):
    """ページtext→作品list。title/volumes/author/publisher。星評価/価格は取らない。"""
    out = []
    ms = list(_TITLE.finditer(text))
    for i, m in enumerate(ms):
        title = m.group(1).strip(" 　|")
        vols = m.group(2)  # "1-23" or "36"
        seg = text[m.end(): ms[i + 1].start() if i + 1 < len(ms) else m.end() + 400]
        au = re.search(r"作者\s*\|\s*([^\n|]+)", seg)
        pub = re.search(r"出版社\s*\|\s*([^\n|]+)", seg)
        if not title:
            continue
        out.append({
            "title": title,
            "volumes_full": vols,           # 完結全巻数の範囲(1-N or N)
            "author": (au.group(1).strip() if au else ""),
            "publisher": (pub.group(1).strip() if pub else ""),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="完結")
    ap.add_argument("--test", type=int, default=0, help="Nページだけ試験(0=全ページ)")
    ap.add_argument("--max", type=int, default=800, help="安全上限ページ")
    a = ap.parse_args()

    tagq = urllib.parse.quote(a.tag)
    out_path = os.path.join(ROOT, ".cache", f"mangazenkan-{a.tag}.jsonl")
    cur_path = os.path.join(ROOT, ".cache", f"mangazenkan-{a.tag}.cursor")
    start = 1
    if not a.test and os.path.exists(cur_path):
        start = int(open(cur_path).read().strip() or "1") + 1
        print(f"resume: page {start} から")

    mode = "w" if a.test else "a"
    seen_titles = set()
    total = 0
    limit = a.test or a.max
    with open(out_path if not a.test else out_path + ".test", mode, encoding="utf-8") as fo:
        page = start
        end = start + a.test - 1 if a.test else a.max
        while page <= end:
            url = f"https://www.mangazenkan.com/s/?tags={tagq}&page={page}"
            res = fetch([url])
            txt = (res.get("results") or [{}])[0].get("text", "") if isinstance(res, dict) else ""
            works = parse_page(txt)
            if not works:
                print(f"page {page}: 0作 → 終端とみなし停止")
                break
            n = 0
            for w in works:
                key = (w["title"], w["author"])
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                w["tag"] = a.tag
                fo.write(json.dumps(w, ensure_ascii=False) + "\n")
                n += 1
            total += n
            if not a.test:
                open(cur_path, "w").write(str(page))
            print(f"page {page}: {n}作 (累計{total})")
            page += 1
            time.sleep(RATE)
    print(f"\n完了: {total}作 → {out_path if not a.test else out_path + '.test'}")


if __name__ == "__main__":
    main()
