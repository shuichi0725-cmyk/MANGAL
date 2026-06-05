#!/usr/bin/env python3
"""画集の分かち書きフリガナ(title_kana_segmented)を NDLキャッシュから抽出 (= 再取得なし)。

★NDL は既に furigana 監査で叩き、 応答(スペース付き transcription)を
  .cache/ndl-yomi-cache.json に保存済 → 再度叩かずに分かち書きを取り出す。
★整合性ガード: スペース除去した NDL 読み == 画集の確定 title_kana の時のみ採用
  (= NDL が別読み/部分の時は採らない。 表示kanaと矛盾しない分だけ)。
出力: data/seeds/art-book-furigana-segmented.yml (= git追跡 seed、 {series_key: segmented})。
"""
import importlib.util
import json
import re
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
NDL_CACHE = ROOT / ".cache" / "ndl-yomi-cache.json"
OUT = ROOT / "data" / "seeds" / "art-book-furigana-segmented.yml"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
    m = importlib.util.module_from_spec(spec)
    sys.argv = ["x"]
    spec.loader.exec_module(m)
    return m


def nospace(s):
    return re.sub(r"[\s　]+", "", s or "")


def norm_spaces(s):
    return re.sub(r"[\s　]+", " ", (s or "").strip())


def main():
    pb = _load("pb", "_promote-bulk-v2.py")
    fa = _load("fa", "_furigana-audit.py")  # clean_ndl
    con = sqlite3.connect(pb.DB)
    con.row_factory = sqlite3.Row
    art_books = pb.load_art_books()
    key2sid = {sk: sid for sid, sk in con.execute("SELECT id, series_key FROM series")}
    merge_groups = pb.get_merge_sids(con)
    cache = json.loads(NDL_CACHE.read_text(encoding="utf-8")) if NDL_CACHE.exists() else {}
    corr = pb.load_furigana_corrections()

    out = {}
    stats = {"adopted_ndl": 0, "adopted_corr": 0, "mismatch": 0, "no_ndl": 0, "no_isbn": 0}
    for sk, meta in sorted(art_books.items()):
        sid = key2sid.get(sk)
        if sid is None:
            continue
        srow = con.execute("SELECT title_kana FROM series WHERE id=?", (sid,)).fetchone()
        c = corr.get(sk) or {}
        # 確定 title_kana (= promote と同じ優先・スペース除去)
        raw = meta.get("title_kana") or c.get("title_kana") or (srow["title_kana"] if srow else "") or ""
        final_kana = nospace(raw)
        if not final_kana:
            continue
        # ① furigana-corrections に segmented があればそれを最優先 (= 既裁定)
        seg_corr = c.get("title_kana_segmented")
        if seg_corr and nospace(seg_corr) == final_kana:
            out[sk] = norm_spaces(seg_corr)
            stats["adopted_corr"] += 1
            continue
        # ② NDL キャッシュの spaced transcription。 ★build_artbook と同じく merge group の
        #    出力巻ISBNで引く(単一sidのrep_isbnだとgroup-mate由来ISBNを取りこぼす)。
        group = merge_groups.get(sid, [sid])
        eds = pb.get_editions_with_volumes(con, group)
        isbns = [str(v.get("isbn13")) for e in eds for v in e["volumes"] if v.get("isbn13")]
        if not isbns:
            stats["no_isbn"] += 1
            continue
        raw_ndl = None
        for ib in isbns:
            raw_ndl = cache.get(ib) or cache.get(re.sub(r"[^0-9]", "", ib))
            if raw_ndl:
                break
        if not raw_ndl:
            stats["no_ndl"] += 1
            continue
        seg = norm_spaces(fa.clean_ndl(raw_ndl))
        # 整合性: スペース除去が確定kanaと一致 + スペースが実際に在る(分かち書きの意味がある)
        if nospace(seg) == final_kana and " " in seg:
            out[sk] = seg
            stats["adopted_ndl"] += 1
        else:
            stats["mismatch"] += 1

    OUT.write_text(
        "# 画集の分かち書きフリガナ (= slug生成用 title_kana_segmented)。\n"
        "# NDLキャッシュの spaced transcription から抽出 (整合ガード: nospace==確定title_kana)。\n"
        "# scripts/_extract-artbook-segmented.py。 build_artbook が読込。\n"
        + yaml.dump({"segmented": out}, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )
    print(f"抽出 {len(out)} 件 → {OUT}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
