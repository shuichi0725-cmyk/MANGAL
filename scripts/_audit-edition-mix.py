#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1つの版(edition)に★別の版の巻が混ざっている★頁を検出する。

★なぜ要るか (= 2026-08-01 ユーザ発見『ベルサイユのばら』から型化)
  「愛蔵版の書影が通常版に出ている」という書影の違和感を追ったら、正体は版の取り違えだった。
  中公愛蔵版の2巻(9784120015601)が通常版(中公コミックスーリ)の2巻スロットに座り、
  本当の2巻(9784124104257)は同じ巻番号に押し出されてどの頁にも出ていなかった。
  = ★書影の違和感は症状で、原因は版混在★ ([[feedback_cover_oddity_signal]])。

★2つの signal を独立に見る(片方だけだと本命を取り逃す)
  ① 出版者記号の混在 … ISBN の 978-4 直後の可変長コードが1版の中で2種類以上。
     ただし出版社移籍(末尾に連続)は正当なので TAIL/HEAD/SCATTERED に分ける。
  ② ★叢書名(楽天 seriesName)の混在 … 版取り違えの本命。
     ベルサイユのばら型は愛蔵版もスーリも出版者記号が同じ 978412 なので①では捕まらない。
     叢書名は「中公愛蔵版」対「中公コミックスーリ」で明確に割れる。

★自動修正はしない。是正は edition-canonical(版を権威データで再構築)や
  volume-exclude + extra-editions で per-case に当てる。

出力: docs/production-diagnostics/edition-mix.tsv
使い方:
  python scripts/_audit-edition-mix.py
"""
import argparse
import collections
import glob
import io
import json
import os
import sys
import unicodedata

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "edition-mix.tsv")
RAKUTEN = [os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"),
           os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl")]
COLS = ["分類", "slug", "題", "版type", "imprint", "publisher",
        "版の巻数", "多数派", "少数派", "少数派ISBN"]


def norm_isbn(s) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def jp_pub_prefix(s) -> str:
    """日本(978-4)ISBN の出版者記号プレフィックス(登録グループ長ルール・可変長2-7桁)。
    ★固定長 slice は大手(講談社06等)を誤分割する。_promote-bulk-v2.py と同じ規則。"""
    i = norm_isbn(s)
    if len(i) < 13 or not i.startswith("9784"):
        return i[:7]
    r = i[4:]
    if r[0] in "01":
        ln = 2
    elif r[0] in "23456":
        ln = 3
    elif "70" <= r[:2] <= "84":
        ln = 4
    elif "85" <= r[:2] <= "89":
        ln = 5
    elif "900" <= r[:3] <= "949":
        ln = 6
    else:
        ln = 7
    return i[:4 + ln]


def norm_series(s: str) -> str:
    """叢書名の照合キー。★同じ叢書の表記ゆらぎを潰さないと誤検出だらけになる。
    初回実測の誤検出例: ジャンプコミックス/ジャンプ・コミックス、花とゆめコミックス/花とゆめCOMICS、
    ニチブンコミックス/NICHIBUN COMICS/Nichibun comics。
    → NFKC + 小文字化 + 記号(中黒・長音・ハイフン・括弧)除去 + comics 系の表記統一。"""
    t = unicodedata.normalize("NFKC", s or "").lower()
    for a, b in (("comics", "コミックス"), ("comic", "コミック"),
                 ("ladys", "レディース"), ("lady's", "レディース")):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch not in " 　・·‐-—―ー()（）[]【】’'\"")


def load_series_map(needed: set) -> dict:
    """isbn13 → 楽天 seriesName(叢書名)。本番に在るISBNだけ拾う。"""
    out = {}
    for fn in RAKUTEN:
        if not os.path.exists(fn):
            continue
        for line in io.open(fn, encoding="utf-8", errors="replace"):
            if '"seriesName"' not in line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            i = norm_isbn(o.get("isbn"))
            if i in needed and i not in out:
                sn = ((o.get("item") or {}).get("seriesName") or "").strip()
                if sn:
                    out[i] = sn
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-minority", type=int, default=1)
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(SRC, "*.yml")))
    print(f"走査 {len(files)} 頁", flush=True)

    pages, all_isbn = [], set()
    for n, p in enumerate(files, 1):
        if n % 20000 == 0:
            print(f"  読込 {n}", flush=True)
        try:
            d = yaml.safe_load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        eds = []
        for ed in (d.get("editions") or []):
            vols = [v for v in (ed.get("volumes") or []) if v.get("isbn13")]
            if len(vols) >= 2:
                eds.append((ed, vols))
                all_isbn.update(norm_isbn(v["isbn13"]) for v in vols)
        if eds:
            pages.append((d, eds))
    print(f"  対象 {len(pages)}頁 / ISBN {len(all_isbn)}件 → 楽天の叢書名を索く", flush=True)
    smap = load_series_map(all_isbn)
    print(f"  叢書名が取れたISBN: {len(smap)}件", flush=True)

    rows, cls_n = [], collections.Counter()
    for d, eds in pages:
        slug = d.get("slug") or ""
        title = d.get("title") or ""
        for ed, vols in eds:
            meta = [str(ed.get("edition_type")), str(ed.get("imprint")), str(ed.get("publisher"))]

            # ① 出版者記号の混在
            pref = [jp_pub_prefix(v["isbn13"]) for v in vols]
            cnt = collections.Counter(pref)
            if len(cnt) >= 2:
                major, major_n = cnt.most_common(1)[0]
                minority = cnt.most_common()[1:]
                if sum(c for _, c in minority) >= a.min_minority:
                    idx = [i for i, pr in enumerate(pref) if pr != major]
                    tail = idx == list(range(len(pref) - len(idx), len(pref)))
                    head = idx == list(range(len(idx)))
                    kind = ("TAIL(移籍らしい)" if tail
                            else "HEAD(前半別社)" if head else "SCATTERED(汚染らしい)")
                    cls_n[kind] += 1
                    odd = [str(v["isbn13"]) for v, pr in zip(vols, pref) if pr != major]
                    rows.append([kind, slug, title] + meta + [
                        str(len(vols)), f"{major}x{major_n}",
                        " / ".join(f"{pr}x{c}" for pr, c in minority), ",".join(odd)[:80]])

            # ② ★叢書名の混在(本命)= 出版者記号が同じでも捕まえる
            sn = [norm_series(smap.get(norm_isbn(v["isbn13"]), "")) for v in vols]
            known = [x for x in sn if x]
            if len(known) < 3:
                continue
            sc = collections.Counter(known)
            smaj, smaj_n = sc.most_common(1)[0]
            odd_v = [v for v, x in zip(vols, sn) if x and x != smaj]
            # 少数派が既知の1/3未満の時だけ(半々なら版そのものが2叢書=別問題)
            if not odd_v or len(odd_v) >= len(known) / 3:
                continue
            # ★優先度: 多数派と少数派が包含関係なら同じ叢書の表記/サブレーベル差の疑いが濃い
            #   (ビッグコミックス ⊂ ビッグコミックス〔オリジナル〕)。包含しなければ別叢書=本命。
            odd_keys = {x for x in sn if x and x != smaj}
            contained = all(k.startswith(smaj) or smaj.startswith(k) for k in odd_keys)
            kind = "SERIES低(表記/サブレーベル差)" if contained else "SERIES高(別叢書の混入)"
            cls_n[kind] += 1
            maj_raw = next((smap[norm_isbn(v["isbn13"])] for v, x in zip(vols, sn) if x == smaj), smaj)
            min_raw = sorted({smap[norm_isbn(v["isbn13"])] for v in odd_v if norm_isbn(v["isbn13"]) in smap})
            rows.append([kind, slug, title] + meta + [
                str(len(vols)), f"{maj_raw}x{smaj_n}", " / ".join(min_raw),
                ",".join(str(v["isbn13"]) for v in odd_v)[:80]])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(COLS) + "\n")
        for r in sorted(rows):
            fh.write("\t".join(r) + "\n")
    print(f"\n該当 {len(rows)} 版 → {os.path.relpath(OUT, ROOT)}")
    for k, c in cls_n.most_common():
        print(f"   {k}: {c}")
    print("★自動修正しない。SERIES高 が版取り違えの本命。TAIL は移籍、SERIES低 は表記差が多い。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
