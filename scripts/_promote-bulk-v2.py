"""step G: db-v2.sqlite + series-supplement-v2.yml から MANGAL yml を 生成。

v1 scope: 既存 56 yml に 対応する series のみ regenerate
  - data/manga/*.yml の slug を 起点に db-v2 で 検索
  - 新 schema (= subtitle, subtitle_kana, volume_label 等) で 出力
  - data/manga.v2/<slug>.yml に書き出し (= 旧 data/manga は 不変)
  - 後で diff で 比較

filter (= step A/B、 「本編以外は極力表示しない」):
  - step A: 同 qid series で 「親 / 子」 関係 検出
            親 = title が prefix で 親 has MORE volumes → 子 is spinoff
  - step B: 本編 series 内の edition filter
            keep: standard / bunkobon / wideban / kanzenban / shinsoban / aizoban
            drop: anime / other / renewal
            drop imprint: 'My first big%' / '%コンビニ%' / '%増刊%'
            spinoff series は max(release_date) >= CUTOFF_YEAR なら keep
"""

import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
SRC_DIR = ROOT / "data" / "manga"
OUT_DIR = ROOT / "data" / "manga.v2"

CUTOFF_YEAR = 2015  # spinoff で この年 以降なら keep
KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}

# brand (= MADB imprint) → magazine key (= data/magazines.yml master)
# 確度高い 1対1 のみ。
BRAND_TO_MAGAZINE = {
    "ジャンプコミックス": "weekly-shonen-jump",
    "JUMPCOMICS": "weekly-shonen-jump",
    "ジャンプcomics": "weekly-shonen-jump",
    "Jumpcomics": "weekly-shonen-jump",
    "少年サンデーコミックス": "weekly-shonen-sunday",
    "SHONENSUNDAYCOMICS": "weekly-shonen-sunday",
    "少年マガジンコミックス": "weekly-shonen-magazine",
    "SHONENMAGAZINECOMICS": "weekly-shonen-magazine",
    "少年チャンピオンコミックス": "champion",
    "SHONENCHAMPIONCOMICS": "champion",
    "SHŌNENCHAMPIONCOMICS": "champion",
    "ガンガンコミックス": "gangan",
    "Gangancomics": "gangan",
    "角川コミックスエース": "shonen-ace",
    "コミックボンボン": "comic-bonbon",
    "月刊少年マガジン": "monthly-shonen-magazine",
    "別冊少年マガジン": "bessatsu-shonen-magazine",
    "ヤングジャンプコミックス": "weekly-young-jump",
    "YOUNGJUMPCOMICS": "weekly-young-jump",
    "ヤングマガジンKC": "weekly-young-magazine",
    "ヤンマガKC": "weekly-young-magazine",
    "ヤングサンデーコミックス": "weekly-young-sunday",
    "ウルトラジャンプコミックス": "ultra-jump",
    "ビッグコミックス": "big-comic",
    "BIGCOMICS": "big-comic",
    "ビッグコミックススペシャル": "big-comic",
    "BIGCOMICSSPECIAL": "big-comic",
    "モーニングKC": "morning",
    "MorningKC": "morning",
    "アフタヌーンKC": "afternoon",
    "AfternoonKC": "afternoon",
    "アクションコミックス": "manga-action",
    "ACTIONCOMICS": "manga-action",
    "マーガレットコミックス": "margaret",
    "MARGARETCOMICS": "margaret",
    "別冊マーガレットコミックス": "betsuma",
    "りぼんマスコットコミックス": "ribon",
    "なかよしコミックス": "nakayoshi",
    "ちゃおコミックス": "ciao",
    "花とゆめCOMICS": "hana-to-yume",
    "花とゆめコミックス": "hana-to-yume",
    "LaLacomics": "lala",
    "LaLaCOMICS": "lala",
    "ヤングアニマルコミックス": "young-animal",
    "YOUNGANIMALCOMICS": "young-animal",
    "BELOVE": "be-love",
    "てんとう虫コミックス": "ciao",
}


def _normalize_brand_for_mag(brand: str) -> str:
    """brand を BRAND_TO_MAGAZINE key 形式に正規化 (= 中黒/空白 strip)。"""
    if not brand:
        return ""
    return brand.replace("・", "").replace("　", "").replace(" ", "").strip()


def infer_magazine_from_brand(editions: list[dict], valid_mags: set) -> str | None:
    """editions の 主 brand から magazine 推定。"""
    for ed in editions:
        norm = _normalize_brand_for_mag(ed.get("imprint") or "")
        if norm in BRAND_TO_MAGAZINE:
            mag = BRAND_TO_MAGAZINE[norm]
            if not valid_mags or mag in valid_mags:
                return mag
    return None
DROP_IMPRINT_PATTERNS = ["My first big", "コンビニ", "増刊", "同人", "ジャンプremix", "フィルムコミック",
                         "カッパ・ノベル", "カッパノベル", "カッパ・ホーム", "カッパホーム"]
# bilingual / 英訳版 imprint は drop (= 翻訳版 は 別 product)
DROP_IMPRINT_LOWER_PATTERNS = ["bilingual", "english"]
# 'complete works' は 英訳 全集 で 多用 (= 「TEZUKA OSAMU THE COMPLETE WORKS」、
# 「The complete works of Fujiko・F・Fujio」 等)。 但し 日本語 imprint で 「= English」
# 並列表記 cases (= 「藤子・F・不二雄大全集 = The Complete Works of Fujiko・F・Fujio」)
# は 日本語版 で keep。 「=」 含む imprint は drop 対象外。
DROP_IMPRINT_LOWER_PATTERNS_NO_EQ = ["complete works"]
# 漫画以外 series は MANGAL 掲載対象外 (= title prefix で detect)。
# CLAUDE.md / MEMORY.md 大原則: 「通常版/ワイド版/文庫版/愛蔵版 等 漫画 only」
DROP_TITLE_PREFIX_PATTERNS = [
    "テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
    "劇場版", "映画", "OVA",
    "ノベライズ", "ノベル",
]
# 関連書 (= ガイドブック / 設定資料集 / 攻略本 等、 漫画作品ではない 副次出版物)。
# title 内 包含で detect。 「大全集」 は 主作品 compilation 多いので 除外しない。
DROP_TITLE_CONTAINS_PATTERNS = [
    "ガイドブック", "ファンブック", "設定資料集",
    "公式図録", "公式読本", "公式ファン", "公式コミックガイド",
    "アンソロジー",
    "キャラクター名鑑", "人物名鑑",
    "心理分析", "心理解析", "完全解析", "完全攻略", "攻略本",
    "解析書", "解体新書", "解体全書",
    "大研究", "最終研究", "超研究", "大事典", "大百科", "大解剖",
    "パーフェクトガイド", "完全読本", "完全ガイド", "必勝法",
    "の秘密", "の謎", "コミック大全", "コミックスペシャル",
    "ナビゲーション", "考察",
]


def load_seed3() -> dict:
    """series_key → seed3 entry の dict"""
    with SEED3.open("r", encoding="utf-8") as f:
        d = yaml.safe_load(f)
    return {e["key"]: e for e in d["series"]}


def normalize_title_for_prefix(t: str) -> str:
    """『〜』 strip、 「英訳・」「劇場版」「テレビアニメ版」 等 接頭辞 strip。"""
    s = t.strip()
    # 『...』 → ...
    s = re.sub(r"[『「【〔]", "", s)
    s = re.sub(r"[』」】〕]", "", s)
    # 接頭辞 strip
    for prefix in ["英訳・", "劇場版", "劇場用アニメ", "テレビアニメ版",
                   "映画 ", "映画"]:
        if s.startswith(prefix):
            s = s[len(prefix):].lstrip()
    return s


def build_parent_map(con: sqlite3.Connection) -> dict[int, int]:
    """series_id → parent_series_id (= 親検出済 only)。 公開対象 (= score<3) のみ。

    親判定:
      - 同 qid または 同 creator_name
      - 親 title が 子 title の prefix (= normalize 後)
      - 親 has MORE total ISBN volumes than 子
      - 親 自身 が 副題なし
    """
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    cur.execute("""
        SELECT s.id, s.qid, s.title, s.subtitle,
               (SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id
                WHERE e.series_id=s.id AND v.isbn13 IS NOT NULL) AS n_isbn
        FROM series s
        WHERE s.adult_score < 3
    """)
    all_series = [dict(r) for r in cur.fetchall()]
    by_qid = defaultdict(list)
    for s in all_series:
        if s["qid"]:
            by_qid[s["qid"]].append(s)
    parent_map: dict[int, int] = {}
    for qid, sib in by_qid.items():
        # 候補 parent (= 副題なし、 n_isbn 多い順)
        parents = [s for s in sib if not s["subtitle"]]
        parents.sort(key=lambda s: -s["n_isbn"])
        for child in sib:
            child_norm = normalize_title_for_prefix(child["title"])
            for parent in parents:
                if parent["id"] == child["id"]:
                    continue
                parent_norm = normalize_title_for_prefix(parent["title"])
                if not parent_norm:
                    continue
                # parent_norm が child_norm の prefix
                if child_norm.startswith(parent_norm) and child_norm != parent_norm:
                    # 親 has more vol
                    if parent["n_isbn"] > child["n_isbn"]:
                        parent_map[child["id"]] = parent["id"]
                        break
                # 副題ある child は parent と base title が一致 (= no prefix relation)
                # ケースも spinoff 扱い
                elif child.get("subtitle") and parent_norm == child_norm:
                    if parent["n_isbn"] > child["n_isbn"]:
                        parent_map[child["id"]] = parent["id"]
                        break
    return parent_map


def get_max_release_year(con: sqlite3.Connection, series_id: int) -> int | None:
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    r = cur.execute("""
        SELECT MAX(SUBSTR(v.release_date, 1, 4)) AS y
        FROM volumes v JOIN editions e ON e.id=v.edition_id
        WHERE e.series_id=? AND v.release_date IS NOT NULL
    """, (series_id,)).fetchone()
    if r and r["y"]:
        try:
            return int(r["y"])
        except ValueError:
            return None
    return None


def find_series(con: sqlite3.Connection, slug: str, title: str, qid: str | None) -> dict | None:
    """旧 yml の (slug, title, qid) から db-v2 で series 探す。

    優先順:
      1. qid + title 完全一致
      2. title 完全一致 (= qid なし時)
      3. title 部分一致
    """
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    if qid:
        rows = cur.execute(
            "SELECT * FROM series WHERE qid=? AND title=? ORDER BY adult_score LIMIT 1",
            (qid, title),
        ).fetchall()
        if rows:
            return dict(rows[0])
    rows = cur.execute(
        "SELECT * FROM series WHERE title=? ORDER BY adult_score LIMIT 1", (title,)
    ).fetchall()
    if rows:
        return dict(rows[0])
    return None


def _title_punct_suffix(title: str | None) -> str:
    """title から alphanumeric + kana + 漢字 を 全部 strip し、 残った punctuation を 返す。

    例: 'バクマン。' → '。'、 'BAKUMAN。' → '。'、 'バクマン!' → '!'
    『BAKUMAN。』 と 『バクマン。』 は match (= 同作品の表記揺れ)、
    『バクマン!』 (= 別作品) は punct 違いで 非 match。
    """
    if not title:
        return ""
    return re.sub(r"[a-zA-Z0-9ぁ-んァ-ヶー一-龯々〆〇 　]", "", title)


def _normalize_kana(kana: str | None) -> str:
    """title_kana を normalize (= 空白 / 中黒 / × 等 strip)。

    'ハンター ハンター' と 'ハンター × ハンター' を 共通 'ハンターハンター' に
    寄せて kana match の 表記揺れ吸収。
    """
    if not kana:
        return ""
    return re.sub(r"[^ぁ-んァ-ヶー一-龯]", "", kana)


def _is_ascii_title(title: str | None) -> bool:
    """title に 漢字/かな が 含まれない なら ASCII (= ローマ字表記) 扱い。

    'Hunter×hunter' = ASCII (= 'H','u','n',...,×,'h','u','n','t','e','r' で kana/kanji なし)
    'ハンター×ハンター' = non-ASCII (= カナ含む)
    """
    if not title:
        return False
    return not bool(re.search(r"[ぁ-んァ-ヶー一-龯]", title))


def _strip_trailing_punct(title: str | None) -> str:
    """title 末尾 の punct (= '.', ',', '。', '．' 等) を strip。
    '銀河英雄伝説.' と '銀河英雄伝説' を 同一視 する 用途。
    """
    if not title:
        return ""
    return re.sub(r"[.,。．・、]+$", "", title.strip())


# publisher prefix + kana normalize cache (= 起動時 1 回 build、 lookup O(1))
# extract で 2000 candidates × find_related_series_ids = 大量 SQL を 回避
_PUB_CACHE: dict | None = None
_MAJOR_CACHE: dict | None = None
_KANA_INDEX: dict | None = None  # normalized_kana → list of (series_id, title, title_kana)


def _build_kana_index(con: sqlite3.Connection) -> None:
    """全 series で normalize_kana(title_kana) → [(id, title, title_kana)] map 構築。"""
    global _KANA_INDEX
    if _KANA_INDEX is not None:
        return
    from collections import defaultdict
    _KANA_INDEX = defaultdict(list)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, title, title_kana FROM series WHERE title_kana IS NOT NULL"
    ).fetchall()
    for sid, title, kana in rows:
        k_norm = _normalize_kana(kana)
        if k_norm:
            _KANA_INDEX[k_norm].append((sid, title, kana))


def _build_publisher_cache(con: sqlite3.Connection) -> None:
    """全 series の publisher prefixes を 1 回 SQL scan で 構築 (= cache)。"""
    global _PUB_CACHE, _MAJOR_CACHE
    if _PUB_CACHE is not None:
        return
    from collections import defaultdict, Counter
    _PUB_CACHE = defaultdict(set)
    counters: dict = defaultdict(Counter)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT e.series_id, v.isbn13, e.type, e.imprint "
        "FROM volumes v JOIN editions e ON e.id=v.edition_id "
        "WHERE v.isbn13 IS NOT NULL"
    ).fetchall()
    for sid, isbn, type_, imp in rows:
        if type_ not in KEEP_EDITION_TYPES:
            continue
        imp = imp or ""
        if any(pat in imp for pat in DROP_IMPRINT_PATTERNS):
            continue
        imp_l = imp.lower()
        if any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS):
            continue
        if "=" not in imp and any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
            continue
        p = (isbn or "").replace("-", "")
        if len(p) >= 6:
            prefix = p[:6]
            _PUB_CACHE[sid].add(prefix)
            counters[sid][prefix] += 1
    _MAJOR_CACHE = {
        sid: cnt.most_common(1)[0][0]
        for sid, cnt in counters.items()
    }


def get_major_publisher_prefix(con: sqlite3.Connection, series_id: int) -> str | None:
    """cache から series の 最大 vol 数 publisher prefix 取得。"""
    _build_publisher_cache(con)
    return _MAJOR_CACHE.get(series_id) if _MAJOR_CACHE else None


def _get_major_publisher_prefix_legacy(con: sqlite3.Connection, series_id: int) -> str | None:
    """旧 (= cache 不使用) 実装、 比較 / 確認 用。"""
    from collections import Counter
    cur = con.cursor()
    rows = cur.execute(
        "SELECT v.isbn13, e.type, e.imprint "
        "FROM volumes v JOIN editions e ON e.id=v.edition_id "
        "WHERE e.series_id=? AND v.isbn13 IS NOT NULL", (series_id,)
    ).fetchall()
    counter: Counter = Counter()
    for r in rows:
        if r[1] not in KEEP_EDITION_TYPES:
            continue
        imp = r[2] or ""
        if any(pat in imp for pat in DROP_IMPRINT_PATTERNS):
            continue
        imp_l = imp.lower()
        if any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS):
            continue
        if "=" not in imp and any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
            continue
        p = (r[0] or "").replace("-", "")
        if len(p) >= 6:
            counter[p[:6]] += 1
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def get_publisher_prefixes(con: sqlite3.Connection, series_id: int) -> set:
    """cache から series の publisher prefixes set 取得。"""
    _build_publisher_cache(con)
    return _PUB_CACHE.get(series_id, set()) if _PUB_CACHE else set()


def _get_publisher_prefixes_legacy(con: sqlite3.Connection, series_id: int) -> set:
    """旧 (= cache 不使用) 実装。"""
    cur = con.cursor()
    prefixes: set = set()
    rows = cur.execute(
        "SELECT v.isbn13, e.type, e.imprint "
        "FROM volumes v JOIN editions e ON e.id=v.edition_id "
        "WHERE e.series_id=? AND v.isbn13 IS NOT NULL", (series_id,)
    ).fetchall()
    for r in rows:
        if r[1] not in KEEP_EDITION_TYPES:
            continue
        imp = r[2] or ""
        if any(pat in imp for pat in DROP_IMPRINT_PATTERNS):
            continue
        imp_l = imp.lower()
        if any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS):
            continue
        if "=" not in imp and any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
            continue
        p = (r[0] or "").replace("-", "")
        if len(p) >= 6:
            prefixes.add(p[:6])
    return prefixes


def find_related_series_ids(con: sqlite3.Connection, main: dict) -> list[int]:
    """main series と 関連 series id を 返す。

    cluster 分裂で 同一作品の volumes が 別 series row に 散らばってる cases を 統合する。

    rules:
      - main 自身
      - 同 qid で title が case-insensitive 一致
      - 同 title (= 完全一致 + 末尾 punct strip 後) で qid IS NULL な orphan
      - title_kana + punct suffix 一致 (= ローマ字/カタカナ 表記揺れ)
      - **publisher group check**: main の publisher と 候補の publisher が 別 (= 6桁
        ISBN prefix で 別 系列) なら merge しない (= 銀河英雄伝説 道原版 徳間 vs
        藤崎竜版 集英社 の 誤統合 防止)
    """
    cur = con.cursor()
    ids = {main["id"]}
    main_title_lower = (main["title"] or "").lower()
    main_title_strip = _strip_trailing_punct(main["title"])
    main_kana = main.get("title_kana") or ""
    main_punct = _title_punct_suffix(main["title"])
    main_pubs = get_publisher_prefixes(con, main["id"])

    def pub_compatible(cand_id: int) -> bool:
        """候補の major publisher (= 最多 vol publisher prefix) が main の publishers
        set に 含まれる か 候補 不明なら merge OK。

        - 銀英伝 117723 (= 主 集英社 ヤング ジャンプ 33 vols、 副 徳間 アニメ 6 vols)
          → major=集英社 978408、 道原 main pubs={978419} → skip
        - ドラえもん 78712 (= 主 小学館 てんとう虫 36、 副 中公 35)
          → major=小学館 978409、 main pubs={978409} → merge OK
        """
        if not main_pubs:
            return True
        cand_major = get_major_publisher_prefix(con, cand_id)
        if not cand_major:
            return True
        return cand_major in main_pubs

    # 同 qid で title case-insensitive 一致
    if main.get("qid"):
        for r in cur.execute(
            "SELECT id, title FROM series WHERE qid=?", (main["qid"],)
        ).fetchall():
            if (r[1] or "").lower() == main_title_lower and pub_compatible(r[0]):
                ids.add(r[0])
    # 同 title (= 末尾 punct strip 後) で qid 無し orphan
    for r in cur.execute(
        "SELECT id, title FROM series WHERE qid IS NULL"
    ).fetchall():
        if _strip_trailing_punct(r[1]) == main_title_strip and pub_compatible(r[0]):
            ids.add(r[0])
    # title_kana + punct suffix 一致 (= romaji/katakana 表記揺れ cluster)
    # 安全策: 片方が ASCII (= ローマ字表記、 e.g. 'BAKUMAN。', 'Hunter×hunter') の cases のみ。
    # でないと 'テレビアニメ版 犬夜叉' と '犬夜叉' (= 両方 kana='イヌヤシャ') が
    # 誤 merge され、 別作品 が 統合されてしまう。
    # kana は normalize (= 空白/×/中黒 strip) で 'ハンター ハンター' と
    # 'ハンター × ハンター' を 同 'ハンターハンター' として 比較。
    main_title = main["title"] or ""
    main_is_ascii = _is_ascii_title(main_title)
    main_kana_norm = _normalize_kana(main_kana)
    if main_kana_norm:
        # cache から 同 normalized kana の series を 即取得 (= 旧 full table scan 回避)
        _build_kana_index(con)
        for sid, other_title, _other_kana in _KANA_INDEX.get(main_kana_norm, []):
            if sid == main["id"]:
                continue
            other_title = other_title or ""
            other_is_ascii = _is_ascii_title(other_title)
            if not (main_is_ascii or other_is_ascii):
                continue
            if _title_punct_suffix(other_title) == main_punct and pub_compatible(sid):
                ids.add(sid)
    # transitive expansion: 既に merge 済 ids の titles から 同 qid +
    # case-insensitive title match を 追加探索 (= e.g. HUNTER で kana=NULL な
    # 'HUNTER×HUNTER' cluster を 'Hunter×hunter' cluster 経由で 拾う)
    merged_titles_lower = set()
    if ids:
        ph = ",".join("?" for _ in ids)
        for r in cur.execute(
            f"SELECT title, qid FROM series WHERE id IN ({ph})", list(ids)
        ).fetchall():
            if r[0]:
                merged_titles_lower.add((r[0].lower(), r[1] or ""))
    for t_lower, q in merged_titles_lower:
        # 同 qid + title case-insensitive 一致 で merge (= 安全: ASCII variant 同士)
        if q:
            for r in cur.execute(
                "SELECT id, title FROM series WHERE qid=?", (q,)
            ).fetchall():
                if (r[1] or "").lower() == t_lower and pub_compatible(r[0]):
                    ids.add(r[0])
        # qid 無し orphan で title case-insensitive 一致
        for r in cur.execute(
            "SELECT id FROM series WHERE LOWER(title)=? AND qid IS NULL",
            (t_lower,),
        ).fetchall():
            if pub_compatible(r[0]):
                ids.add(r[0])
    return list(ids)


def get_authors(con: sqlite3.Connection, series_id: int) -> list[dict]:
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    rows = cur.execute(
        """
        SELECT m.name, sa.role
        FROM series_authors sa
        JOIN mangaka m ON m.id = sa.mangaka_id
        WHERE sa.series_id = ?
        """,
        (series_id,),
    ).fetchall()
    return [{"name": r["name"], "role": r["role"]} for r in rows]


def edition_passes_filter(ed_row: dict) -> bool:
    """edition の type / imprint で 本編判定。 step B filter。"""
    if ed_row["type"] not in KEEP_EDITION_TYPES:
        return False
    imp = ed_row["imprint"] or ""
    for pat in DROP_IMPRINT_PATTERNS:
        if pat in imp:
            return False
    imp_l = imp.lower()
    for pat in DROP_IMPRINT_LOWER_PATTERNS:
        if pat in imp_l:
            return False
    # 'complete works' 等 「=」 並列表記 除く 英訳 全集 系
    if "=" not in imp:
        for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ:
            if pat in imp_l:
                return False
    return True


def get_editions_with_volumes(con: sqlite3.Connection, series_ids: list[int] | int) -> list[dict]:
    """editions + volumes を まとめて取得し、 同 type editions を 1 つに merge。

    merge logic (= 同 series 内の 同 type editions = 限定版/DVD付き 等 packaging variant が
                  imprint 違いで 分裂しているため):
      - imprint 違いの 同 type editions を 1 つに統合
      - volume number で dedup、 同 number は 最古 release_date の entry を採用
      - 統合後 edition の imprint = 最多 volumes を持つ imprint
      - label は 最多 volumes を持つ edition から
    """
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    if isinstance(series_ids, int):
        series_ids = [series_ids]
    placeholders = ",".join("?" for _ in series_ids)
    eds = cur.execute(
        f"SELECT * FROM editions WHERE series_id IN ({placeholders})", series_ids
    ).fetchall()
    # type → [edition+volumes] list
    by_type: dict[str, list[dict]] = defaultdict(list)
    for ed in eds:
        if not edition_passes_filter(dict(ed)):
            continue
        # ORDER BY で release_date NULL を 後回し (= date あり record を dedup で 優先採用)
        vols = cur.execute(
            """SELECT * FROM volumes WHERE edition_id=?
               ORDER BY number, (release_date IS NULL), release_date""",
            (ed["id"],),
        ).fetchall()
        if not vols:
            continue
        # number=0 (= 巻号 extract 失敗) 扱い:
        #   - edition 内に 1 つでも numbered vol あれば → number=0 は skip (= 偽 #1 dedup 弊害除去)
        #   - edition 内 全部 number=0 → release_date 昇順で #1, #2,... 連番付与 (= 短編集等)
        nonzero_exists = any(v["number"] for v in vols)
        # 同 number 内で 一番古い 1 件のみ採用 (= 初版 representative、 同 edition 内 dedup)
        seen = set()
        primary_vols = []
        if nonzero_exists:
            for v in vols:
                if not v["number"]:
                    continue
                if v["number"] in seen:
                    continue
                seen.add(v["number"])
                primary_vols.append(
                    {
                        "number": v["number"],
                        "volume_label": v["volume_label"],
                        "isbn13": v["isbn13"],
                        "release_date": v["release_date"],
                        "cover_url": v["cover_url"],
                        "asin": v["asin"],
                    }
                )
        else:
            # 全 vol が number=0 → release_date 順で連番
            vols_sorted = sorted(vols, key=lambda x: x["release_date"] or "9999-99")
            for idx, v in enumerate(vols_sorted, start=1):
                primary_vols.append(
                    {
                        "number": idx,
                        "volume_label": v["volume_label"],
                        "isbn13": v["isbn13"],
                        "release_date": v["release_date"],
                        "cover_url": v["cover_url"],
                        "asin": v["asin"],
                    }
                )
        if not primary_vols:
            continue
        by_type[ed["type"]].append(
            {
                "type": ed["type"],
                "label": ed["label"],
                "imprint": ed["imprint"],
                "year_started": ed["year_started"],
                "year_ended": ed["year_ended"],
                "volumes": primary_vols,
            }
        )
    out = []
    for type_key, ed_group in by_type.items():
        if len(ed_group) == 1:
            out.append(ed_group[0])
            continue
        # 同 type で 複数 edition → merge
        # 全 volumes を集めて number で dedup、 同 number は release_date 最古 entry 優先
        by_num: dict[int, dict] = {}
        for ed in ed_group:
            for v in ed["volumes"]:
                n = v["number"]
                cur_v = by_num.get(n)
                if cur_v is None:
                    by_num[n] = v
                    continue
                # release_date 比較 (= None は 最後扱い)
                cur_d = cur_v.get("release_date") or "9999-99"
                new_d = v.get("release_date") or "9999-99"
                if new_d < cur_d:
                    by_num[n] = v
        merged_vols = [by_num[n] for n in sorted(by_num.keys())]
        # 代表 imprint / label 選定:
        #   1. 最古 first vol release_date を 持つ edition (= 元祖 imprint 優先)
        #   2. 同点なら 最多 vol 数
        # 例: ドラえもん で 中公 35 vols (1984~) と てんとう虫 34 vols (1974~) → てんとう虫
        def _ed_priority(e):
            dates = [v["release_date"] for v in e["volumes"] if v["release_date"]]
            first_date = min(dates) if dates else "9999-99"
            return (first_date, -len(e["volumes"]))
        primary_ed = sorted(ed_group, key=_ed_priority)[0]
        out.append(
            {
                "type": type_key,
                "label": primary_ed["label"],
                "imprint": primary_ed["imprint"],
                "year_started": primary_ed["year_started"],
                "year_ended": primary_ed["year_ended"],
                "volumes": merged_vols,
            }
        )
    # editions を 第1巻 (= 最古 volume) の release_date 昇順 で sort
    def first_vol_date(ed_dict):
        dates = [v["release_date"] for v in ed_dict["volumes"] if v["release_date"]]
        return min(dates) if dates else "9999-99"
    out.sort(key=first_vol_date)
    return out


def clean_vol(v: dict) -> dict:
    """yml に出力する volume dict を 作る (= null を 適切に省略)"""
    o = {"number": v["number"]}
    if v["volume_label"]:
        o["volume_label"] = v["volume_label"]
    o["asin"] = v.get("asin")
    if v["isbn13"]:
        o["isbn13"] = str(v["isbn13"])
    else:
        o["isbn13"] = None
    o["cover_url"] = v.get("cover_url")
    if v["release_date"]:
        o["release_date"] = v["release_date"]
    else:
        o["release_date"] = None
    return o


def clean_edition(ed: dict) -> dict:
    out = {
        "type": ed["type"],
        "label": ed["label"],
    }
    if ed["imprint"]:
        out["imprint"] = ed["imprint"]
    if ed["year_started"]:
        out["year_started"] = ed["year_started"]
    if ed["year_ended"]:
        out["year_ended"] = ed["year_ended"]
    out["volumes"] = [clean_vol(v) for v in ed["volumes"]]
    return out


def build_yml(
    src_yml: dict,
    series_row: dict,
    authors: list[dict],
    editions: list[dict],
    seed3: dict | None,
    valid_pubs: set,
    valid_mags: set,
    valid_gens: set,
) -> dict:
    """db-v2 + 種3 + 旧 yml の slug / 一部 metadata から 新 yml dict を build。

    旧 yml から流用:
      - slug
      - title_romaji (= ローマ字化は ロジック移植せず 既存値 再利用)
      - anime_first_year / awards / wikipedia_url 等 既存補強
    """
    o: dict = {}
    o["slug"] = src_yml["slug"]
    o["title"] = series_row["title"]
    # title_kana は スペース削除 (= MANGAL protocol: ふりがな に空白 入れない)
    raw_kana = series_row["title_kana"] or src_yml.get("title_kana", "")
    o["title_kana"] = re.sub(r"[\s　]+", "", raw_kana) if raw_kana else ""
    o["title_romaji"] = src_yml.get("title_romaji", "")
    # subtitle が edition 名 (= '新装再編版' 等) なら strip (= 全 edition 含む page には不適)
    sub = series_row["subtitle"]
    EDITION_NAME_SUBTITLES = {"新装再編版", "新装版", "完全版", "愛蔵版", "文庫版",
                              "ワイド版", "デラックス", "新装新版", "リニューアル版",
                              "廉価版", "新装版コミックス", "新装版", "復刻版"}
    if sub and sub in EDITION_NAME_SUBTITLES:
        sub = None
    if sub:
        o["subtitle"] = sub
    if series_row["subtitle_kana"] and sub:
        o["subtitle_kana"] = re.sub(r"[\s　]+", "", series_row["subtitle_kana"])

    # 年代: editions の volumes.release_date から 計算
    # year_started = 最も古い edition の 最初の volume year
    # year_ended = 「最初の edition (= 本編初版)」 の 最後の volume year
    #              (= リニューアル版を 含めずに 原作連載終了年を出す)
    def year_of(d: str | None) -> int | None:
        if not d or len(d) < 4:
            return None
        try:
            return int(d[:4])
        except ValueError:
            return None

    all_years = []
    for ed in editions:
        for v in ed["volumes"]:
            y = year_of(v.get("release_date"))
            if y:
                all_years.append(y)
    o["year_started"] = min(all_years) if all_years else src_yml.get("year_started", 2000)

    # year_ended: standard edition の 「最大 vol number の 初版 date」 (= 真の 連載完結年)
    # standard edition が ない (= 文庫/愛蔵 のみ 等) 場合は 全 editions
    # vol 1 の 「reissue date 2000」 が 混入 する のを 避ける ため、 各 vol の MIN
    # (= 初版) を 取り、 最大 vol number の date を 採用
    if editions:
        standard_eds = [ed for ed in editions if ed.get("type") == "standard"]
        target_eds = standard_eds if standard_eds else editions
        per_vol_min_date: dict = {}
        for ed in target_eds:
            for v in ed["volumes"]:
                n = v.get("number")
                d = v.get("release_date")
                if not n or not d:
                    continue
                if n not in per_vol_min_date or d < per_vol_min_date[n]:
                    per_vol_min_date[n] = d
        if per_vol_min_date:
            max_vol = max(per_vol_min_date.keys())
            o["year_ended"] = year_of(per_vol_min_date[max_vol])
        else:
            o["year_ended"] = src_yml.get("year_ended")
    else:
        o["year_ended"] = src_yml.get("year_ended")
    # status は 種3 から
    o["status"] = (seed3 or {}).get("status") or src_yml.get("status", "completed")
    # status=ongoing なら year_ended は null
    if o["status"] == "ongoing":
        o["year_ended"] = None

    # authors / original_authors
    writers, originals = [], []
    for a in authors:
        if a["role"] == "original_author":
            originals.append({"name": a["name"], "role": "writer"})  # 旧 schema 互換
        else:
            writers.append({"name": a["name"], "role": a["role"]})
    if not writers:
        writers = src_yml.get("authors") or [{"name": "(unknown)", "role": "writer_artist"}]
    o["authors"] = writers
    o["original_authors"] = originals

    # publisher: 種3 → 旧 yml の 優先で 取得、 master 未定義なら 旧 yml に fallback
    pub_cand = (seed3 or {}).get("publisher") or src_yml.get("publisher")
    if pub_cand and valid_pubs and pub_cand not in valid_pubs:
        pub_cand = src_yml.get("publisher", pub_cand)
    o["publisher"] = pub_cand or "(unknown)"

    # magazine: 種3 由来は AI fill で 旧 master key と 揃ってない 可能性
    # master 未定義時は 旧 yml に fallback、 それでも未定義なら brand から推定、
    # 最後に null
    mag_cand = (seed3 or {}).get("magazine") or src_yml.get("magazine")
    if mag_cand and valid_mags and mag_cand not in valid_mags:
        old_mag = src_yml.get("magazine")
        mag_cand = old_mag if old_mag and old_mag in valid_mags else None
    # brand → magazine 推定 (= 種3 fill 漏れ 補完)
    if not mag_cand:
        mag_cand = infer_magazine_from_brand(editions, valid_mags)
    o["magazine"] = mag_cand

    o["demographic"] = (seed3 or {}).get("demographic") or src_yml.get("demographic", "shounen")

    # genres: 種3 由来 keys を validate
    genres_cand = (seed3 or {}).get("genres") or src_yml.get("genres", ["other"])
    if valid_gens:
        filtered = [g for g in genres_cand if g in valid_gens]
        if not filtered:
            filtered = src_yml.get("genres", ["other"])
        genres_cand = filtered
    o["genres"] = genres_cand

    o["synopsis"] = (seed3 or {}).get("synopsis") or src_yml.get("synopsis", "")

    # anime / alternative_titles
    anime_adapted = (seed3 or {}).get("anime_adapted")
    if anime_adapted is None:
        anime_adapted = src_yml.get("anime_adapted")
    if anime_adapted is not None:
        o["anime_adapted"] = anime_adapted
    if "anime_first_year" in src_yml:
        o["anime_first_year"] = src_yml["anime_first_year"]

    # alt_en 優先順: 種3 (= ユーザ手動修正) > 種3 で明示削除 (= en: null) > db-v2 (= 種1直) > src_yml
    # L3 計画 Phase C: 旧 logic は 種3 を 全く参照せず、 _fix-seed3-en-values.py 修正が 永久 未反映 bug。
    seed3_alt = (seed3 or {}).get("alternative_titles") or {}
    src_alt = src_yml.get("alternative_titles") or {}
    db_alt_en = series_row["title_official_en"]

    # 種3 で 「en: null」 明示 = 削除意思 (= ranma 等)
    if "en" in seed3_alt and seed3_alt.get("en") is None:
        merged_alt = {k: v for k, v in seed3_alt.items() if v is not None}
    else:
        merged_alt = dict(src_alt)
        # 種3 値で 上書き (= ユーザ手動修正 を 最優先)
        for k, v in seed3_alt.items():
            if v is not None:
                merged_alt[k] = v
        # db-v2 alt_en fallback (= 種3/旧 yml に en なければ)
        if db_alt_en and "en" not in merged_alt:
            merged_alt["en"] = db_alt_en

    if merged_alt:
        o["alternative_titles"] = merged_alt

    if "awards" in src_yml:
        o["awards"] = src_yml["awards"]
    if series_row["qid"]:
        o["wikidata_qid"] = series_row["qid"]
    if "wikipedia_url" in src_yml:
        o["wikipedia_url"] = src_yml["wikipedia_url"]

    o["editions"] = [clean_edition(ed) for ed in editions]
    return o


def load_master_keys() -> tuple[set, set, set]:
    """data/magazines.yml + publishers.yml + genres.yml の 有効 key set を返す。"""
    pub_yml = ROOT / "data" / "publishers.yml"
    mag_yml = ROOT / "data" / "magazines.yml"
    gen_yml = ROOT / "data" / "genres.yml"
    pubs, mags, gens = set(), set(), set()
    if pub_yml.exists():
        with pub_yml.open("r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        pubs = set(d.keys())
    if mag_yml.exists():
        with mag_yml.open("r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        mags = set(d.keys())
    if gen_yml.exists():
        with gen_yml.open("r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        gens = set(d.keys())
    return pubs, mags, gens


def main():
    print(f"loading {SEED3} ...", file=sys.stderr)
    seed3 = load_seed3()
    print(f"  entries: {len(seed3)}", file=sys.stderr)

    valid_pubs, valid_mags, valid_gens = load_master_keys()
    print(
        f"  master keys: pubs={len(valid_pubs)} mags={len(valid_mags)} gens={len(valid_gens)}",
        file=sys.stderr,
    )

    con = sqlite3.connect(DB)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 既存 v2 dir clean
    for p in OUT_DIR.glob("*.yml"):
        p.unlink()

    # step A: 親 series 検出 map
    print("[step A] 親 series 検出 中 ...", file=sys.stderr)
    parent_map = build_parent_map(con)
    print(f"  検出 spinoff series 数: {len(parent_map)}", file=sys.stderr)

    stats = {"total": 0, "regenerated": 0, "not_found_in_db": 0,
             "no_editions": 0, "dropped_spinoff_old": 0,
             "dropped_non_manga": 0}
    not_found = []
    dropped = []
    dropped_non_manga = []

    for ypath in sorted(SRC_DIR.glob("*.yml")):
        stats["total"] += 1
        with ypath.open("r", encoding="utf-8") as f:
            src = yaml.safe_load(f)
        slug = src["slug"]
        title = src["title"]
        qid = src.get("wikidata_qid")
        # 漫画以外 (= テレビアニメ版 / 映画 / 劇場版 等) は MANGAL 対象外
        if any(title.startswith(pat) for pat in DROP_TITLE_PREFIX_PATTERNS):
            stats["dropped_non_manga"] += 1
            dropped_non_manga.append(f"{ypath.name}  title={title}")
            continue
        # 関連書 (= ガイドブック / 設定資料集 / アンソロジー / 攻略本 等) は対象外
        if any(pat in title for pat in DROP_TITLE_CONTAINS_PATTERNS):
            stats["dropped_non_manga"] += 1
            dropped_non_manga.append(f"{ypath.name}  title={title}  (= 関連書)")
            continue
        series = find_series(con, slug, title, qid)
        if not series:
            stats["not_found_in_db"] += 1
            not_found.append(f"{ypath.name}  title={title}")
            continue
        # step A: spinoff 判定 (= 親があれば 子 = spinoff)
        is_spinoff = series["id"] in parent_map
        if is_spinoff:
            max_y = get_max_release_year(con, series["id"])
            if max_y is None or max_y < CUTOFF_YEAR:
                stats["dropped_spinoff_old"] += 1
                dropped.append(f"{ypath.name}  title={title}  max_year={max_y}")
                continue
        # 同一作品 cluster 分裂 を 検出 (= main + 同qid + 同title orphan)、 全部 merge
        # yml の title_kana を fallback (= db series row の kana が NULL の cases、
        # e.g. id=128570 'ハンター×ハンター' kana=NULL では kana match 効かない)
        merged_series = dict(series)
        if not merged_series.get("title_kana") and src.get("title_kana"):
            merged_series["title_kana"] = src["title_kana"]
        related_ids = find_related_series_ids(con, merged_series)
        editions = get_editions_with_volumes(con, related_ids)
        if not editions:
            stats["no_editions"] += 1
            continue
        authors = get_authors(con, series["id"])
        seed_entry = seed3.get(series["series_key"])
        new_yml = build_yml(src, series, authors, editions, seed_entry,
                            valid_pubs, valid_mags, valid_gens)
        out_path = OUT_DIR / f"{slug}.yml"
        with out_path.open("w", encoding="utf-8") as f:
            f.write("# Regenerated by scripts/_promote-bulk-v2.py (= path B' step G)\n")
            yaml.dump(new_yml, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        stats["regenerated"] += 1

    print(f"\n=== stats ===", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k}: {v}", file=sys.stderr)
    if not_found:
        print(f"\n=== not found in db-v2 ===", file=sys.stderr)
        for n in not_found:
            print(f"  ❌ {n}", file=sys.stderr)
    if dropped:
        print(f"\n=== dropped (= spinoff & old) ===", file=sys.stderr)
        for d in dropped:
            print(f"  🗑️  {d}", file=sys.stderr)
    if dropped_non_manga:
        print(f"\n=== dropped (= non-manga: anime/movie/novel) ===", file=sys.stderr)
        for d in dropped_non_manga:
            print(f"  🚫 {d}", file=sys.stderr)

    print(f"\nwrote {stats['regenerated']} yml to {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
