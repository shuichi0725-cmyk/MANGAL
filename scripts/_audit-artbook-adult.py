#!/usr/bin/env python3
"""画集 adult 監査 (= 設計 §4)。

art-books.yml の作画家を多層 signal で照合し、 成人疑いを「疑わしい順」に並べた
レビュー用リストを出力する。 ★自動 flag のみ。 確定は人手 (= 203件は現実的)。

signals:
  1. already_adult      : 既に adult: true (= 確定済)
  2. known_mangaka      : artist ∈ adult_mangaka_known (Wikipedia 成人作家一覧 2035件)
  3. artist_max_score   : その作画家の他作品の adult_score 最大 (= 種2 sqlite 必要。
                          db.sqlite が空ならスキップし None)
  4. title_marker       : 画集 title に成人 marker (艶/官能/淫… )。 ★単独では誤爆する
                          ので known_mangaka との AND を strong とし、 marker 単独は weak。

出力: .cache/artbook-adult-review.tsv (= 監査 artifact、 commit しない)
      + stdout に tier 別サマリ。

★このスクリプトは art-books.yml を変更しない (= read-only 監査)。
  確定後の adult: true 付与は人手レビューを経て純粋追加で行う。
"""
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ART_BOOKS = ROOT / "data" / "seeds" / "art-books.yml"
ADULT_CACHE = ROOT / "data" / "seeds" / "adult-wikipedia-cache.yml"
DB = ROOT / ".cache" / "db-v2.sqlite"  # ★派生DB (= adult_score 有。 旧db.sqliteは空)
OUT = ROOT / ".cache" / "artbook-adult-review.tsv"

# 成人 title marker (= 設計 §4-2)。 「艶」等は一般題にもあるので marker 単独は weak tier。
TITLE_MARKERS = [
    "艶", "官能", "エロ", "成人", "SM", "緊縛", "淫", "熟女", "痴漢", "陵辱",
    "BL", "やおい", "ボーイズラブ", "アダルト", "18禁", "性", "ハーレム",
]


def norm_name(s: str) -> str:
    """作家名の正規化: 曖昧回避括弧「(漫画家)」等と wiki markup ノイズを除去。"""
    if not s:
        return ""
    s = s.strip()
    # 末尾の曖昧回避括弧 (= 「A10(漫画家)」→「A10」) を除去
    for suf in ("(漫画家)", "（漫画家）"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    # wiki markup ノイズ
    s = s.replace("<!--", "").replace("<!", "").strip()
    return s


def parse_series_key(key: str) -> tuple[str | None, str]:
    """'qid:Q123|name:タイトル' → (qid, name)。"""
    qid = None
    name = ""
    for part in key.split("|"):
        if part.startswith("qid:"):
            qid = part[4:]
        elif part.startswith("name:"):
            name = part[5:]
    return qid, name


def load_known_mangaka() -> set[str]:
    d = yaml.safe_load(ADULT_CACHE.read_text(encoding="utf-8"))
    out = set()
    for item in d.get("adult_mangaka_known", []):
        nm = norm_name(item.get("name", ""))
        if nm:
            out.add(nm)
    return out


def load_artist_max_score() -> dict[str, int] | None:
    """qid -> その作家(qid)が紐づく series の adult_score 最大。 db 空なら None。"""
    if not DB.exists() or DB.stat().st_size == 0:
        return None
    con = sqlite3.connect(str(DB))
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "series" not in tables:
        con.close()
        return None
    cols = {r[1] for r in con.execute("PRAGMA table_info(series)")}
    if not {"qid", "adult_score"} <= cols:
        con.close()
        return None
    out: dict[str, int] = {}
    for qid, score in con.execute(
        "SELECT qid, MAX(COALESCE(adult_score,0)) FROM series WHERE qid IS NOT NULL GROUP BY qid"
    ):
        out[qid] = int(score or 0)
    con.close()
    return out


def main() -> int:
    data = yaml.safe_load(ART_BOOKS.read_text(encoding="utf-8"))
    entries = data.get("art_books", [])
    known = load_known_mangaka()
    qid_score = load_artist_max_score()

    rows = []
    for e in entries:
        key = e.get("series_key", "")
        qid, name = parse_series_key(key)
        artist = e.get("artist") or ""
        already = bool(e.get("adult"))
        multi = bool(e.get("multi_artist"))

        sig_known = norm_name(artist) in known
        markers = [m for m in TITLE_MARKERS if m in name]
        sig_marker = bool(markers)
        # qid は種2では「作者QID」だが art-books.yml の qid は series_key 由来 (= 作品系)。
        # ここでは参考値として series 群の最大 score を引く (= db ある時のみ)。
        max_score = qid_score.get(qid) if (qid_score is not None and qid) else None

        # tier 判定 (= 疑わしい順)
        if already:
            tier = "0-CONFIRMED"
        elif sig_known and sig_marker:
            tier = "1-STRONG"          # 既知成人作家 AND title marker
        elif sig_known:
            tier = "2-KNOWN_MANGAKA"   # 既知成人作家
        elif max_score is not None and max_score >= 3:
            tier = "3-ARTIST_SCORE"    # 他作品が成人 (db 必要)
        elif sig_marker:
            tier = "4-MARKER_ONLY"     # marker 単独 (= 誤爆注意 / weak)
        else:
            tier = "9-CLEAN"

        rows.append({
            "tier": tier, "artist": artist, "name": name, "qid": qid or "",
            "already": "Y" if already else "",
            "known": "Y" if sig_known else "",
            "markers": "/".join(markers),
            "max_score": "" if max_score is None else str(max_score),
            "multi": "Y" if multi else "",
        })

    rows.sort(key=lambda r: (r["tier"], r["artist"]))

    hdr = ["tier", "artist", "name", "qid", "already", "known", "markers", "max_score", "multi"]
    with OUT.open("w", encoding="utf-8") as f:
        f.write("\t".join(hdr) + "\n")
        for r in rows:
            f.write("\t".join(r[h] for h in hdr) + "\n")

    # サマリ
    from collections import Counter
    cnt = Counter(r["tier"] for r in rows)
    print(f"=== 画集 adult 監査: {len(rows)} 件 ===")
    print(f"種2 sqlite: {'有効' if qid_score is not None else '★空/不在 → artist_score signal スキップ'}")
    print(f"adult_mangaka_known: {len(known)} 名")
    print()
    for t in sorted(cnt):
        print(f"  {t}: {cnt[t]} 件")
    print()
    print("=== 人手確認すべき候補 (tier 1-4、 CLEAN 除く) ===")
    for r in rows:
        if r["tier"] == "9-CLEAN" or r["tier"] == "0-CONFIRMED":
            continue
        flags = []
        if r["known"]:
            flags.append("known成人作家")
        if r["markers"]:
            flags.append(f"marker:{r['markers']}")
        if r["max_score"]:
            flags.append(f"他作score:{r['max_score']}")
        print(f"  [{r['tier']}] {r['artist']} / {r['name']}  ({', '.join(flags)})")
    print()
    print(f"全件 TSV: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
