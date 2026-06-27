"""共通機構: 「題＋巻番号 → 楽天item照合」 (発売日逆行/巻抜け の両方が使う)

設計 (= [[harvest_based_fix_mechanism]]):
- 楽天harvest生 = .cache/rakuten-isbn-delta.jsonl(828MB) + .cache/rakuten-isbn.jsonl(373MB)
- ★安全規則: 巻トークンを末尾から剥がした「残差題」が **target題と完全一致(norm)** の時だけ採用。
  → スピンオフ/外伝/データファイル/超全集 を自然に除外 (= 残差題が一致しない)。
- ★ゴルゴ13の罠: 末尾数字を素朴に巻番号扱いすると題が壊れる。
  巻トークンは「（N）/（N巻）/（volume N）」 か 「空白+数字(末尾)」のみ。空白の無い末尾数字(=題の一部)は剥がさない。
- salesDate(和文) → sortable (Y,M,D)。複数printing(=再版)から **最古** を採る。

再利用API:
  norm(s)                  : NFKC + 記号/空白除去 + lower (題キー)
  parse_vol(nfkc_title)    : (vol:int|None, residual_base:str)  末尾巻トークン剥がし
  parse_salesdate(s)       : (Y,M,D) tuple or None。比較/最古採用に使う
  date_str(tup)            : (Y,M,D) → "YYYY-MM" or "YYYY"(月不明) 表示用
  iter_items(paths)        : 生jsonlを (isbn13, item) で yield (utf-8固定・防御デコード)
  build_index(targets,...) : target基底題集合に対して focused index を1パスで構築
"""
import re, json, unicodedata, html

ROOT = "C:/Users/shuic/code/MANGAL"
DELTA = f"{ROOT}/.cache/rakuten-isbn-delta.jsonl"
OLD = f"{ROOT}/.cache/rakuten-isbn.jsonl"

# ---- 題正規化 (既存 _distill_fill_rakuten.py の norm と同義) ----
_NORM_STRIP = re.compile(r"[\s　・･:：!！?？.,。、\-－〜~＝=\[\]【】()『』「」（）]")
def norm(s):
    return _NORM_STRIP.sub("", unicodedata.normalize("NFKC", str(s or ""))).lower()

# ---- 巻トークン剥がし (NFKC済 = 半角括弧/半角数字/半角空白前提) ----
# 末尾の (...) 内に巻番号: （178巻）/（155）/（volume 145）/（vol.3）/（上）は数字無→None
_P_PAREN = re.compile(r"[(]\s*(?:vol(?:ume)?\.?\s*|第\s*)?(\d+)\s*巻?\s*[)]\s*$", re.I)
# 末尾 "第5巻" / "5巻" (空白区切り)
_P_KAN   = re.compile(r"\s+第?\s*(\d+)\s*巻\s*$")
# 末尾 "vol.5" / "#5" / "Vol 5"
_P_VOL   = re.compile(r"\s+(?:vol\.?|#)\s*(\d+)\s*$", re.I)
# 末尾 空白+数字 ("ONE PIECE 100"型)。空白必須 = 題内末尾数字(ゴルゴ13)は剥がさない
_P_SP    = re.compile(r"\s+(\d+)\s*$")

def parse_vol(t):
    """NFKC済タイトル t から末尾巻トークンを剥がす。
    return (vol:int|None, residual:str)。vol=None は巻番号トークン無(=単巻/vol1扱い候補)。"""
    t = t.rstrip()
    for p in (_P_PAREN, _P_KAN, _P_VOL, _P_SP):
        m = p.search(t)
        if m:
            v = int(m.group(1))
            residual = t[:m.start()].rstrip()
            return v, residual
    return None, t

def nfkc(s):
    return unicodedata.normalize("NFKC", str(s or ""))

# ---- salesDate 和文 → (Y,M,D) ----
_SD_FULL = re.compile(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})")
_SD_YM   = re.compile(r"(\d{4})\D+(\d{1,2})")
_SD_Y    = re.compile(r"(\d{4})")
# 上旬/中旬/下旬 → 代表日
def parse_salesdate(s):
    """return (Y, M, D)。M=0 は月不明(年のみ), D=0 は日不明(月のみ)。比較は tuple順で安全。"""
    s = str(s or "")
    m = _SD_FULL.match(s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _SD_YM.match(s)
    if m:
        d = 5 if "上旬" in s else 15 if "中旬" in s else 25 if "下旬" in s else 0
        return (int(m.group(1)), int(m.group(2)), d)
    m = _SD_Y.match(s)
    if m:
        return (int(m.group(1)), 0, 0)
    return None

def date_str(tup, day=False):
    if not tup: return ""
    y, m, d = tup
    if m == 0:  # 月不明 = 年のみ
        return f"{y:04d}"
    if day and d:
        return f"{y:04d}-{m:02d}-{d:02d}"
    return f"{y:04d}-{m:02d}"

_PD = re.compile(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?")
def parse_prod_date(s):
    """本番 release_date ("1976"/"1976-04"/"1976-04-05") → (Y,M,D)。M/D不明は0。"""
    if not s: return None
    m = _PD.match(str(s))
    if not m: return None
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))

# ---- 生jsonl iterator (utf-8固定) ----
def iter_items(paths):
    for path in paths:
        try:
            f = open(path, "r", encoding="utf-8")
        except FileNotFoundError:
            continue
        with f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                isbn = re.sub(r"\D", "", str(d.get("isbn", "")))
                it = d.get("item") or {}
                if len(isbn) == 13:
                    yield isbn, it

def clean_title(raw):
    """防御的 html unescape (&#39; 等) + NFKC。"""
    return nfkc(html.unescape(html.unescape(str(raw or ""))))

def build_index(target_bases, paths=(DELTA, OLD), progress=None):
    """target_bases = norm済基底題の set。
    return index: dict[(base_norm, vol)] -> list[dict(isbn,date,raw,publisher,cover)]
    残差題が target_bases に一致する item のみ収録 (= 完全一致ガード)。
    vol=None(巻トークン無) は vol=1 として収録 (単巻/1巻候補)。"""
    index = {}
    n = 0
    for isbn, it in iter_items(paths):
        n += 1
        if progress and n % 200000 == 0:
            progress(n)
        raw = clean_title(it.get("title", ""))
        vol, residual = parse_vol(raw)
        base = norm(residual)
        if base not in target_bases:
            continue
        v = 1 if vol is None else vol
        key = (base, v)
        cover = (it.get("largeImageUrl") or "").split("?")[0]
        rec = {
            "isbn": isbn,
            "date": parse_salesdate(it.get("salesDate", "")),
            "salesDate": it.get("salesDate", ""),
            "raw": raw,
            "vol_token": vol,  # None=トークン無
            "publisher": it.get("publisherName", ""),
            "cover": cover if "noimage" not in cover else "",
        }
        index.setdefault(key, []).append(rec)
    return index, n
