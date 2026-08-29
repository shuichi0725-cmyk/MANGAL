#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""頁をまたぐISBN重複 監査 (= 同じ1冊が2つ以上の作品頁に載っている型。 2026-08-29 新設)。

★何を見るか
  `.cache/volume-flat.tsv`(本番全巻を1行1巻に展開)を1パスで読み、 **同一 isbn13 が複数 slug(頁)に
  現れる**ものを **ISBN単位**で名指しする。 1冊の本は1つの作品頁にしか属せないので、
  頁をまたぐ同一ISBNは「どちらかの頁が間違っている」= 必ず是正対象。
  (同名別作品は題を共有してもISBNは共有しない = ISBN一致は題一致より遥かに強い証拠)

★なぜ既存の `_audit-isbn-dup-pages.py` と別に要るか (= 重複範囲と差分)
  既存器は同じ現象を見るが **頁ペア単位**に畳んで重なり率(≥50%=DUP_PAGE / 未満=SHARED_FEW)の
  2分類しか出さない。 そのため以下が構造的に見えない:
   1. ★**3頁以上が同じISBNを共有**する型 (= ペアに分解され 3行の SHARED_FEW に散る)
   2. ★**片方の頁でその巻だけが孤立**している型 (= その版に ≤2巻 しか無く、その全部が相手頁と
      共有 = 相手頁の巻が丸ごと接ぎ木されている。 是正の「向き」が機械的に確定する最強候補)
   3. **巻番号の食い違い** (= 同じISBNが頁Aでは3巻・頁Bでは7巻。 少なくとも片方は誤スロット)
   4. **versions[](刷タブ)由来かどうか** (= 既存器は yml 全文の正規表現なので刷タブのISBNも
      本文の巻と同列に数え、原因の切り分けができない)
  → 本器は ISBN 1個 = 1行、 上記4signalを列に持たせ、 是正の向きまで示す。

★分類 (severity 降順)
  TRIPLE_PLUS     : 3頁以上が共有。 最大でも1頁しか正しくない
  WRONG_ISBN_FILL : 共有が ≤2冊 かつ 2頁の**著者が全く重ならない**。 = 頁の二重化ではなく
                    「別作品のISBNをその巻に埋めてしまった」型 (= 9番目のムサシ16巻に2024年の
                    続編のISBNが入っていた実例)。 書影・リンク・発売日まで別の本になり実害が大きい。
                    ★共有が多い時はこの判定を使わない: 著者欄の汚染(解説者・原作クレジット混入)
                    で同一作の二重頁でも著者が交わらないことがある(聖魔伝/怪物くんで実踏)
  GRAFT_ISOLATED  : 片方が**衛星頁** = 頁全体が ≤2冊 で、その全部がもう一方のより大きな頁に
                    入っている。 = 大きい頁の巻が丸ごと接ぎ木されて小頁として独立した型。
                    ★是正の向き(衛星側を片寄せる)が機械的に確定する最強候補
  NUMBER_MISMATCH : 同一ISBNなのに頁ごとに巻番号が違う
  PAGE_DUP        : 3冊以上を共有し 小さい方の頁のISBNの50%以上が重なる = 頁丸ごと二重
                    (既存器 DUP_PAGE とほぼ同義。 ★1冊しか無い頁は ratio が常に100%になり
                     意味を成さないので「3冊以上」を課し、衛星頁は GRAFT_ISOLATED に回す)
  VERSION_TAB     : 片方が versions[](刷タブ)由来。 刷タブに他作品の本が紛れた型
  SHARED_FEW      : 上記に当たらない少数共有 (= 既存器と同じ弱シグナル)

★既知の偽陽性/注意
  - **合本/愛蔵版が2作品を1冊に収録**している場合、同じISBNが両作品の頁に載るのは書誌的には
    正当。 ただし MANGAL は1冊=1頁の建付けなので片寄せの裁定は要る(偽陽性というより設計判断)。
  - 上下巻/前後編の分冊・番外編0巻は ISBN が違うので本器の判定に影響しない。
  - 復刻版/新装版/文庫版が**同一頁**に並ぶのは正当。 本器は別頁しか見ないので混入しない。
  - ISBN-10→13 変換の名残で同じ本が別ISBNを持つ型は、ISBNが一致しないので本器の対象外。
  - 非9784(外国版)は `_audit-foreign-editions.py` の担当。 本器の実測では0件。
  - 同一頁の複数版が同ISBNを持つ「頁内ダブリ」は本器の対象外(= `_audit-cover-dup.py` /
    isbn-dup-cleanup 領域)。

★是正先
  - 頁丸ごと二重 → `data/seeds/page-dedup.yml`
  - 片方の頁からの巻の除去 → `data/seeds/volume-exclude*.yml` / `edition-overrides.json`(キー=公開slug)
  - 版の再構築が要る場合 → `data/seeds/edition-canonical/*.yml`(キー=SRC slug)
  ※本器は**調査のみ・本番不変**。

出力: docs/production-diagnostics/isbn-crosspage-dup.tsv
使い方: python scripts/_audit-isbn-crosspage-dup.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
MV2 = os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-crosspage-dup.tsv")

RE_AUTHOR = re.compile(r"^- name:\s*(.+?)\s*$", re.M)
RE_GENRE_ITEM = re.compile(r"^- \S")


def page_authors(slug):
    """flag された頁だけ yml を開いて著者名集合を取る (= 全66k走査はしない)。

    authors[] と original_authors[] の `- name:` を拾う。 genres[] 等の裸リストは
    `- name:` 形式でないので混ざらない。
    """
    p = os.path.join(MV2, slug + ".yml")
    try:
        t = open(p, encoding="utf-8").read()
    except OSError:
        return set()
    return set(RE_AUTHOR.findall(t))

ISOLATED_MAX = 2   # 「衛星頁」とみなす頁の冊数上限


def main():
    if not os.path.exists(FLAT):
        print("見つからない: " + FLAT, file=sys.stderr)
        sys.exit(2)

    # --- 1パス走査 -------------------------------------------------------
    isbn_rows = defaultdict(list)          # isbn13 -> [row,...]
    ed_vols = defaultdict(int)             # (slug, ed_idx) -> 巻数(刷タブ除く)
    ed_isbns = defaultdict(set)            # (slug, ed_idx) -> {isbn}
    page_isbns = defaultdict(set)          # slug -> {isbn}
    page_title = {}                        # slug -> title
    page_vols = defaultdict(int)           # slug -> 巻数(刷タブ除く)
    n_rows = 0

    with open(FLAT, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            n_rows += 1
            slug = row["slug"]
            page_title.setdefault(slug, row["title"])
            isbn = row["isbn13"].strip()
            isver = row["is_version"] == "1"
            key = (slug, row["ed_idx"])
            if not isver:
                ed_vols[key] += 1
                page_vols[slug] += 1
            if not isbn:
                continue
            isbn_rows[isbn].append(row)
            if not isver:
                ed_isbns[key].add(isbn)
                page_isbns[slug].add(isbn)

    # --- 頁をまたぐISBNだけ残す ------------------------------------------
    cross = {i: rs for i, rs in isbn_rows.items() if len(set(r["slug"] for r in rs)) > 1}

    group_shared = defaultdict(set)        # frozenset(slugs) -> {isbn}
    for isbn, rs in cross.items():
        group_shared[frozenset(r["slug"] for r in rs)].add(isbn)

    # 巻き込まれた頁だけ著者を引く(数百件。 全66k走査ではない)
    touched = sorted(set(s for g in group_shared for s in g))
    authors = dict((s, page_authors(s)) for s in touched)

    def ed_desc(r):
        parts = [r["ed_type"], r["ed_imprint"] or r["ed_publisher"]]
        return "/".join(p for p in parts if p)

    def side(r):
        slug = r["slug"]
        key = (slug, r["ed_idx"])
        return {
            "slug": slug,
            "title": page_title.get(slug, ""),
            "ed": ed_desc(r),
            "num": r["number"],
            "date": r["release_date"],
            "ed_vols": ed_vols.get(key, 0),
            "ed_isbns": ed_isbns.get(key, set()),
            "page_vols": page_vols.get(slug, 0),
            "isver": r["is_version"] == "1",
        }

    rows = []
    for isbn, rs in cross.items():
        slugs = sorted(set(r["slug"] for r in rs))
        gshared = group_shared[frozenset(slugs)]
        # 1頁につき代表1行(頁内の複数版に同ISBNが在る場合は本文の巻を優先)
        by_slug = {}
        for r in rs:
            s = r["slug"]
            if s not in by_slug or (by_slug[s]["is_version"] == "1" and r["is_version"] == "0"):
                by_slug[s] = r
        sides = [side(by_slug[s]) for s in slugs]

        # --- 衛星頁(孤立)判定 --------------------------------------------
        # ★「版」でなく「頁」の大きさで見る。 版で見ると、19巻の頁どうしが丸ごと二重に
        #   なっているだけ(= 各版は1〜2巻ずつ)でも孤立と誤判定する(ウルトラセブンで実踏)。
        # 衛星 = その頁の全ISBNが ≤ISOLATED_MAX冊 で、全部が相手のより大きな頁に入っている。
        isolated = []
        for s in slugs:
            mine = page_isbns.get(s, set())
            rest = set()
            for t in slugs:
                if t != s:
                    rest |= page_isbns.get(t, set())
            if mine and len(mine) <= ISOLATED_MAX and mine <= rest and len(rest) > len(mine):
                isolated.append(s)

        nums = set(s["num"] for s in sides if s["num"])
        num_mismatch = len(nums) > 1
        ver_involved = any(s["isver"] for s in sides)

        smalls = [len(page_isbns.get(s, ())) for s in slugs]
        small = min(smalls) or 1
        ratio = len(gshared) / small

        # 著者が全く重ならない = 頁の二重化でなく「別作品のISBNを埋めた」型
        asets = [authors.get(s, set()) for s in slugs]
        known = [a for a in asets if a]
        author_rel = "?"
        if len(known) == len(slugs) and len(slugs) > 1:
            inter = set.intersection(*known)
            author_rel = "共通著者あり" if inter else "著者不一致"

        n_pages = len(slugs)
        if n_pages >= 3:
            klass = "TRIPLE_PLUS"
        elif isolated:
            klass = "GRAFT_ISOLATED"
        elif author_rel == "著者不一致" and len(gshared) <= 2:
            klass = "WRONG_ISBN_FILL"
        elif len(gshared) >= 3 and ratio >= 0.5:
            # ★頁が丸ごと重なる時は著者文字列で判定しない。 著者欄の汚染(解説者・原作
            #   クレジット混入 = author-not-in-volumes 系)が普通に在り、同一作の二重頁でも
            #   著者集合が交わらないことがある(聖魔伝/怪物くんで実踏)。
            klass = "PAGE_DUP"
        elif num_mismatch:
            klass = "NUMBER_MISMATCH"
        elif ver_involved:
            klass = "VERSION_TAB"
        else:
            klass = "SHARED_FEW"

        rows.append({
            "class": klass,
            "isbn13": isbn,
            "n_pages": n_pages,
            "group_shared_n": len(gshared),
            "group_ratio": "%d%%" % round(ratio * 100),
            "author_rel": author_rel,
            "isolated_side": ",".join(isolated),
            "num_mismatch": "1" if num_mismatch else "",
            "version_side": ",".join(s["slug"] for s in sides if s["isver"]),
            "pages": " | ".join(
                "%s[%s] ed=%s vol=%s ed_vols=%d page_vols=%d date=%s" % (
                    s["slug"], s["title"], s["ed"], s["num"] or "-",
                    s["ed_vols"], s["page_vols"], s["date"] or "-")
                for s in sides),
            "group_id": "+".join(slugs),
        })

    order = {"WRONG_ISBN_FILL": 0, "TRIPLE_PLUS": 1, "GRAFT_ISOLATED": 2,
             "NUMBER_MISMATCH": 3, "PAGE_DUP": 4, "VERSION_TAB": 5, "SHARED_FEW": 6}
    rows.sort(key=lambda r: (order[r["class"]], -r["n_pages"], -r["group_shared_n"],
                             r["group_id"], r["isbn13"]))

    cols = ["class", "isbn13", "n_pages", "group_shared_n", "group_ratio",
            "author_rel", "isolated_side", "num_mismatch", "version_side",
            "pages", "group_id"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    cnt = defaultdict(int)
    for r in rows:
        cnt[r["class"]] += 1
    n_pages_touched = len(set(s for g in group_shared for s in g))
    print("走査: %d巻 / ISBN %d種" % (n_rows, len(isbn_rows)))
    print("頁をまたぐISBN: %d件 / 頁グループ %d組 / 巻き込まれた頁 %d頁"
          % (len(cross), len(group_shared), n_pages_touched))
    for k in sorted(cnt, key=lambda k: order[k]):
        print("  %-16s%5d件" % (k, cnt[k]))
    print("→ " + os.path.relpath(OUT, ROOT))
    print("")
    print("== 強候補(WRONG_ISBN_FILL / TRIPLE_PLUS) ==")
    for r in rows:
        if r["class"] not in ("WRONG_ISBN_FILL", "TRIPLE_PLUS"):
            continue
        print("  [%s] %s 共有%d冊 著者=%s 衛星=%s"
              % (r["class"], r["isbn13"], r["group_shared_n"], r["author_rel"],
                 r["isolated_side"] or "-"))
        print("      " + r["pages"])


if __name__ == "__main__":
    main()
