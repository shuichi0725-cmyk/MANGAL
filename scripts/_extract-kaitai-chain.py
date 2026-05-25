"""metadata101.json から 改題 chain を 抽出 + 種2 sqlite と マッチング。

抽出 pattern:
  「<旧 series 名>」の改題、巻次を継承  ← 強 chain (= 安全に merge 候補)
  「<旧 series 名>」の改題                ← 弱 chain (= 別物の可能性あり、 別出力)

種2 sqlite と照合:
  - 旧 series 名 と 新 series 名 (= 当該 MangaBook の schema:name) を
    `series.title` で lookup
  - 両方 hit したら series_id ペアを 出力

出力:
  .cache/kaitai-chain-strong.csv  = 巻次継承あり (= merge 推奨候補)
  .cache/kaitai-chain-weak.csv    = 巻次継承なし (= 別物の可能性、 目視確認用)
"""
from __future__ import annotations
import csv
import re
import sqlite3
from pathlib import Path

SRC = Path(".cache/madb/metadata101.json")
DB = Path(".cache/db-v2.sqlite")
OUT_STRONG = Path(".cache/kaitai-chain-strong.csv")
OUT_WEAK = Path(".cache/kaitai-chain-weak.csv")

# 「○○」の改題、巻次を継承
STRONG_RE = re.compile(r"「([^」]+?)」の改題.{0,15}(?:巻次|巻号|巻次を継承|巻号を継承|巻次引き継ぎ)")
# 「○○」の改題 (= 巻次継承なし)
ANY_RE = re.compile(r"「([^」]+?)」の改題")
# 当該 MangaBook の title 抽出 (= schema:name の 1 個目 = 日本語名)
# JSON-LD では schema:name = list の場合あり (= ja + ja-hrkt)、 当面は schema:name 行末の 値を 取る
# pattern (簡易): "schema:name": "<title>"
NAME_INLINE_RE = re.compile(r'"schema:name":\s*"([^"]+)"')
# list の場合 1 行目に `"schema:name": [` が来て 2 行目に "<title>"
NAME_LIST_START_RE = re.compile(r'"schema:name":\s*\[')
ID_RE = re.compile(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(M\d+)"')


def extract_pairs():
    """metadata101.json を 行 stream 解析。 各 entity の (madb_id, name, ma:note) を抽出。"""
    cur_id: str | None = None
    cur_name: str | None = None
    cur_notes: list[str] = []
    in_name_list = False

    pairs_strong: list[tuple[str, str, str, str]] = []  # (madb_id, new_name, old_name, note)
    pairs_weak: list[tuple[str, str, str, str]] = []

    def flush():
        nonlocal cur_id, cur_name, cur_notes
        if cur_id and cur_name and cur_notes:
            for note in cur_notes:
                m = STRONG_RE.search(note)
                if m:
                    pairs_strong.append((cur_id, cur_name, m.group(1), note))
                    continue
                m2 = ANY_RE.search(note)
                if m2:
                    pairs_weak.append((cur_id, cur_name, m2.group(1), note))
        cur_id = None
        cur_name = None
        cur_notes = []

    with SRC.open("r", encoding="utf-8") as f:
        for line in f:
            m_id = ID_RE.search(line)
            if m_id:
                # 新 entity 開始 = 直前の entity flush
                flush()
                cur_id = m_id.group(1)
                in_name_list = False
                continue
            if cur_name is None:
                m_n = NAME_INLINE_RE.search(line)
                if m_n:
                    cur_name = m_n.group(1)
                elif NAME_LIST_START_RE.search(line):
                    in_name_list = True
                    continue
                elif in_name_list:
                    # list 内の最初の 単純文字列値 (= "..." で囲まれた値) = 日本語 title
                    s = line.strip().rstrip(",")
                    if s.startswith('"') and s.endswith('"') and "@" not in s:
                        cur_name = s[1:-1]
                        in_name_list = False
            if '"ma:note"' in line:
                # 値抽出: "ma:note": "<...>"  もしくは 複数行 = 当面 単行のみ対象
                m_v = re.search(r'"ma:note":\s*"([^"]+)"', line)
                if m_v:
                    cur_notes.append(m_v.group(1))
    flush()
    return pairs_strong, pairs_weak


def lookup_in_db(pairs):
    """series.title で 新名 + 旧名 を 検索、 両方 hit したペアだけ 返す。"""
    if not DB.exists():
        return []
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    results = []
    for madb_id, new_name, old_name, note in pairs:
        new_rows = con.execute(
            "SELECT id, qid, title FROM series WHERE title=? LIMIT 5",
            (new_name,),
        ).fetchall()
        old_rows = con.execute(
            "SELECT id, qid, title FROM series WHERE title=? LIMIT 5",
            (old_name,),
        ).fetchall()
        if not new_rows or not old_rows:
            continue
        results.append({
            "madb_id": madb_id,
            "new_name": new_name,
            "old_name": old_name,
            "new_series_ids": ",".join(str(r["id"]) for r in new_rows),
            "old_series_ids": ",".join(str(r["id"]) for r in old_rows),
            "new_qid": new_rows[0]["qid"] or "",
            "old_qid": old_rows[0]["qid"] or "",
            "note": note[:200],
        })
    return results


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("(no rows)\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    print(f"[1/3] parsing {SRC}...")
    strong, weak = extract_pairs()
    print(f"  raw extract: strong={len(strong):,}, weak={len(weak):,}")

    print(f"[2/3] DB matching against {DB}...")
    strong_matched = lookup_in_db(strong)
    weak_matched = lookup_in_db(weak)
    print(f"  matched both ends: strong={len(strong_matched):,}, weak={len(weak_matched):,}")

    print(f"[3/3] writing csv...")
    write_csv(OUT_STRONG, strong_matched)
    write_csv(OUT_WEAK, weak_matched)
    print(f"  {OUT_STRONG}")
    print(f"  {OUT_WEAK}")

    # 先頭 sample を console にも出す
    print("\n=== strong sample (= 巻次継承 = merge 候補) ===")
    for r in strong_matched[:15]:
        print(f"  {r['madb_id']}: '{r['old_name']}' (= sid:{r['old_series_ids']}) "
              f"→ '{r['new_name']}' (= sid:{r['new_series_ids']})")


if __name__ == "__main__":
    main()
