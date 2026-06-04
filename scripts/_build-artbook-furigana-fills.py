#!/usr/bin/env python3
"""画集フリガナ fill 候補を clean/flagged に分類 (= NDL盲目適用を避ける、 慎重側)。

NEED_FILL(現kana空)のうち、 NDLヨミが信頼できる物だけ clean とし furigana-corrections
追加候補に。 latin残/部分転記(「集」なのにシュウ無)は flagged=人手。
MISMATCH(現kana有 ≠ NDL)は ★既存が正のことが多い(風の聖痕=スティグマ等)→ 触らない=報告のみ。

出力:
  .cache/artbook-furigana-fills.yml   = clean な corrections 追加候補(純粋追加用)
  .cache/artbook-furigana-flagged.tsv = 人手要(latin/部分/NDL無)
"""
import importlib.util
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, ROOT / "scripts" / path)
    m = importlib.util.module_from_spec(spec)
    sys.argv = ["x"]
    spec.loader.exec_module(m)
    return m


pb = _load("pb", "_promote-bulk-v2.py")
fa = _load("fa", "_furigana-audit.py")

FILLS = ROOT / ".cache" / "artbook-furigana-fills.yml"
FLAGGED = ROOT / ".cache" / "artbook-furigana-flagged.tsv"


def has_latin(s):
    return bool(re.search(r"[A-Za-z]", s or ""))


def main():
    con = sqlite3.connect(pb.DB)
    con.row_factory = sqlite3.Row
    art_books = pb.load_art_books()
    key2sid = {sk: sid for sid, sk in con.execute("SELECT id, series_key FROM series")}
    cache = fa.load_ndl_cache()

    clean, flagged = [], []
    for sk, meta in sorted(art_books.items()):
        sid = key2sid.get(sk)
        if sid is None:
            continue
        srow = con.execute("SELECT title, title_kana FROM series WHERE id=?", (sid,)).fetchone()
        title = srow["title"] or ""
        cur = re.sub(r"[\s　]+", "", srow["title_kana"] or "")
        if cur:
            continue  # 現kana有 = 対象外(MISMATCHは別途・既存維持)
        isbn = fa.rep_isbn(con, sid)
        nd = fa.clean_ndl(fa.ndl_yomi(isbn, cache)) if isbn else None
        nd_ns = re.sub(r"[\s　]+", "", nd) if nd else ""
        # 分類
        reason = None
        if not nd_ns:
            reason = "NDL無"
        elif has_latin(nd_ns):
            reason = "latin残"
        elif "集" in title and "シュウ" not in nd_ns:
            reason = "部分転記(集→シュウ欠落)"
        if reason:
            flagged.append((reason, meta.get("artist") or "", title, nd or "", sk))
        else:
            clean.append((meta.get("artist") or "", title, nd_ns, nd or "", sk))

    # clean → corrections yaml fragment(純粋追加用)
    import yaml
    entries = []
    for artist, title, kana_ns, kana_seg, sk in clean:
        entries.append({
            "key": sk, "title": title,
            "title_kana": kana_ns,
            "title_kana_segmented": kana_seg,
            "source": "ndl", "note": "artbook-furigana-fill",
        })
    with FILLS.open("w", encoding="utf-8") as f:
        yaml.dump({"corrections": entries}, f, allow_unicode=True, sort_keys=False)

    with FLAGGED.open("w", encoding="utf-8") as f:
        f.write("reason\tartist\ttitle\tndl\tkey\n")
        for r in sorted(flagged):
            f.write("\t".join(r) + "\n")

    print(f"clean fill(採用候補): {len(clean)}", file=sys.stderr)
    print(f"flagged(人手要): {len(flagged)}", file=sys.stderr)
    print(f"  → {FILLS}", file=sys.stderr)
    print(f"  → {FLAGGED}", file=sys.stderr)


if __name__ == "__main__":
    main()
