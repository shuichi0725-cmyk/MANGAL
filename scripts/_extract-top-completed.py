"""主要 完結 漫画 2000 タイトル を db-v2 から 抽出 + yml 生成。

選定 criteria:
  - adult_score < 3 (= non-adult)
  - 通常版相当 (= standard/bunkobon/wideban/kanzenban/shinsoban/aizoban) edition あり
  - 最新巻 release_date <= 2020 (= 完結 推定)
  - 5巻以上 (= 主要作品)
  - title が 関連書 / 非漫画 prefix で 始まらない
  - score 順: qid あり ボーナス 100 + vol_count、 desc で top N

slug 自動生成:
  - title_kana を pykakasi で ローマ字化、 hyphen 区切り
  - 重複 slug は suffix '-2', '-3' 等

出力:
  - data/manga.draft-2000/*.yml (= 主 dir 不干渉)
"""

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml
import pykakasi

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
OUT_DIR = ROOT / "data" / "manga.draft-2000"

TARGET_COUNT = 2000

# 関連書 / 非漫画 prefix で title 始まったら drop
# (= _promote-bulk-v2.py の DROP_TITLE_PREFIX_PATTERNS と同期)
DROP_TITLE_PATTERNS = [
    "テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
    "劇場版", "映画", "OVA",
    "ノベライズ", "ノベル", "小説",
]
# title 内に 含まれたら drop
# (= _promote-bulk-v2.py の DROP_TITLE_CONTAINS_PATTERNS と同期)
DROP_TITLE_CONTAINS = [
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

KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}

# brand (= MADB imprint) → magazine key (= data/magazines.yml master)
# 確度高い 1対1 mapping のみ。 曖昧 (= 同 brand で 複数 magazine 可能) は 入れない。
# normalize_imprint() で 中黒/空白 strip 後の key (= e.g. 'ジャンプ・コミックス' → 'ジャンプコミックス')。
BRAND_TO_MAGAZINE = {
    # 少年週刊
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
    "SHONENCHAMPIONCOMICS少年チャンピオンコミックス": "champion",
    # 少年月刊
    "ガンガンコミックス": "gangan",
    "Gangancomics": "gangan",
    "角川コミックスエース": "shonen-ace",
    "コミックボンボン": "comic-bonbon",
    "月刊少年マガジン": "monthly-shonen-magazine",
    "別冊少年マガジン": "bessatsu-shonen-magazine",
    # ヤング週刊
    "ヤングジャンプコミックス": "weekly-young-jump",
    "YOUNGJUMPCOMICS": "weekly-young-jump",
    "ヤングマガジンKC": "weekly-young-magazine",
    "ヤンマガKC": "weekly-young-magazine",
    "ヤングサンデーコミックス": "weekly-young-sunday",
    "ウルトラジャンプコミックス": "ultra-jump",
    # ビッグコミック系
    "ビッグコミックス": "big-comic",
    "BIGCOMICS": "big-comic",
    "ビッグコミックススペシャル": "big-comic",
    "BIGCOMICSSPECIAL": "big-comic",
    # 青年月刊
    "モーニングKC": "morning",
    "MorningKC": "morning",
    "アフタヌーンKC": "afternoon",
    "AfternoonKC": "afternoon",
    "アクションコミックス": "manga-action",
    "ACTIONCOMICS": "manga-action",
    # 少女
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
    # 児童
    "てんとう虫コミックス": "ciao",  # = 小学館児童向け、 主に ちゃお系
}


def _normalize_brand_for_mag(brand: str) -> str:
    """brand を BRAND_TO_MAGAZINE key 形式に正規化 (= 中黒/空白/小文字 fold)。"""
    if not brand:
        return ""
    s = brand.replace("・", "").replace("　", "").replace(" ", "").strip()
    return s


def infer_magazine_from_brand(editions: list[dict], valid_mags: set) -> str | None:
    """editions の 主 brand (= 最古 first vol を持つ edition) から magazine 推定。"""
    if not editions:
        return None
    # 各 edition の imprint で 試行 (= 最初 edition から)
    for ed in editions:
        imp = ed.get("imprint") or ""
        norm = _normalize_brand_for_mag(imp)
        if norm in BRAND_TO_MAGAZINE:
            mag = BRAND_TO_MAGAZINE[norm]
            if not valid_mags or mag in valid_mags:
                return mag
    return None

# ISBN-13 prefix → publisher key (= data/publishers.yml master と一致)
# 大半 メジャー 出版社 を カバー。 推定 不能 cases は skip。
ISBN_PUBLISHER_PREFIXES = [
    # 長い prefix を 先 (= 4-08 集英社 と 4-08-XX の sub-prefix は 先頭一致 順)
    ("978487731", "core-magazine"),
    ("978487572", "kubo-shoten"),
    ("978486554", "overlap"),
    ("978486442", "byakuya-shobo"),
    ("978486127", "mag-garden"),
    ("978484585", "leed"),
    ("978484584", "leed"),
    ("978484583", "leed"),
    ("978484582", "leed"),
    ("978484581", "leed"),
    ("978484580", "leed"),
    ("978484519", "leed"),
    ("978478598", "shonen-gahosha"),
    ("978478594", "shonen-gahosha"),
    ("978479861", "hobby-japan"),
    ("978479860", "hobby-japan"),
    ("978477323", "kaiohsha"),
    ("978477081", "line-digital-frontier"),
    ("978477080", "line-digital-frontier"),
    ("978477077", "line-digital-frontier"),
    ("978479262", "seirinkogeisha"),
    ("978478754", "square-enix"),
    ("978478753", "square-enix"),
    ("978478752", "square-enix"),
    ("978478751", "square-enix"),
    ("978478750", "square-enix"),
    ("978483874", "magazine-house"),
    ("978483873", "magazine-house"),
    ("978483872", "magazine-house"),
    ("978483871", "magazine-house"),
    ("978480197", "tatsumi"),
    ("978480198", "tatsumi"),
    ("978480199", "takeshobo"),
    ("978480192", "takeshobo"),
    ("978480193", "takeshobo"),
    ("978480194", "takeshobo"),
    ("978480195", "takeshobo"),
    ("978482116", "bunkasha"),
    ("978482113", "bunkasha"),
    ("978482111", "bunkasha"),
    ("978483224", "houbunsha"),
    ("978483222", "houbunsha"),
    ("978483223", "houbunsha"),
    ("978483444", "gentosha-comics"),
    ("978483447", "gentosha-comics"),
    ("978483449", "gentosha-comics"),
    # 拡張 prefix (= G.17 publisher 推定救済)
    ("9784757", "enterbrain"),
    ("9784758", "enterbrain"),
    ("9784785", "shonen-gahosha"),
    ("9784801", "takeshobo"),
    ("9784800", "takeshobo"),
    ("9784812", "futabasha"),
    ("9784814", "square-enix"),
    ("9784821", "bunkasha"),
    ("9784832", "shonen-gahosha"),
    ("9784834", "furebel-kan"),
    ("9784835", "kaiohsha"),
    ("9784845", "kaiohsha"),
    ("9784847", "shufu-no-tomo"),
    ("9784861", "mediafactory"),
    ("9784862", "mediafactory"),
    ("9784864", "mediafactory"),
    ("9784884", "shodensha"),
    ("9784886", "shodensha"),
    ("9784887", "shodensha"),
    ("9784591", "poplar"),
    ("9784620", "mainichi"),
    ("9784124", "chuokoron"),
    ("9784122", "chuokoron"),
    ("9784120", "chuokoron"),
    ("9784199", "tokuma"),
    ("9784198", "tokuma"),
    ("9784197", "tokuma"),
    ("9784420", "tokuma"),
    ("9784267", "kodansha"),
    ("9784334", "kobunsha"),
    ("9784391", "shufu-to-seikatsu"),
    ("9784107", "asahi-shimbun"),
    ("9784022", "asahi-shimbun"),
    ("9784257", "asahi-shimbun"),
    ("9784051", "gakken"),
    ("9784052", "gakken"),
    ("9784053", "gakken"),
    ("9784054", "gakken"),
    ("9784055", "gakken"),
    ("9784056", "gakken"),
    ("9784073", "shogakukan"),
    # 既存 main prefixes
    ("9784592", "hakusensha"),
    ("9784253", "akita"),
    ("9784408", "jitsugyo-no-nihon"),
    ("9784403", "shinshokan"),
    ("9784480", "chikuma-shobo"),
    ("9784537", "nihon-bungeisha"),
    ("9784575", "futabasha"),
    ("9784396", "shodensha"),
    ("9784596", "harpercollins-japan"),
    ("9784344", "gentosha"),
    ("978404", "kadokawa"),
    ("978404", "kadokawa"),
    ("9784091", "shogakukan"),
    ("9784093", "shogakukan"),
    ("9784092", "shogakukan"),
    ("9784094", "shogakukan"),
    ("9784099", "shogakukan"),
    ("9784065", "kodansha"),
    ("9784063", "kodansha"),
    ("9784061", "kodansha"),
    ("9784062", "kodansha"),
    ("9784064", "kodansha"),
    ("9784066", "kodansha"),
    ("9784068", "kodansha"),
    ("9784069", "kodansha"),
    ("9784088", "shueisha"),
    ("9784087", "shueisha"),
    ("9784086", "shueisha"),
    ("9784085", "shueisha"),
    ("9784084", "shueisha"),
    ("9784083", "shueisha"),
    ("9784082", "shueisha"),
    ("9784081", "shueisha"),
    ("9784080", "shueisha"),
]


def infer_publisher_from_isbn(isbn: str | None) -> str | None:
    """ISBN-13 prefix から publisher を 推定。"""
    if not isbn:
        return None
    s = re.sub(r"[^0-9]", "", isbn)
    if len(s) != 13:
        return None
    for prefix, pub in ISBN_PUBLISHER_PREFIXES:
        if s.startswith(prefix):
            return pub
    return None

# pykakasi kakasi 初期化 (= グローバル に 1 回)
_KKS = pykakasi.kakasi()


def kana_to_slug(kana: str | None) -> str:
    """カタカナ / ひらがな → slug 形式 ローマ字 (= 小文字 + hyphen 区切り)。

    space / 中黒 / 数字境界 で 分割し、 各 part を pykakasi で hepburn ローマ字化。
    非 [a-z0-9] は strip、 part 内 で 連結。 part 同士は hyphen で 結合。

    e.g. 'シンゲキ ノ キョジン' → 'shingeki-no-kyojin'
    e.g. 'ランマニブンノイチ' → 'ranmanibunnoichi' (= space なしで 連結)
    e.g. 'アマクサ1637' → 'amakusa-1637' (= 数字境界 で split)
    """
    if not kana:
        return ""
    # space / 中黒 で 分割、 さらに 数字境界 でも split (= 'アマクサ1637' → ['アマクサ','1637'])
    raw_parts = re.split(r"[\s　・]+", kana)
    parts: list[str] = []
    for p in raw_parts:
        # 数字 / 非数字 boundary で 更に split
        sub = re.split(r"(\d+)", p)
        for s in sub:
            if s:
                parts.append(s)
    romaji_parts: list[str] = []
    for p in parts:
        if re.fullmatch(r"\d+", p):
            romaji_parts.append(p)
            continue
        result = _KKS.convert(p)
        rom = "".join(r["hepburn"] for r in result).lower()
        rom = re.sub(r"[^a-z0-9]", "", rom)
        if rom:
            romaji_parts.append(rom)
    return "-".join(romaji_parts)


# 数字 → カタカナ普通読み map (= CLAUDE.md slug ルール 「ふりがな で 判断」 自動化)
# 日本語読み + 英語読み (= スリー/フォー/ツー 等 も 普通読み 扱い)
DIGIT_KANA = {
    "0": ["ゼロ", "マル", "レイ", "オウ"],
    "1": ["イチ", "ワン"],
    "2": ["ニ", "ツー"],
    "3": ["サン", "スリー"],
    "4": ["ヨン", "シ", "フォー"],
    "5": ["ゴ", "ファイブ"],
    "6": ["ロク", "シックス"],
    "7": ["ナナ", "シチ", "セブン"],
    "8": ["ハチ", "エイト"],
    "9": ["キュウ", "ク", "ナイン"],
}
# 2 桁以上 の 英語 数 reading (= 一部 のみ覆い)
DIGIT_KANA_EN_MULTI = {
    "10": ["テン"],
    "11": ["イレブン"],
    "12": ["トゥエルブ"],
    "13": ["サーティーン"],
    "14": ["フォーティーン"],
    "15": ["フィフティーン"],
    "16": ["シックスティーン"],
    "17": ["セブンティーン"],
    "18": ["エイティーン"],
    "19": ["ナインティーン"],
    "20": ["トゥエンティ"],
    "21": ["トゥエンティワン"],
    "100": ["ハンドレッド"],
    "1000": ["サウザンド"],
}


def extract_title_suffix(title: str) -> str | None:
    """title 末尾 の 「第N部」「II/III/IV/V」「2/3」 等 part 番号 を 抽出。

    返り値: '2', '3' 等 数字 string (slug suffix 用)、 無ければ None。

    e.g. 'カムイ伝全集 第2部' → '2'
         'やじきた学園道中記Ⅱ' → '2'
         'エリートヤンキー三郎 第2部' → '2'
         'うる星やつら2' → '2'
    """
    if not title:
        return None
    s = title.strip()
    # 「第N部」 (= 漢数字/算用数字)
    m = re.search(r"第([0-9０-９一二三四五六七八九十]+)部$", s)
    if m:
        g = m.group(1)
        # 算用 / 全角 → 半角
        g = re.sub(r"[０-９]", lambda x: chr(ord(x.group(0)) - 0xFEE0), g)
        if g.isdigit():
            return g
        # 漢数字 → int
        kanji_map = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
        if g in kanji_map:
            return str(kanji_map[g])
    # ローマ数字 末尾 (= Ⅰ-Ⅹ)
    m = re.search(r"([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ])$", s)
    if m:
        roman = {"Ⅰ":1,"Ⅱ":2,"Ⅲ":3,"Ⅳ":4,"Ⅴ":5,"Ⅵ":6,"Ⅶ":7,"Ⅷ":8,"Ⅸ":9,"Ⅹ":10}
        return str(roman[m.group(1)])
    return None


def slug_from_ascii_title(title: str | None) -> str:
    """title が 純 ASCII (= 'W3', 'AMAKUSA 1637', 'MAJOR') なら 直接 slug 化。

    e.g. 'W3' → 'w-3'
         'AMAKUSA 1637' → 'amakusa-1637'
         'MAJOR' → 'major'
         'H2' → 'h-2'
    """
    if not title:
        return ""
    # 非 ASCII / 非 数字 / 非 記号 が 1 つでも あれば skip (= 漢字/かな含む)
    if re.search(r"[^\x00-\x7F]", title):
        return ""
    # alpha / digit segment 抽出 (= space や punct を 区切り に)
    parts = re.findall(r"[A-Za-z]+|\d+", title)
    if not parts:
        return ""
    return "-".join(p.lower() for p in parts)


def slug_from_alt_en(alt_en: str | None) -> str:
    """英語タイトル → slug (lowercase + hyphen)。

    e.g. 'One Piece' → 'one-piece'
         'Dragon Ball' → 'dragon-ball'
         "JoJo's Bizarre Adventure" → 'jojos-bizarre-adventure'
         'Haikyuu!!' → 'haikyuu'
         'Maison Ikkoku' → 'maison-ikkoku'
    """
    if not alt_en:
        return ""
    s = alt_en.strip()
    # apostrophe / 句読点 を strip
    s = re.sub(r"['!?.,]", "", s)
    # 非 ASCII alphanumeric を hyphen 化
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def gen_digit_readings(digits: str) -> set[str]:
    """digit string → 「普通読み」 variant のカタカナ set。 日本語 + 英語読み 含む。

    e.g. '21' → {'ニジュウイチ', 'トゥエンティワン', 'ニイチ' 等}
         '4' → {'ヨン', 'シ', 'フォー'}
         '3' → {'サン', 'スリー'}
         '707' → {'ナナマルナナ', 'セブンゼロセブン' 等}
    """
    readings: set[str] = set()
    # digit-by-digit reading (= 707 → 'ナナマルナナ', 'セブンゼロセブン')
    def expand(idx: int, acc: str) -> None:
        if idx == len(digits):
            readings.add(acc)
            return
        for kana in DIGIT_KANA.get(digits[idx], []):
            expand(idx + 1, acc + kana)
    expand(0, "")
    # 日本語 数 単位 reading (= 21 → 'ニジュウイチ', 100 → 'ヒャク')
    try:
        n = int(digits)
        if n < 10:
            for k in DIGIT_KANA[str(n)]:
                readings.add(k)
        elif n < 20:
            ones = n - 10
            if ones == 0:
                readings.add("ジュウ")
            else:
                for k in DIGIT_KANA[str(ones)]:
                    if k in {"ワン", "ツー", "スリー", "フォー", "ファイブ",
                             "シックス", "セブン", "エイト", "ナイン"}:
                        continue  # 英語読みは ジュウ 接頭しない
                    readings.add("ジュウ" + k)
        elif n < 100:
            tens = n // 10
            ones = n % 10
            tens_kana = DIGIT_KANA[str(tens)][0] + "ジュウ"
            if ones == 0:
                readings.add(tens_kana)
            else:
                for k in DIGIT_KANA[str(ones)]:
                    if k in {"ワン", "ツー", "スリー", "フォー", "ファイブ",
                             "シックス", "セブン", "エイト", "ナイン"}:
                        continue
                    readings.add(tens_kana + k)
        elif n < 1000:
            hundreds = n // 100
            rest = n % 100
            h_variant = "ヒャク" if hundreds == 1 else DIGIT_KANA[str(hundreds)][0] + "ヒャク"
            if rest == 0:
                readings.add(h_variant)
            else:
                for sub in gen_digit_readings(str(rest)):
                    readings.add(h_variant + sub)
    except ValueError:
        pass
    # 英語 数 reading (= 17 → 'セブンティーン', 100 → 'ハンドレッド')
    if digits in DIGIT_KANA_EN_MULTI:
        for k in DIGIT_KANA_EN_MULTI[digits]:
            readings.add(k)
    return readings


def title_part_to_kana(text: str) -> str:
    """title segment (= 漢字混じり 可) を カタカナ に。 pykakasi で 標準読み。

    特殊読み (= 「黄金郷」 = 'エルドラド') は 通常 dict にないので 標準読み (= 'コガネサト' 等)
    を返す。 alignment check で この差異 を 利用 して 特殊読み判定。
    """
    if not text:
        return ""
    result = _KKS.convert(text)
    out = "".join(r["kana"] for r in result)
    return re.sub(r"[\s　]+", "", out)


def title_to_slug_keep_digit(title: str, kana: str) -> str | None:
    """title に 数字 を 含み、 ふりがな (= kana) が 「普通数字読み」 なら、
    title を walk し digit を keep + 非数字部 を pykakasi で ローマ字化。

    Alignment check: title を 数字 / 非数字 segment に 分割し、
    各 segment が 実 kana に 対応するか 確認:
    - 非数字 segment: pykakasi で kana 化 し、 実 kana の 対応 position と 比較
    - 数字 segment: literal '数字' or reading が 対応 position に あるか 確認
    アラインメント 成功 → digit keep。 失敗 → 特殊読み 認定で fallback。

    e.g. 'ペルソナ4' kana='ペルソナフォー' → 'perusona-4' (= 'ペルソナ' align + 'フォー' = 4)
    e.g. '7つの黄金郷' kana='ナナツノエルドラド' → None (= 'コガネサト' vs 'エルドラド' で align失敗)
    """
    if not title or not re.search(r"\d", title):
        return None
    kana_compact = re.sub(r"[\s　]+", "", kana or "")
    if not kana_compact:
        return None
    # title を 数字 / 非数字 で split
    parts: list[tuple[str, bool]] = []
    cur, cur_is_digit = "", None
    for c in title:
        is_d = c.isdigit()
        if cur_is_digit is None:
            cur, cur_is_digit = c, is_d
        elif cur_is_digit == is_d:
            cur += c
        else:
            parts.append((cur, cur_is_digit))
            cur, cur_is_digit = c, is_d
    if cur:
        parts.append((cur, cur_is_digit))
    # Alignment check
    pos = 0
    for text, is_d in parts:
        if is_d:
            # 数字 segment: literal or reading match at pos
            if kana_compact[pos:pos + len(text)] == text:
                pos += len(text)
                continue
            readings = gen_digit_readings(text)
            found = None
            for r in sorted(readings, key=lambda x: -len(x)):
                if kana_compact[pos:pos + len(r)] == r:
                    found = r
                    break
            if found:
                pos += len(found)
            else:
                return None  # alignment 失敗
        else:
            # 非数字 segment: pykakasi → 実 kana startswith ?
            expected = title_part_to_kana(text)
            if not expected:
                continue  # 空 (= 全 punctuation 等) は skip
            if kana_compact[pos:pos + len(expected)] == expected:
                pos += len(expected)
            else:
                return None
    if pos != len(kana_compact):
        # 余り kana あり → align 失敗
        return None
    # 全 align 成功 → walk して slug 構築
    slug_parts: list[str] = []
    for text, is_d in parts:
        if is_d:
            slug_parts.append(text)
        else:
            rom = "".join(r["hepburn"] for r in _KKS.convert(text)).lower()
            rom = re.sub(r"[^a-z0-9]", "", rom)
            if rom:
                slug_parts.append(rom)
    return "-".join(p for p in slug_parts if p)


def title_to_romaji(kana: str | None) -> str:
    """title_romaji 生成 (= 全小文字 + space 区切り)。"""
    if not kana:
        return ""
    parts = [p for p in re.split(r"[\s　・]+", kana) if p]
    romaji_parts: list[str] = []
    for p in parts:
        result = _KKS.convert(p)
        rom = "".join(r["hepburn"] for r in result).lower()
        rom = re.sub(r"[^a-z0-9]", "", rom)
        if rom:
            romaji_parts.append(rom)
    return " ".join(romaji_parts)


def title_passes_filter(title: str) -> bool:
    if not title:
        return False
    for pat in DROP_TITLE_PATTERNS:
        if title.startswith(pat):
            return False
    for pat in DROP_TITLE_CONTAINS:
        if pat in title:
            return False
    return True


def _normalize_title_for_dedup(title: str) -> str:
    """title を 正規化 (= 大小揃え + 中黒/句読点 strip + 全角/半角 揺れ 吸収)。

    e.g. 'BLACK JACK', 'Black Jack', 'ブラック・ジャック' → 同じ key (kana 一致 必要)
    e.g. 'おーい!竜馬', 'お～い！竜馬', 'お～い!竜馬' → 同じ
    """
    if not title:
        return ""
    s = title.lower()
    # 中黒 / 全半角空白 / 全半角! / ★❤❣ / ASCII 句読点 strip
    s = re.sub(r"[・\s　!！?？★☆♥❤❣◆◇♪～~・，,．.。]", "", s)
    # 全角 ASCII → 半角 (= 簡略)
    s = re.sub(r"[Ａ-Ｚａ-ｚ０-９]", lambda m: chr(ord(m.group(0)) - 0xFEE0), s)
    return s


def select_candidates(con: sqlite3.Connection, limit: int) -> list[dict]:
    """完結 推定 series を 抽出。 ranking 順 で limit 件 返す。"""
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    types_in = ",".join("?" for _ in KEEP_EDITION_TYPES)
    rows = cur.execute(
        f"""
        SELECT s.id, s.title, s.subtitle, s.title_kana, s.subtitle_kana, s.qid,
               s.title_official_en,
               s.adult_score, s.source, s.series_key,
               MAX(v.release_date) AS last_date,
               MIN(v.release_date) AS first_date,
               COUNT(DISTINCT v.id) AS vol_count
        FROM series s
        JOIN editions e ON e.series_id = s.id
        JOIN volumes v ON v.edition_id = e.id
        WHERE s.adult_score < 3
          AND e.type IN ({types_in})
          AND v.release_date IS NOT NULL
          AND v.number > 0
        GROUP BY s.id
        HAVING vol_count >= 5
           AND SUBSTR(last_date, 1, 4) <= '2020'
        ORDER BY (CASE WHEN s.qid IS NOT NULL THEN 100 ELSE 0 END) + vol_count DESC
        LIMIT ?
        """,
        list(KEEP_EDITION_TYPES) + [limit * 5],  # 5x で 取得 後 filter
    ).fetchall()
    out = []
    seen_titles = set()
    for r in rows:
        if not title_passes_filter(r["title"]):
            continue
        if not r["title_kana"]:
            continue  # kana 必須
        # 同一作品 (= 大小違い / 中黒違い / ASCII vs カタカナ) は 1 件 のみ
        # dedup key: (title_kana_norm, part_suffix)
        # - kana_norm: 表記揺れ (= 'BLACK JACK','ブラック・ジャック' 共 kana 同じ) 吸収
        # - part_suffix: 続編 (= 「第N部」「II」) は 別 entry 保持
        kana_norm = re.sub(r"[\s　]", "", r["title_kana"] or "")
        part = extract_title_suffix(r["title"] or "") or "main"
        key = (kana_norm, part)
        if key in seen_titles:
            continue
        seen_titles.add(key)
        out.append(dict(r))
        if len(out) >= limit:
            break
    return out


def build_yml_for_candidate(
    con: sqlite3.Connection,
    cand: dict,
    seed3: dict,
    valid_pubs: set,
    valid_mags: set,
    valid_gens: set,
    related_finder,
    editions_loader,
    authors_loader,
) -> dict | None:
    """1 candidate を yml dict に。"""
    series_row = cand  # cand already has all needed fields
    related_ids = related_finder(con, series_row)
    editions = editions_loader(con, related_ids)
    if not editions:
        return None
    authors = authors_loader(con, series_row["id"])
    seed_entry = seed3.get(series_row["series_key"])

    # title_kana strip space (= 必須 field、 空なら skip)
    raw_kana = series_row.get("title_kana") or ""
    title_kana = re.sub(r"[\s　]+", "", raw_kana)
    if not title_kana:
        return None  # title_kana 不明 → skip
    title_romaji = title_to_romaji(raw_kana)
    if not title_romaji:
        return None  # title_romaji 推定不能 → skip

    # subtitle 空 でも edition 名 strip 不要 (= 種3 直接出力)
    sub = series_row.get("subtitle")
    EDITION_NAME_SUBTITLES = {"新装再編版", "新装版", "完全版", "愛蔵版", "文庫版",
                              "ワイド版", "デラックス", "新装新版", "リニューアル版",
                              "廉価版", "新装版コミックス", "復刻版"}
    if sub and sub in EDITION_NAME_SUBTITLES:
        sub = None

    # year
    all_years = []
    for ed in editions:
        for v in ed["volumes"]:
            d = v.get("release_date")
            if d and len(d) >= 4:
                try:
                    all_years.append(int(d[:4]))
                except ValueError:
                    pass
    year_started = min(all_years) if all_years else 2000
    year_ended = None
    if editions:
        first_ed_years = []
        for v in editions[0]["volumes"]:
            d = v.get("release_date")
            if d and len(d) >= 4:
                try:
                    first_ed_years.append(int(d[:4]))
                except ValueError:
                    pass
        first_ed_years.sort()
        while len(first_ed_years) > 5:
            if first_ed_years[-1] - first_ed_years[-2] > 5:
                first_ed_years.pop()
            else:
                break
        if first_ed_years:
            year_ended = max(first_ed_years)

    status = (seed_entry or {}).get("status") or "completed"  # 抽出時点で 完結扱い
    if status == "ongoing":
        year_ended = None

    writers, originals = [], []
    for a in authors:
        if a["role"] == "original_author":
            originals.append({"name": a["name"], "role": "writer"})
        else:
            writers.append({"name": a["name"], "role": a["role"]})
    if not writers:
        writers = [{"name": "(unknown)", "role": "writer_artist"}]

    pub_cand = (seed_entry or {}).get("publisher")
    if pub_cand and valid_pubs and pub_cand not in valid_pubs:
        pub_cand = None
    # ISBN prefix から publisher 推定 (= 種3 fill 漏れ 補完)
    if not pub_cand:
        for ed in editions:
            for v in ed["volumes"]:
                p = infer_publisher_from_isbn(v.get("isbn13"))
                if p and (not valid_pubs or p in valid_pubs):
                    pub_cand = p
                    break
            if pub_cand:
                break

    mag_cand = (seed_entry or {}).get("magazine")
    if mag_cand and valid_mags and mag_cand not in valid_mags:
        mag_cand = None
    # brand → magazine 推定 (= 種3 fill 漏れ 補完)
    if not mag_cand:
        mag_cand = infer_magazine_from_brand(editions, valid_mags)

    demographic = (seed_entry or {}).get("demographic") or "shounen"

    genres_cand = (seed_entry or {}).get("genres") or ["drama"]
    if valid_gens:
        filtered = [g for g in genres_cand if g in valid_gens]
        genres_cand = filtered or ["drama"]

    o: dict = {
        "slug": cand["__slug__"],
        "title": series_row["title"],
        "title_kana": title_kana,
        "title_romaji": title_romaji,
    }
    if sub:
        o["subtitle"] = sub
        if series_row.get("subtitle_kana"):
            o["subtitle_kana"] = re.sub(r"[\s　]+", "", series_row["subtitle_kana"])
    o["year_started"] = year_started
    o["year_ended"] = year_ended
    o["status"] = status
    o["authors"] = writers
    o["original_authors"] = originals
    if not pub_cand:
        return None  # publisher 推定不能 → skip
    o["publisher"] = pub_cand
    o["magazine"] = mag_cand
    o["demographic"] = demographic
    o["genres"] = genres_cand
    o["synopsis"] = (seed_entry or {}).get("synopsis") or ""
    anime_adapted = (seed_entry or {}).get("anime_adapted")
    if anime_adapted is not None:
        o["anime_adapted"] = anime_adapted
    if series_row.get("qid"):
        o["wikidata_qid"] = series_row["qid"]

    # editions 出力 (= type/label/imprint/volumes 構造)
    cleaned_eds = []
    for ed in editions:
        vols_out = []
        for v in ed["volumes"]:
            vo = {"number": v["number"]}
            if v.get("volume_label"):
                vo["volume_label"] = v["volume_label"]
            vo["asin"] = v.get("asin")
            vo["isbn13"] = str(v["isbn13"]) if v.get("isbn13") else None
            vo["cover_url"] = v.get("cover_url")
            vo["release_date"] = v.get("release_date") or None
            vols_out.append(vo)
        ce = {"type": ed["type"], "label": ed.get("label")}
        if ed.get("imprint"):
            ce["imprint"] = ed["imprint"]
        ce["volumes"] = vols_out
        cleaned_eds.append(ce)
    o["editions"] = cleaned_eds
    return o


def main():
    import importlib.util
    # 既存 promote logic を import (= find_related_series_ids, get_editions_with_volumes, get_authors)
    spec = importlib.util.spec_from_file_location("p", ROOT / "scripts" / "_promote-bulk-v2.py")
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)

    print(f"loading {SEED3} ...", file=sys.stderr)
    with SEED3.open("r", encoding="utf-8") as f:
        d = yaml.safe_load(f)
    seed3 = {e["key"]: e for e in d["series"]}
    print(f"  entries: {len(seed3)}", file=sys.stderr)

    valid_pubs, valid_mags, valid_gens = pm.load_master_keys()
    print(
        f"  master: pubs={len(valid_pubs)} mags={len(valid_mags)} gens={len(valid_gens)}",
        file=sys.stderr,
    )

    con = sqlite3.connect(DB)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in OUT_DIR.glob("*.yml"):
        p.unlink()

    print(f"[step 1] parent_map 構築...", file=sys.stderr)
    parent_map = pm.build_parent_map(con)
    print(f"  spinoff: {len(parent_map)}", file=sys.stderr)

    print(f"[step 2] 候補抽出...", file=sys.stderr)
    # 余裕持って 3x 取得 (= publisher 推定 不能 / kana 空 等で skip された場合 backfill)
    cands = select_candidates(con, TARGET_COUNT * 3)
    print(f"  候補: {len(cands)}", file=sys.stderr)

    # spinoff drop
    cands = [c for c in cands if c["id"] not in parent_map or c["vol_count"] >= 10]
    print(f"  spinoff 除外後: {len(cands)}", file=sys.stderr)

    # slug 自動生成 + 重複 handling
    print(f"[step 3] slug 生成...", file=sys.stderr)
    slug_count: dict[str, int] = defaultdict(int)
    for c in cands:
        # slug 優先順:
        # 1. 種3 entry の slug field (= 手動 override)
        # 2. 種3 alternative_titles.en or DB title_official_en (= 'one-piece' 等 外来語)
        # 3. title が 純 ASCII (= 'W3', 'MAJOR', 'AMAKUSA 1637' 等) → 直接 slug 化
        # 4. 数字 含む title で 普通数字読み (= 英語含む) なら digit keep + alignment 検証
        # 5. kana → ローマ字 fallback (= 'ranma-nibunnoichi' 等)
        seed_entry = seed3.get(c["series_key"]) if c.get("series_key") else None
        base_slug = (seed_entry or {}).get("slug") or ""
        if not base_slug:
            alt_en = (seed_entry or {}).get("alternative_titles", {}).get("en") if seed_entry else None
            official_en = c.get("title_official_en") or None
            en_name = alt_en or official_en
            base_slug = slug_from_alt_en(en_name) if en_name else ""
        if not base_slug:
            base_slug = slug_from_ascii_title(c["title"])
        if not base_slug:
            base_slug = title_to_slug_keep_digit(c["title"] or "", c["title_kana"] or "")
        if not base_slug:
            base_slug = kana_to_slug(c["title_kana"])
        if not base_slug:
            # title から ASCII 部分 抽出 fallback
            base_slug = re.sub(r"[^a-z0-9]+", "-", (c["title"] or "").lower()).strip("-")
        if not base_slug:
            base_slug = f"series-{c['id']}"
        # title 末尾 「第N部」「II」 等 part 番号 を slug suffix に 反映
        # (= '第2部' → '-2' で 続編 を 区別、 '-2'/'-3' 自動 suffix より 意味あり)
        part_suffix = extract_title_suffix(c["title"] or "")
        if part_suffix and not base_slug.endswith(f"-{part_suffix}"):
            base_slug = f"{base_slug}-{part_suffix}"
        slug_count[base_slug] += 1
        if slug_count[base_slug] == 1:
            c["__slug__"] = base_slug
        else:
            c["__slug__"] = f"{base_slug}-{slug_count[base_slug]}"

    print(f"[step 4] yml 生成 (= {TARGET_COUNT} 達成まで)...", file=sys.stderr)
    stats = {"written": 0, "no_editions": 0, "error": 0}
    for i, c in enumerate(cands):
        if stats["written"] >= TARGET_COUNT:
            print(f"  達成: {TARGET_COUNT} 件、 残り 候補 {len(cands)-i} は skip", file=sys.stderr)
            break
        if i % 500 == 0:
            print(f"  progress: written={stats['written']} skipped={stats['no_editions']} scanned={i}/{len(cands)}", file=sys.stderr)
        try:
            yml_dict = build_yml_for_candidate(
                con, c, seed3, valid_pubs, valid_mags, valid_gens,
                pm.find_related_series_ids,
                pm.get_editions_with_volumes,
                pm.get_authors,
            )
        except Exception as e:
            stats["error"] += 1
            continue
        if not yml_dict:
            stats["no_editions"] += 1
            continue
        out_path = OUT_DIR / f"{c['__slug__']}.yml"
        with out_path.open("w", encoding="utf-8") as f:
            f.write("# Auto-generated by scripts/_extract-top-completed.py\n")
            yaml.dump(yml_dict, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        stats["written"] += 1

    print(f"\n=== stats ===", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"\nwrote {stats['written']} yml to {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
