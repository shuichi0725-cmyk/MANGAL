#!/usr/bin/env python3
"""画集フリガナ補正候補 生成 (= NDL公式ヨミ ground-truth、 漫画と同手法)。

画集は漫画の NDLフリガナ監査を通っていない → title_kana が空/誤/latin生混入。
本スクリプトは art-books.yml の各画集 series を NDL(ISBN照合)で照合し、 補正候補を出す。
★生成のみ。 適用 (furigana-corrections.yml への純粋追加) は人手確認後。

提案条件 (= 慎重側、 誤上書き回避):
  - current(種2 kana)が空            → NDL があれば fill 候補 (NEED_FILL)
  - current に latin 生混入           → NDL があれば差し替え候補 (LATIN_MIX)
  - current ≠ NDL かつ title token 共有 → 不一致候補 (MISMATCH。 NDLがへうげ型誤りも
                                          あるので人が裁定)
  - current == NDL or NDL無           → 提案しない (OK / NO_NDL)

出力: .cache/artbook-furigana-proposed.tsv (= 人手レビュー用)
NDL応答は .cache/ndl-yomi-cache.json に共有蓄積 (= 監査と同じ、 resumable)。
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
    sys.argv = ["x"]  # promote の argv 解析を無害化
    spec.loader.exec_module(m)
    return m


pb = _load("pb", "_promote-bulk-v2.py")
fa = _load("fa", "_furigana-audit.py")  # NDL helpers 流用

OUT = ROOT / ".cache" / "artbook-furigana-proposed.tsv"


def has_latin(s: str) -> bool:
    return bool(re.search(r"[A-Za-z]", s or ""))


def main() -> int:
    con = sqlite3.connect(pb.DB)
    con.row_factory = sqlite3.Row
    art_books = pb.load_art_books()
    key2sid = {sk: sid for sid, sk in con.execute("SELECT id, series_key FROM series")}
    cache = fa.load_ndl_cache()

    rows = []
    n = 0
    for sk, meta in sorted(art_books.items()):
        sid = key2sid.get(sk)
        if sid is None:
            continue
        srow = con.execute("SELECT title, title_kana FROM series WHERE id=?", (sid,)).fetchone()
        title = srow["title"] or ""
        cur = re.sub(r"[\s　]+", "", srow["title_kana"] or "")  # 種2 kana (promote と同じ正規化)
        isbn = fa.rep_isbn(con, sid)
        nd = fa.clean_ndl(fa.ndl_yomi(isbn, cache)) if isbn else None
        nd_nospace = re.sub(r"[\s　]+", "", nd) if nd else None
        n += 1
        if n % 20 == 0:
            print(f"  ...{n} 件 NDL照合 (cache {len(cache)})", file=sys.stderr)

        # 判定
        if not cur and nd_nospace:
            tier = "1-NEED_FILL"
        elif cur and has_latin(cur) and nd_nospace and not has_latin(nd_nospace):
            tier = "2-LATIN_MIX"
        elif cur and nd_nospace and cur != nd_nospace and fa.shares_title(nd, title):
            tier = "3-MISMATCH"
        elif not cur and not nd_nospace:
            tier = "8-NO_KANA_NO_NDL"   # 空のまま (= NDLにも無、 別途手当)
        else:
            tier = "9-OK"
        rows.append({
            "tier": tier, "artist": meta.get("artist") or "", "title": title,
            "cur_kana": cur, "ndl_kana": nd or "", "ndl_seg": nd or "",
            "isbn": isbn or "", "key": sk,
        })

    # cache 保存 (= 次回 resumable)
    import json
    json.dump(cache, fa.NDL_CACHE.open("w", encoding="utf-8"), ensure_ascii=False)

    rows.sort(key=lambda r: (r["tier"], r["artist"]))
    hdr = ["tier", "artist", "title", "cur_kana", "ndl_kana", "isbn", "key"]
    with OUT.open("w", encoding="utf-8") as f:
        f.write("\t".join(hdr) + "\n")
        for r in rows:
            f.write("\t".join(str(r[h]) for h in hdr) + "\n")

    from collections import Counter
    cnt = Counter(r["tier"] for r in rows)
    print(f"\n=== 画集フリガナ監査: {len(rows)} 件 ===", file=sys.stderr)
    for t in sorted(cnt):
        print(f"  {t}: {cnt[t]}", file=sys.stderr)
    print(f"\n提案TSV: {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
