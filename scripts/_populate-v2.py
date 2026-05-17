"""series-v2.json を db-v2.sqlite に投入する。

処理順:
  1. 各 cluster → series row 投入
  2. cluster の madb_records + books の brand を 集計し、 (type, imprint) ごとに
     editions row 投入
  3. books を 該当 edition に紐づけ、 volumes row 投入
     (= 同 (edition_id, number) で 複数 ISBN 可)
  4. adult_score 投入 (= cluster.is_adult なら 30)
"""

import json
import re
import sqlite3
import sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SERIES_V2 = ROOT / ".cache" / "series-v2.json"


# ----------- helpers -----------
def isbn10_to_isbn13(isbn10: str) -> str | None:
    digits = re.sub(r"[^0-9X]", "", isbn10.upper())
    if len(digits) != 10:
        return None
    base = "978" + digits[:9]
    total = 0
    for i, ch in enumerate(base):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    check = (10 - total % 10) % 10
    return base + str(check)


def normalize_isbn(isbn: str) -> str | None:
    if not isbn:
        return None
    s = re.sub(r"[^0-9X]", "", isbn.upper())
    if len(s) == 13:
        return s
    if len(s) == 10:
        return isbn10_to_isbn13(s)
    return None


def classify_edition_from_imprint(imprint: str) -> str:
    """既存 lib/edition.ts:classifyEditionFromImprint() の Python 移植。"""
    if not imprint:
        return "standard"
    t = imprint  # NFKC は重い、 ざっくり
    if re.search(r"TVアニメ|アニメ版", t):
        return "anime"
    if "ワイド版" in t:
        return "wideban"
    if re.search(r"文庫", t):
        return "bunkobon"
    if "愛蔵" in t:
        return "aizoban"
    if "完全" in t:
        return "kanzenban"
    if "新装" in t:
        return "shinsoban"
    if re.search(r"カバー新装|カバーリニューアル", t):
        return "renewal"
    # デラックス = 新装再編版 / 大判版 系 (= e.g. ジャンプ・コミックスデラックス)
    if "デラックス" in t or "DELUXE" in t.upper():
        return "shinsoban"
    return "standard"


EDITION_LABELS = {
    "standard": "通常版",
    "kanzenban": "完全版",
    "bunkobon": "文庫版",
    "shinsoban": "新装版",
    "aizoban": "愛蔵版",
    "wideban": "ワイド版",
    "renewal": "カバーリニューアル",
    "anime": "アニメ版",
    "other": "その他",
}


def normalize_imprint(s: str) -> str:
    """imprint 正規化: 中黒 / 全角空白 / 半角空白 を 全部除去。
    例: 'ジャンプ・コミックス' / 'ジャンプ コミックス' / 'ジャンプコミックス' → 同一扱い
    """
    if not s:
        return ""
    return s.replace("・", "").replace("　", "").replace(" ", "").strip()


KANJI_VOLUME_MAP = {
    "上": 1, "中": 2, "下": 3,
    "上巻": 1, "中巻": 2, "下巻": 3,
    "前": 1, "後": 2,
    "前編": 1, "後編": 2,
}

KANJI_DIGIT = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
               "六": 6, "七": 7, "八": 8, "九": 9,
               # 大字 (= 銀行記帳用)
               "壱": 1, "弐": 2, "参": 3, "肆": 4, "伍": 5,
               "陸": 6, "漆": 7, "捌": 8, "玖": 9}
KANJI_UNIT = {"十": 10, "百": 100, "千": 1000, "拾": 10}

# Roman numerals (= unicode 2160-2168 = Ⅰ-Ⅸ、 Ⅹ=2169)
ROMAN_MAP = {chr(0x2160 + i): i + 1 for i in range(20)}  # Ⅰ-ⅩⅨ → 1-20


def parse_kanji_number(s: str) -> int | None:
    """漢数字 string を int に。 例: '一'→1, '十'→10, '三十一'→31, '百二十三'→123。"""
    if not s:
        return None
    # 全文字が 漢数字系か確認
    if not all(c in KANJI_DIGIT or c in KANJI_UNIT for c in s):
        return None
    total = 0
    current_digit = 0  # 直前の数字 (= 0 なら 暗黙的 1)
    for c in s:
        if c in KANJI_DIGIT:
            current_digit = KANJI_DIGIT[c]
        else:
            # unit (十/百/千)
            unit = KANJI_UNIT[c]
            total += (current_digit if current_digit else 1) * unit
            current_digit = 0
    total += current_digit
    return total if total > 0 else None


def extract_volume_number(label: str, vol_field: str) -> tuple[int | None, str | None, bool]:
    """(number, volume_label, is_extra) を返す。

    rule:
      - vol_field が 純粋数字 → number = int、 volume_label = None
      - vol_field が KANJI_VOLUME_MAP に hit → number = map 値、 volume_label = 元
      - vol_field が '第<漢数字>巻' → 漢数字を int 化、 volume_label = 元
      - vol_field が 数字 含む → 数字抽出 → number、 volume_label = 元
      - vol_field 空 + label から 末尾数字 抽出 → number、 volume_label = None
      - extraction 不能 → number = None, is_extra = True
    """
    if vol_field:
        s = vol_field.strip()
        # 純粋数字
        if re.match(r"^\d+$", s):
            return int(s), None, False
        # KANJI_VOLUME_MAP (= 上/中/下 等)
        if s in KANJI_VOLUME_MAP:
            return KANJI_VOLUME_MAP[s], s, False
        # roman numeral (= 'Ⅰ', 'Ⅱ', etc.)
        if s in ROMAN_MAP:
            return ROMAN_MAP[s], s, False
        # 第<漢数字>巻 / 第<漢数字>集 / 第<漢数字>編 / 第<漢数字>部 / 巻<漢数字>
        m = re.match(r"^(?:第|巻)([〇零一二三四五六七八九十百千壱弐参肆伍陸漆捌玖拾]+)[巻集編卷部篇]?$", s)
        if m:
            n = parse_kanji_number(m.group(1))
            if n is not None:
                return n, s, False
        # 漢数字単独 (= '一', '二', '三十一' 等)
        if re.fullmatch(r"[〇零一二三四五六七八九十百千壱弐参肆伍陸漆捌玖拾]+", s):
            n = parse_kanji_number(s)
            if n is not None:
                return n, s, False
        # 数字含む (例: 'NO.27', 'vol.1', '第3巻', '上巻', '01')
        m = re.search(r"\d+", s)
        if m:
            return int(m.group()), s, False
        # 数字なし (= 特装版 / 外伝 / etc.)
        return None, s, True

    # vol_field 空 → label から
    if label:
        # 末尾 空白 + 数字
        m = re.search(r"\s+(\d{1,3})\s*$", label)
        if m:
            return int(m.group(1)), None, False
        # 末尾 () 内 数字 (例: 'ゴルゴ13(125)')
        m = re.search(r"[(（](\d{1,3})[)）]\s*$", label)
        if m:
            return int(m.group(1)), None, False
        # 末尾 漢数字
        m = re.search(r"([〇零一二三四五六七八九十百千壱弐参肆伍陸漆捌玖拾]+)$", label)
        if m:
            n = parse_kanji_number(m.group(1))
            if n is not None:
                return n, None, False

    return None, None, True


def main():
    print(f"loading {SERIES_V2} ...", file=sys.stderr)
    with SERIES_V2.open("r", encoding="utf-8") as f:
        v2 = json.load(f)
    clusters = v2["clusters"]
    print(f"  clusters: {len(clusters)}", file=sys.stderr)

    print(f"opening {DB} ...", file=sys.stderr)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    # 既存 series rows を 空にする (= 再 import で 重複防止)
    cur.execute("DELETE FROM volumes")
    cur.execute("DELETE FROM editions")
    cur.execute("DELETE FROM series_authors")
    cur.execute("DELETE FROM series")
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('series','editions','volumes')")
    db.commit()

    stats = {
        "series_inserted": 0,
        "editions_inserted": 0,
        "volumes_inserted": 0,
        "volumes_skip_no_isbn": 0,
        "volumes_skip_dup_isbn": 0,
        "volumes_extra": 0,
    }

    # mangaka qid → id (= series_authors 用)
    qid_to_mangaka_id: dict[str, int] = {}
    cur.execute("SELECT id, qid FROM mangaka")
    for r in cur.fetchall():
        qid_to_mangaka_id[r["qid"]] = r["id"]

    isbn_seen: set[str] = set()
    madb_book_seen: set[str] = set()

    for c in clusters:
        # 1. series row
        adult_score = 30 if c["is_adult"] else 0
        cur.execute(
            """INSERT INTO series (series_key, qid, source, title, subtitle,
                                    title_kana, subtitle_kana, title_official_en,
                                    adult_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                c["series_key"],
                c["qid"] or None,
                c["source"],
                c["title"],
                c["subtitle"] or None,
                c["title_kana"] or None,
                c["subtitle_kana"] or None,
                c["title_official_en"] or None,
                adult_score,
            ),
        )
        series_id = cur.lastrowid
        stats["series_inserted"] += 1

        # 2. series_authors (= qid 解決済の場合のみ)
        if c["qid"] and c["qid"] in qid_to_mangaka_id:
            cur.execute(
                """INSERT OR IGNORE INTO series_authors (series_id, mangaka_id, role)
                   VALUES (?, ?, ?)""",
                (series_id, qid_to_mangaka_id[c["qid"]], "writer_artist"),
            )

        # 3. editions: (type, imprint) で aggregate
        # imprint は books 由来を 優先 (= MADB 個別 record より 確度高い)、
        # books が 空なら madb_records 由来
        edition_map: dict[tuple[str, str], int] = {}  # (type, imprint) → edition_id

        def get_or_create_edition(brand: str) -> int | None:
            brand = brand or ""
            type_ = classify_edition_from_imprint(brand)
            label = EDITION_LABELS.get(type_, "通常版")
            # imprint は normalize した値で grouping key (= 中黒/空白 差異の編集 統合)
            norm_imprint = normalize_imprint(brand) or None
            imprint_display = brand or None
            key = (type_, norm_imprint or "")
            if key in edition_map:
                return edition_map[key]
            try:
                cur.execute(
                    """INSERT INTO editions (series_id, type, label, imprint)
                       VALUES (?, ?, ?, ?)""",
                    (series_id, type_, label, imprint_display),
                )
                eid = cur.lastrowid
                edition_map[key] = eid
                stats["editions_inserted"] += 1
                return eid
            except sqlite3.IntegrityError:
                # UNIQUE (series_id, type, imprint) 衝突
                # 既存 edition のうち normalize 一致するものを 検索
                cur.execute(
                    """SELECT id, imprint FROM editions WHERE series_id=? AND type=?""",
                    (series_id, type_),
                )
                for row in cur.fetchall():
                    if normalize_imprint(row["imprint"] or "") == (norm_imprint or ""):
                        edition_map[key] = row["id"]
                        return row["id"]
                return None

        # books が 空 (= madb104 cluster で book 紐づけ失敗) でも madb_records.brand で
        # edition だけは 1 つ作っておく (= 後で book 追加できるよう骨格用意)
        if not c["books"]:
            for r in c["madb_records"]:
                get_or_create_edition(r["brand"])

        # 4. volumes (= ISBN なしも 投入、 madb_book_id で uniqueness)
        for book in c["books"]:
            edition_id = get_or_create_edition(book["brand"])
            if edition_id is None:
                continue
            madb_book_id = book.get("madb_id", "")
            if not madb_book_id:
                stats["volumes_skip_no_madb_id"] = stats.get("volumes_skip_no_madb_id", 0) + 1
                continue
            if madb_book_id in madb_book_seen:
                stats["volumes_skip_dup_madb"] = stats.get("volumes_skip_dup_madb", 0) + 1
                continue
            isbn = normalize_isbn(book["isbn"]) or None
            if isbn and isbn in isbn_seen:
                # 同 ISBN が 別 cluster で 重複登録 (= データ不整合) → skip
                stats["volumes_skip_dup_isbn"] += 1
                continue
            num, vlabel, is_extra = extract_volume_number(
                book.get("label", ""), book.get("vol", "")
            )
            if is_extra or num is None:
                stats["volumes_extra"] += 1
                num = num or 0
            try:
                cur.execute(
                    """INSERT INTO volumes
                       (edition_id, madb_book_id, isbn13, number, volume_label,
                        is_extra, release_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        edition_id,
                        madb_book_id,
                        isbn,
                        num,
                        vlabel,
                        1 if is_extra else 0,
                        book.get("date") or None,
                    ),
                )
                madb_book_seen.add(madb_book_id)
                if isbn:
                    isbn_seen.add(isbn)
                stats["volumes_inserted"] += 1
                if not isbn:
                    stats["volumes_no_isbn"] = stats.get("volumes_no_isbn", 0) + 1
            except sqlite3.IntegrityError as e:
                stats["volumes_skip_dup_madb"] = stats.get("volumes_skip_dup_madb", 0) + 1

    db.commit()

    print("\n=== populate stats ===", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k}: {v}", file=sys.stderr)

    # 確認 query
    print("\n=== DB 確認 ===", file=sys.stderr)
    for tbl in ["series", "editions", "volumes", "series_authors"]:
        row = cur.execute(f"SELECT COUNT(*) AS n FROM {tbl}").fetchone()
        print(f"  {tbl}: {row['n']}", file=sys.stderr)

    # 主要 series 確認
    print("\n=== 主要 series 確認 ===", file=sys.stderr)
    probes = [
        ("Q219948", "うる星やつら", ""),
        ("Q219948", "うる星やつら", "オンリー・ユー"),
        ("Q219948", "うる星やつら2", "ビューティフル・ドリーマー"),
        ("Q219948", "らんま1/2", ""),
        ("Q550311", "HUNTER×HUNTER", ""),
    ]
    for qid, title, sub in probes:
        row = cur.execute(
            """SELECT s.id, s.title, s.subtitle, s.title_kana, s.title_official_en,
                      s.source, s.adult_score,
                      (SELECT COUNT(*) FROM editions WHERE series_id=s.id) AS n_ed,
                      (SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id
                       WHERE e.series_id=s.id) AS n_vol
               FROM series s
               WHERE s.qid IS ? AND s.title = ? AND IFNULL(s.subtitle,'') = ?""",
            (qid, title, sub),
        ).fetchone()
        if row:
            print(
                f"  ✅ {row['title']!r} sub={row['subtitle']!r}  src={row['source']}  "
                f"editions={row['n_ed']}  volumes={row['n_vol']}  "
                f"kana={row['title_kana']!r}",
                file=sys.stderr,
            )
        else:
            print(f"  ❌ NOT FOUND: {qid}|{title}|{sub}", file=sys.stderr)

    db.close()


if __name__ == "__main__":
    main()
