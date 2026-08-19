# -*- coding: utf-8 -*-
"""がきデカ型=一部ISBN欠け巻の機械是正 (2026-08-19 ユーザGO)。

対象: 同一edition内でISBN有巻と無巻が混在する頁(初回実測824頁/2,179巻)。
候補生成2経路 × 検証必須(二重証拠のみ自動適用、単一証拠は報告のみ):
  経路1 帯内挿: editionの既知ISBNが「コード=定数+巻番号」の線形連番なら欠け巻を内挿/外挿
  経路2 楽天逆引き: 楽天キャッシュ(isbn-title-map)を(正規化題,巻番号)で逆引き
検証(自動適用の条件、両経路とも):
  a. 候補ISBNの楽天題が 頁題(正規化)を含み、かつ題中の巻番号==欠け巻番号
  b. 候補ISBNの出版者帯(先頭8桁)が そのeditionの既存ISBN帯の多数派と一致(edition-mix教訓)
  c. 候補ISBNが本番の他の巻/頁で未使用(ダブリ防止)
適用先: isbn-fill.json(純粋追加・isbn13空巻のみ充填=promoteガード済)。
★isbn-fill.jsonのキー=公開slug(edition-overridesと同じ。SRC stemは死にキー=無警告不適用。
  2026-08-19実踏: slug-override頁11件が不着→公開slugへrekeyで解決。--applyは公開slugで書く)。
★edition-canonical結線頁はfillが後勝ちで無効なため自動適用せずTSVへ(人がcanonical本体を直す)。
未解決は docs/production-diagnostics/partial-isbn-gap-unresolved.tsv へ。

usage: python scripts/_fix-partial-isbn-gaps.py [--apply]  (無印=dry-run)
"""
import glob
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
APPLY = "--apply" in sys.argv

NUM_PAT = re.compile(r"[（(]\s*(\d+)\s*[)）]|第(\d+)巻|(\d+)巻|\bvol\.?\s*(\d+)", re.I)


def norm_title(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[\s　・‐\-—―:：!！?？'’\"”「」『』〜~、。.,]", "", s)


def rak_vol(title: str) -> int | None:
    t = unicodedata.normalize("NFKC", title or "")
    m = NUM_PAT.search(t)
    if not m:
        return None
    return int(next(g for g in m.groups() if g))


def isbn_core(i13: str) -> int:
    return int(i13[3:12])


def core_to_isbn13(core: int) -> str:
    body = "978" + str(core).zfill(9)
    s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(body))
    return body + str((10 - s % 10) % 10)


def main() -> None:
    tm = json.load(io.open(ROOT / ".cache" / "isbn-title-map.json", encoding="utf-8"))
    # 楽天逆引き index: (正規化題, 巻) -> [isbn,...]
    rev: dict = {}
    for isbn, title in tm.items():
        v = rak_vol(title)
        if v is None:
            continue
        # 巻番号表記より前を題部分とみなす
        t = unicodedata.normalize("NFKC", title)
        m = NUM_PAT.search(t)
        base = norm_title(t[: m.start()])
        if base:
            rev.setdefault((base, v), []).append(isbn)
    print(f"楽天逆引きindex: {len(rev):,} (題,巻)キー", file=sys.stderr)

    canonical_slugs = {Path(f).stem for f in glob.glob(str(ROOT / "data" / "seeds" / "edition-canonical" / "*.yml"))}

    # 本番の全使用済みISBN
    used: set = set()
    pages = []
    for f in glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")):
        try:
            y = yaml.safe_load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        if not y:
            continue
        pages.append((Path(f).stem, y))
        for ed in y.get("editions") or []:
            for v in ed.get("volumes") or []:
                if v.get("isbn13"):
                    used.add(str(v["isbn13"]))
    print(f"頁 {len(pages):,} / 使用済みISBN {len(used):,}", file=sys.stderr)

    fills: dict = {}
    regen_stems: set = set()
    unresolved = []
    stats = Counter()

    for stem, y in pages:
        title_n = norm_title(y.get("title") or "")
        for ed in y.get("editions") or []:
            vols = ed.get("volumes") or []
            if len(vols) < 2:
                continue
            known = {v["number"]: str(v["isbn13"]) for v in vols if v.get("isbn13") and v.get("number")}
            lack = [v["number"] for v in vols if not v.get("isbn13") and v.get("number")]
            if not known or not lack:
                continue
            stats["対象edition"] += 1
            # 帯多数派(出版者帯≒ISBN13先頭8桁)
            band = Counter(i[:8] for i in known.values()).most_common(1)[0][0]
            # 線形判定
            pairs = sorted((n, isbn_core(i)) for n, i in known.items())
            diffs = {c - n for n, c in pairs}
            global_linear = len(diffs) == 1
            for n in sorted(lack):
                stats["欠け巻"] += 1
                if stem in canonical_slugs:
                    unresolved.append((stem, ed.get("type"), n, "canonical結線頁=fill無効(canonical本体へ)", ""))
                    stats["canonical除外"] += 1
                    continue
                cands = []
                # 経路1: 内挿/外挿
                below = [(k, c) for k, c in pairs if k < n]
                above = [(k, c) for k, c in pairs if k > n]
                if below and above:
                    k1, c1 = below[-1]
                    k2, c2 = above[0]
                    if c2 - c1 == k2 - k1:
                        cands.append(("内挿", core_to_isbn13(c1 + (n - k1))))
                elif global_linear:
                    cands.append(("外挿", core_to_isbn13(next(iter(diffs)) + n)))
                # 経路2: 楽天逆引き(一意のみ)
                hit = rev.get((title_n, n)) or []
                if len(hit) == 1:
                    cands.append(("楽天逆引き", hit[0]))
                # 検証
                chosen = None
                for method, cand in cands:
                    rt = tm.get(cand)
                    if not rt:
                        continue
                    if cand[:8] != band:
                        continue
                    if cand in used:
                        continue
                    rtn, rv = norm_title(re.sub(NUM_PAT, "", unicodedata.normalize("NFKC", rt))), rak_vol(rt)
                    if rv != n:
                        continue
                    if not (title_n and (title_n in rtn or rtn in title_n)):
                        continue
                    chosen = (method, cand, rt)
                    break
                if chosen:
                    method, cand, rt = chosen
                    _fillkey = y.get("slug") or stem  # ★キー=公開slug(SRC stemは死にキー)
                    regen_stems.add(stem)
                    fills.setdefault(_fillkey, []).append({
                        "edition": ed.get("type"), "number": n, "isbn13": cand,
                        "source": f"partial-isbn-gap {method}+楽天題『{rt}』 2026-08-19",
                    })
                    used.add(cand)
                    stats[f"確定:{method}"] += 1
                else:
                    why = []
                    if not cands:
                        why.append("候補生成不能(帯非線形+楽天逆引き無し)")
                    else:
                        why.append("検証不通過(" + "/".join(m for m, _ in cands) + ")")
                    unresolved.append((stem, ed.get("type"), n, ";".join(why),
                                       ",".join(c for _, c in cands)))
                    stats["未解決"] += 1

    print("=== stats ===", dict(stats))
    print(f"確定 {sum(len(v) for v in fills.values())}巻 / {len(fills)}頁, 未解決 {len(unresolved)}巻")

    out_un = ROOT / "docs" / "production-diagnostics" / "partial-isbn-gap-unresolved.tsv"
    with io.open(out_un, "w", encoding="utf-8", newline="\n") as w:
        w.write("slug\tedition\t巻\t理由\t候補\n")
        for r in sorted(unresolved):
            w.write("\t".join(str(x) for x in r) + "\n")
    print("unresolved TSV:", out_un)

    if not APPLY:
        # dry-run サンプル表示
        for stem in list(fills)[:8]:
            print(" 例:", stem, fills[stem][:2])
        print("(dry-run。--apply で isbn-fill.json へ追記)")
        return

    p = ROOT / "data" / "seeds" / "isbn-fill.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    added = 0
    for stem, lst in fills.items():
        cur = d.setdefault(stem, [])
        have = {(e["edition"], e["number"]) for e in cur}
        for e in lst:
            if (e["edition"], e["number"]) in have:
                continue
            cur.append(e)
            added += 1
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, ensure_ascii=False, indent=1))
    print(f"isbn-fill.json += {added}巻 / {len(fills)}頁")
    regen = ROOT / ".cache" / "isbn-gap-regen-list.txt"
    io.open(regen, "w", encoding="utf-8", newline="\n").write("\n".join(sorted(regen_stems)))
    print("regen list(SRC stems):", regen)


if __name__ == "__main__":
    main()
