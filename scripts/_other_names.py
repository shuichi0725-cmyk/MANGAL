"""他言語名(other_names)の組み立て = 作品頁の「英語/中国語/韓国語…」欄の正本ロジック。

★2026-10-19 新設(らんま1/2「他言語がハングルしかない」報告 → 全頁見直し。 ユーザ裁定 A1 =
  AIが作った訳題は表示しない)。 promote(_promote-bulk-v2.py)と既存頁への一括適用
  (_apply-other-names.py)の両方がここを呼ぶ = 規則は1か所。

出所(言語ラベルが確かなものだけ):
  英語   = AniList title.english(公式英題) > Wikidata en > 種3/MADB/NDL の欧文併記題
           ★AI訳題(data/seeds/_fills の alternative_titles.en = 旧slug規則のための埋め草)は使わない
           ★日本語題のローマ字(AniList romaji / title_romaji)と同じ綴りは、公式英題以外どの言語でも出さない
  他言語 = Wikidata rdfs:label(作品QID経由・言語コード付き)+ AniList synonyms を文字種で判定
           (ハングル=韓国語 / タイ文字=タイ語 / 漢字のみで題に無い字を含む=中国語)
  alt    = AniList synonyms のラテン文字・キリル文字(言語が判らない)=「その他の表記」

出力 = [{"lang": "en", "name": "Ranma ½"}, {"lang": "zh-hans", "name": "乱马½"}, ...](LANG_ORDER 順)。
空でも [] を返す(= 処理済みの印。 表示側は other_names 欄の有無で新旧表示を切り替える)。
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANILIST_DUMP = ROOT / ".cache" / "anilist-manga-dump-v3.jsonl.gz"
ANILIST_TITLES = ROOT / ".cache" / "anilist-titles.json"   # dump から作る軽量版(dump が新しければ作り直す)
WORK_QID = ROOT / ".cache" / "work-qid-map.json"           # _fetch-work-qid.py
WORK_LABELS = ROOT / ".cache" / "work-labels.json"         # _fetch-work-labels.py
FILLS_DIR = ROOT / "data" / "seeds" / "_fills"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"

# 表示する言語(順番 = 表示順)。 これ以外の Wikidata ラベルは捨てる(少数言語・記事名の写しが多い)。
LANG_ORDER = ["en", "zh-hans", "zh-hant", "zh", "ko", "th", "vi", "id",
              "fr", "de", "it", "es", "pt", "ru", "pl", "ar", "alt"]
_RANK = {l: i for i, l in enumerate(LANG_ORDER)}
ZH_HANS = {"zh-hans", "zh-cn", "zh-sg", "zh-my"}
ZH_HANT = {"zh-hant", "zh-tw", "zh-hk", "zh-mo"}
WD_KEEP = {"zh", "ko", "th", "vi", "id", "fr", "de", "it", "es", "pt", "ru", "pl", "ar"} | ZH_HANS | ZH_HANT

KANA = re.compile(r"[぀-ヿㇰ-ㇿｦ-ﾟ]")
HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
HANGUL = re.compile(r"[가-힯ᄀ-ᇿ㄰-㆏]")
THAI = re.compile(r"[฀-๿]")
LATIN_OR_CYR = re.compile(r"[A-Za-zÀ-ɏЀ-ӿ]")
CYR = re.compile(r"[Ѐ-ӿ]")
ARAB = re.compile(r"[؀-ۿ]")
# 非ラテン文字の言語は、その文字を含むラベルだけ採る(露語欄に「Sousou no Frieren」等のローマ字の写しが入るため)
SCRIPT_OF = {"zh-hans": HAN, "zh-hant": HAN, "zh": HAN, "ko": HANGUL, "th": THAI, "ru": CYR, "ar": ARAB}
# Wikidata の記事名由来の曖昧さ回避「(manga)」「(манга)」等は落とす
WD_PAREN = re.compile(r"\s*[（(][^()（）]*(manga|манг|漫画|マンガ|comic|anime|аниме)[^()（）]*[)）]\s*$", re.I)
# 併記題に混ざるレーベル名・版名・年(MADB の「=」右側の誤り)
JUNK_EN = re.compile(r"(^\d+$)|(^(special|manga|all in one)$)|\b(label|edition|selection|collection|bunko|comics?)\b", re.I)


def _n(s) -> str:
    """重複判定キー(NFKC・小文字・空白記号除去。 ½ と 1/2 は同じになる)。"""
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", str(s or ""))).lower()


def _rk(s) -> str:
    """ローマ字比較キー(発音記号・長音の書き分けを潰す: Sōsō = Sousou = Soso)。"""
    s = unicodedata.normalize("NFKD", str(s or "")).lower()
    s = re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))
    for a, b in (("ou", "o"), ("oo", "o"), ("uu", "u"), ("aa", "a"), ("ii", "i"), ("ee", "e"), ("wo", "o")):
        s = s.replace(a, b)
    return s


def _fill_title(key: str) -> str:
    """_fills のキー(name:作者|name:題|sub:副題 / Q123|題)から題を取り出す。"""
    parts = [p for p in key.split("|") if not p.startswith(("sub:", "qid:"))]
    if not parts:
        return ""
    t = parts[-1]
    return t[5:] if t.startswith("name:") else t


def _load_anilist_titles() -> dict:
    """{anilist_id(str): [english, romaji, synonyms]}。 dump(~数百MB)を毎回読まないよう軽量版をキャッシュ。"""
    if ANILIST_TITLES.exists() and (not ANILIST_DUMP.exists()
                                    or ANILIST_TITLES.stat().st_mtime >= ANILIST_DUMP.stat().st_mtime):
        return json.loads(ANILIST_TITLES.read_text(encoding="utf-8"))
    out = {}
    if ANILIST_DUMP.exists():
        with gzip.open(ANILIST_DUMP, "rt", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                t = d.get("title") or {}
                out[str(d["id"])] = [t.get("english"), t.get("romaji"), d.get("synonyms") or []]
        ANILIST_TITLES.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def _load_ai_en() -> tuple[dict, set]:
    """AIが埋めた英題 = ({seed3キー: {英題,...}}, {(題, 英題)})。 キーで引けない頁(既存yml)は題+値で引く。"""
    keys, pairs = {}, set()
    for fp in glob.glob(str(FILLS_DIR / "*.json")):
        try:
            d = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            en = isinstance(v, dict) and isinstance(v.get("alternative_titles"), dict) and v["alternative_titles"].get("en")
            if en:
                keys.setdefault(k, set()).add(str(en).strip())
                pairs.add((_fill_title(k), str(en).strip()))
    return keys, pairs


def _load_seed3_en_owners() -> dict:
    """{英題: {種3キー,...}}(種3 33MB を正規表現で1秒)。 種3キーを持たない既存頁のAI判定に使う。"""
    if not SEED3.exists():
        return {}
    import yaml
    txt = SEED3.read_text(encoding="utf-8")
    owners: dict = {}
    for mm in re.finditer(r"^- key: (.+?)\n(.*?)(?=^- key: |\Z)", txt, re.S | re.M):
        e = re.search(r"^  alternative_titles:\n    en: (.+)$", mm.group(2), re.M)
        if not e or e.group(1).strip() == "null":
            continue
        try:
            v = str(yaml.safe_load(e.group(1).strip()))
        except Exception:
            v = e.group(1).strip()
        try:
            k = str(yaml.safe_load(mm.group(1).strip()))
        except Exception:
            k = mm.group(1).strip()
        owners.setdefault(v.strip(), set()).add(k)
    return owners


class Sources:
    """出所データ一式(重いので1回だけ読む)。"""

    def __init__(self):
        self.anilist = _load_anilist_titles()
        qmap = json.loads(WORK_QID.read_text(encoding="utf-8")) if WORK_QID.exists() else {}
        self.qid_by_anilist = {k: v["qid"] for k, v in qmap.items() if v and v.get("qid")}
        self.labels = json.loads(WORK_LABELS.read_text(encoding="utf-8")) if WORK_LABELS.exists() else {}
        self.ai_keys, self.ai_pairs = _load_ai_en()
        # 題の表記ゆれ吸収用: {AI英題: {正規化した題,...}}
        self.ai_titles_by_en: dict = {}
        for k, vs in self.ai_keys.items():
            for v in vs:
                self.ai_titles_by_en.setdefault(v, set()).add(_n(_fill_title(k)))
        self.seed3_en_owners = _load_seed3_en_owners()

    def summary(self) -> str:
        return (f"AniList題 {len(self.anilist):,} / 作品QID {len(self.qid_by_anilist):,} / "
                f"Wikidataラベル {len(self.labels):,}作 / AI英題 {len(self.ai_pairs):,}")


def is_ai_en(src: Sources, title: str, en: str, seed3_key: str | None = None) -> bool:
    en = str(en or "").strip()
    if not en:
        return False
    if seed3_key and en in src.ai_keys.get(seed3_key, ()):
        return True                           # 種3キー+値の一致(後から手で直した英題は値が違うので AI 扱いしない)
    if (str(title or ""), en) in src.ai_pairs:
        return True
    if seed3_key:
        return False                          # promote = 種3キーが判っている時はキー判定が正(下の推定は使わない)
    # ↓ 種3キーを持たない既存頁(_apply-other-names.py)向けの推定
    if _n(title) in src.ai_titles_by_en.get(en, ()):
        return True                           # 題の表記ゆれ(空白・中黒・全半角)違いのAI埋め
    owners = src.seed3_en_owners.get(en)
    if owners and all(en in src.ai_keys.get(k, ()) for k in owners):
        return True                           # この英題を持つ種3項目が全部AI埋め
    return False


def build(page: dict, src: Sources, seed3_key: str | None = None) -> list[dict]:
    title = str(page.get("title") or "")
    seen = {_n(title), _n(page.get("title_kana")), _n(page.get("subtitle"))} - {""}
    title_han = set(HAN.findall(title + str(page.get("subtitle") or "")))
    out: list[tuple[str, str]] = []
    aid = page.get("anilist_id")
    al = src.anilist.get(str(aid)) if aid else None
    english, romaji, synonyms = (al or [None, None, []])
    # 日本語題のローマ字(他言語名ではない)= AniList romaji / 頁の title_romaji
    romaji_keys = {_rk(romaji), _rk(page.get("title_romaji"))} - {""}

    def add(lang: str, name, romaji_ok: bool = False):
        name = re.sub(r"\s+", " ", str(name or "")).strip()
        k = _n(name)
        if not k or k in seen:
            return
        if lang in SCRIPT_OF and not SCRIPT_OF[lang].search(name):
            return
        if not romaji_ok and _rk(name) in romaji_keys:
            return
        seen.add(k)
        out.append((lang, name))

    qid = page.get("work_wikidata_qid") or (src.qid_by_anilist.get(str(aid)) if aid else None)
    wl = src.labels.get(qid) or {} if qid else {}

    # ── 英語 ──
    if english:
        add("en", english, romaji_ok=True)   # 公式英題はローマ字綴りでも採る(Kimi ni Todoke 等)
    wd_en = wl.get("en")
    if wd_en and not KANA.search(wd_en) and LATIN_OR_CYR.search(wd_en):
        add("en", WD_PAREN.sub("", wd_en))
    alt_en = str((page.get("alternative_titles") or {}).get("en") or "").strip()
    if (alt_en and not is_ai_en(src, title, alt_en, seed3_key)
            and not JUNK_EN.search(alt_en) and LATIN_OR_CYR.search(alt_en)):
        add("en", alt_en)

    # ── Wikidata の他言語(言語コード付き)──
    zh_plain = []
    for lang, lab in wl.items():
        if lang not in WD_KEEP:
            continue
        lab = WD_PAREN.sub("", lab)
        if lang in ZH_HANS:
            add("zh-hans", lab)
        elif lang in ZH_HANT:
            add("zh-hant", lab)
        elif lang == "zh":
            zh_plain.append(lab)              # 簡/繁の明示ラベルを先に通してから(重複は seen が落とす)
        else:
            add(lang, lab)
    for lab in zh_plain:
        add("zh", lab)

    # ── AniList synonyms(言語タグが無いので文字種で判定)──
    for s in synonyms or []:
        s = str(s).strip()
        if not s or KANA.search(s):
            continue                          # 仮名入り = 日本語の別名(表示側の「別名」欄)
        if HANGUL.search(s):
            add("ko", s)
        elif THAI.search(s):
            add("th", s)
        elif HAN.search(s):
            if set(HAN.findall(s)) <= title_han:
                continue                      # 題に在る漢字だけ = 日本語の略称・部分題
            add("zh", s)
        elif LATIN_OR_CYR.search(s):
            add("alt", s)
        # アラビア文字・ヘブライ文字など = 言語を決められないので出さない

    out.sort(key=lambda x: _RANK.get(x[0], 99))   # 安定ソート = 言語内は出所の優先順のまま
    return [{"lang": l, "name": n} for l, n in out]
