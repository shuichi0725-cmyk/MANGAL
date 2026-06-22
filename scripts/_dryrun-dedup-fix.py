#!/usr/bin/env python3
"""dedup 修正の ★ドライラン (= read-only、 manga.v2 に一切書かない)。

目的: promote の巻 dedup を「最古日付優先」→「★多数派出版者線を最優先→その中で最古日付」
に変えた場合の影響を、 本番出力(現状)と突合して定量化する。 適用はしない。

安全性質(実証対象): 提案 dedup は候補が全て同一出版者線のとき従来と完全一致(=単一社ページ無変化)。
変わるのは ★複数出版者が競合する番号だけ(=汚染/多版の箇所)。

手順(各 affected slug):
  1. 本番 yml の全 edition から ISBN を集める → isbn→sid で実 merge sid 群を復元(出力=真の grouping)
  2. その sid 群の KEEP-type source 巻を番号別に集め、 dom_pub(=多数派出版者線) を決める
  3. 提案 dedup で番号別 pick を計算 → 現状出力の pick と比較
  4. 差分を分類: RESTORE_MISSING(出力に無い番号が復活) / PUB_SWAP(別社→本物に是正) / OTHER
出力: .cache/dryrun-dedup-*.tsv + docs/audit/dryrun-dedup-summary.md (read-only レポート)
"""
import sys, os, glob, json
from collections import defaultdict, Counter
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
MANGA = ROOT / "data" / "manga.v2"
KEEP_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}


def norm_isbn(s) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit()) if s is not None else ""


def jp_pub_prefix(isbn: str) -> str:
    i = norm_isbn(isbn)
    if len(i) < 13 or not i.startswith("9784"): return i[:7]
    r = i[4:]
    if r[0] in "01": ln = 2
    elif r[0] in "23456": ln = 3
    elif "70" <= r[:2] <= "84": ln = 4
    elif "85" <= r[:2] <= "89": ln = 5
    elif "900" <= r[:3] <= "949": ln = 6
    else: ln = 7
    return i[:4 + ln]


def date_key(rd) -> str:
    return str(rd) if rd else "9999-99"


def affected_slugs():
    slugs = set()
    for fn in ("missing1", "gap", "pubmix", "datedisorder"):
        p = ROOT / ".cache" / f"audit-vol-output-{fn}.tsv"
        if not p.exists(): continue
        with p.open(encoding="utf-8") as f:
            next(f, None)
            for line in f:
                s = line.split("\t", 1)[0].strip()
                if s: slugs.add(s)
    return slugs


def main():
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    # source index: isbn→sid, sid→{type:{number:[(isbn,rd)]}}
    isbn2sid = {}
    sid_vol = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for sid, ty, num, isbn, rd in con.execute(
        """SELECT e.series_id, e.type, v.number, v.isbn13, v.release_date
           FROM volumes v JOIN editions e ON e.id=v.edition_id
           WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"""):
        ni = norm_isbn(isbn)
        if not ni: continue
        isbn2sid[ni] = sid
        if ty in KEEP_TYPES and num:
            sid_vol[sid][ty][num].append((ni, rd))

    slugs = affected_slugs()
    rows = []
    n_pages_changed = 0; n_restore = 0; n_pubswap = 0; n_other = 0; n_pages = 0
    for slug in sorted(slugs):
        p = MANGA / f"{slug}.yml"
        if not p.exists(): continue
        try: d = yaml.load(p.open(encoding="utf-8"), Loader=L)
        except Exception: continue
        if not d: continue
        n_pages += 1
        # 出力の全 ISBN → 実 merge sid 群
        out_isbns, out_pick = [], {}  # out_pick[(type,number)] = isbn
        for ed in (d.get("editions") or []):
            ty = ed.get("type")
            if ty not in KEEP_TYPES: continue
            for v in (ed.get("volumes") or []):
                ni = norm_isbn(v.get("isbn13"))
                n = v.get("number")
                if ni: out_isbns.append(ni)
                if ni and isinstance(n, int):
                    out_pick[(ty, n)] = ni
        sidset = {isbn2sid[i] for i in out_isbns if i in isbn2sid}
        if not sidset: continue
        # type別に候補を集約 → dom_pub は type 横断の多数派(=主出版線)
        cand = defaultdict(lambda: defaultdict(list))  # cand[type][number] = [(isbn,rd)]
        all_pubs = Counter()
        for sid in sidset:
            for ty, byn in sid_vol.get(sid, {}).items():
                for num, lst in byn.items():
                    cand[ty][num].extend(lst)
                    for isbn, _ in lst: all_pubs[jp_pub_prefix(isbn)] += 1
        if not all_pubs: continue
        dom_pub = all_pubs.most_common(1)[0][0]
        multi_pub = len(all_pubs) > 1
        # 提案 dedup で pick
        page_changes = []
        for ty, byn in cand.items():
            for num, lst in byn.items():
                proposed = min(lst, key=lambda iv: (0 if jp_pub_prefix(iv[0]) == dom_pub else 1,
                                                     date_key(iv[1]), iv[0]))[0]
                cur = out_pick.get((ty, num))
                if cur == proposed:
                    continue
                if cur is None:
                    kind = "RESTORE_MISSING"; n_restore += 1
                elif jp_pub_prefix(cur) != jp_pub_prefix(proposed) and jp_pub_prefix(proposed) == dom_pub:
                    kind = "PUB_SWAP"; n_pubswap += 1
                else:
                    kind = "OTHER"; n_other += 1
                page_changes.append((ty, num, kind, cur or "(無)", proposed))
        if page_changes:
            n_pages_changed += 1
            for ty, num, kind, cur, prop in page_changes:
                rows.append([slug, d.get("title") or "", ty, num, kind, cur, prop,
                             dom_pub, "multi" if multi_pub else "single"])

    rows.sort(key=lambda r: (r[4] != "RESTORE_MISSING", r[4] != "PUB_SWAP", r[0]))
    with (ROOT / ".cache" / "dryrun-dedup-changes.tsv").open("w", encoding="utf-8") as f:
        f.write("slug\ttitle\ttype\tnumber\tkind\tcurrent\tproposed\tdom_pub\tpubclass\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    # 安全性質チェック: single(単一出版者)ページで変化が出ていないか
    single_changes = sum(1 for r in rows if r[8] == "single")
    summary = (
        f"# dedup修正ドライラン (read-only / 書込なし)\n\n"
        f"- 対象 affected ページ: {n_pages:,}  /  変化が出たページ: {n_pages_changed:,}\n"
        f"- 変化した番号(巻)総数: {len(rows):,}\n"
        f"  - RESTORE_MISSING (欠番が復活): {n_restore:,}\n"
        f"  - PUB_SWAP (別社→多数派本物に是正): {n_pubswap:,}\n"
        f"  - OTHER (要確認): {n_other:,}\n"
        f"- ★安全性質: 単一出版者(single)ページで変化した番号 = {single_changes:,} "
        f"(0 が理想 = 単一社ページ無変化)\n"
    )
    (ROOT / "docs" / "audit" / "dryrun-dedup-summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    print("菜(sai) の変化:")
    for r in rows:
        if r[0] == "sai":
            print(f"  #{r[3]} {r[4]}: {r[5]} → {r[6]}")
    print("\nRESTORE_MISSING / PUB_SWAP 例:")
    for r in rows[:12]:
        print(f"  {r[0]} #{r[3]} {r[4]}: {r[5]} → {r[6]}")


if __name__ == "__main__":
    main()
