"""metadata101.json から 改題 chain を 抽出 + 種2 sqlite と マッチング。

★ v2 = 安全側 pattern 拡張 (= A + C + D)

拡張点:
A. strong pattern variation 追加 (= 「巻次/巻号 を 継承/引き継ぐ/引き継ぎ/継続」)
   + 二重カギ括弧 『』 対応
   + ma:note の list 形式対応 (= 続き行も拾う)
   + schema:description も対象に追加 (= 同 strong pattern のみ、 危険 keyword exclude)
D. 「改題」 直後 30 文字 に 危険 keyword (= 合本/外伝/抜粋/再構成/加筆/セレクション/続編)
   含む match は **strong から弾く** (= 巻番衝突 / 別シリーズリスク 回避)

出力:
  .cache/kaitai-chain-strong.csv  = 安全に merge できる候補 (= 自動採用想定)
  .cache/kaitai-chain-weak.csv    = 「改題」 のみ patternの 全件 (= 手動 review 用)

注意: 種2 sqlite は **不変** (C 原則)。 これは audit script + 本番 yml 生成時
の lookup 用 mapping source。
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

# 「○○」の改題、 + 巻次/巻号 + を + 継承/引き継ぐ/引き継ぎ/継続
STRONG_RE = re.compile(
    r"[「『]([^」』]+?)[」』]の改題.{0,20}(?:巻次|巻号)(?:を)?(?:継承|引き継ぐ|引き継ぎ|継続)"
)
ANY_RE = re.compile(r"[「『]([^」』]+?)[」』]の改題")

# strong から弾く 危険 keyword (= 改題 直後 30 文字以内に 含まれたら不採用)
DANGER_KEYWORDS = [
    "合本", "外伝", "抜粋", "再構成", "加筆", "セレクション",
    "続編", "続巻", "別冊", "総集編", "ベスト版", "復刻"
]

NAME_INLINE_RE = re.compile(r'"schema:name":\s*"([^"]+)"')
NAME_LIST_START_RE = re.compile(r'"schema:name":\s*\[')
NOTE_INLINE_RE = re.compile(r'"ma:note":\s*"([^"]+)"')
NOTE_LIST_START_RE = re.compile(r'"ma:note":\s*\[')
DESC_INLINE_RE = re.compile(r'"schema:description":\s*"([^"]+)"')
ID_RE = re.compile(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(M\d+)"')
# list 内の単純文字列値 (= "..." ja のみ)
SIMPLE_STR_RE = re.compile(r'^\s*"([^"]+)"\s*,?\s*$')


def is_safe(note: str, m: re.Match) -> bool:
    """match の 直後 30 文字 に 危険 keyword 含まれるか チェック。"""
    after = note[m.end(): m.end() + 30]
    for kw in DANGER_KEYWORDS:
        if kw in after:
            return False
    return True


def extract_pairs():
    """metadata101.json を 行 stream 解析。"""
    cur_id: str | None = None
    cur_name: str | None = None
    cur_notes: list[str] = []
    cur_descs: list[str] = []
    in_name_list = False
    in_note_list = False

    pairs_strong: list[tuple[str, str, str, str, str]] = []  # id, new, old, note, src
    pairs_weak: list[tuple[str, str, str, str, str]] = []

    def add_strong(text: str, src: str):
        for m in STRONG_RE.finditer(text):
            if is_safe(text, m):
                pairs_strong.append((cur_id, cur_name, m.group(1), text[:300], src))

    def add_weak(text: str, src: str):
        for m in ANY_RE.finditer(text):
            # strong に該当する match は 既に 集計済 → ここでは strong に該当しないものだけ
            sm = STRONG_RE.search(text, m.start(), m.start() + 200)
            if sm and sm.start() == m.start():
                continue
            pairs_weak.append((cur_id, cur_name, m.group(1), text[:300], src))

    def flush():
        nonlocal cur_id, cur_name, cur_notes, cur_descs
        if cur_id and cur_name:
            for note in cur_notes:
                add_strong(note, "ma:note")
                add_weak(note, "ma:note")
            for desc in cur_descs:
                add_strong(desc, "schema:description")
                add_weak(desc, "schema:description")
        cur_id = None
        cur_name = None
        cur_notes = []
        cur_descs = []

    with SRC.open("r", encoding="utf-8") as f:
        for line in f:
            m_id = ID_RE.search(line)
            if m_id:
                flush()
                cur_id = m_id.group(1)
                in_name_list = False
                in_note_list = False
                continue

            # ma:note の list 形式 続き行 対応
            if in_note_list:
                m_s = SIMPLE_STR_RE.match(line)
                if m_s and "@" not in m_s.group(1):
                    cur_notes.append(m_s.group(1))
                    continue
                if "]" in line:
                    in_note_list = False
                    continue

            # name list 形式 続き行
            if in_name_list and cur_name is None:
                m_s = SIMPLE_STR_RE.match(line)
                if m_s and "@" not in m_s.group(1):
                    cur_name = m_s.group(1)
                    in_name_list = False
                    continue
                if "]" in line:
                    in_name_list = False
                    continue

            if cur_name is None:
                m_n = NOTE_INLINE_RE.search(line) and None
                m_n = NAME_INLINE_RE.search(line)
                if m_n:
                    cur_name = m_n.group(1)
                elif NAME_LIST_START_RE.search(line):
                    in_name_list = True
                    continue

            if '"ma:note"' in line:
                m_v = NOTE_INLINE_RE.search(line)
                if m_v:
                    cur_notes.append(m_v.group(1))
                elif NOTE_LIST_START_RE.search(line):
                    in_note_list = True
                    continue
            if '"schema:description"' in line:
                m_v = DESC_INLINE_RE.search(line)
                if m_v:
                    cur_descs.append(m_v.group(1))
    flush()
    return pairs_strong, pairs_weak


def lookup_in_db(pairs):
    """series.title で 新名 + 旧名 を 検索、 両方 hit したペアだけ 返す。"""
    if not DB.exists():
        return []
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    results = []
    seen = set()  # (new_name, old_name) で dedupe (= 同 chain 複数巻で 重複)
    for madb_id, new_name, old_name, note, src in pairs:
        key = (new_name, old_name)
        if key in seen:
            continue
        seen.add(key)
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
            "src_field": src,
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
    print(f"  matched both ends + deduped: strong={len(strong_matched):,}, weak={len(weak_matched):,}")

    print(f"[3/3] writing csv...")
    write_csv(OUT_STRONG, strong_matched)
    write_csv(OUT_WEAK, weak_matched)
    print(f"  {OUT_STRONG}")
    print(f"  {OUT_WEAK}")

    print("\n=== strong sample (= 自動採用候補) ===")
    for r in strong_matched[:30]:
        print(f"  {r['madb_id']} [{r['src_field']}]: "
              f"'{r['old_name']}' (= sid:{r['old_series_ids']}) "
              f"→ '{r['new_name']}' (= sid:{r['new_series_ids']})")


if __name__ == "__main__":
    main()
