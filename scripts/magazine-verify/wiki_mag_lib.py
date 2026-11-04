"""Wikipedia 作品記事の Infobox(漫画)から 掲載誌・作者・開始 を抜く共通部品 + 誌名の同一視。"""
import re, unicodedata, os, json, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TR = re.compile(r"[\s・･!！?？。、,，.．:：;；\"'“”‘’「」『』()（）\[\]［］〜~\-‐－—―=＝/／★☆♪♡♥❤＋+×&＆]")


def norm(s):
    return TR.sub("", unicodedata.normalize("NFKC", s or "").lower())


def safe_key(name):          # scripts/_wiki-date-fetch.py と同じ
    return re.sub(r"[^0-9A-Za-z぀-ヿ一-鿿]", "_", name)[:80]


def strip_markup(s):
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    return s


def blocks(wt):
    """{{Infobox animanga/Manga ...}} を入れ子込みで切り出し、 |key=value を dict に。"""
    out = []
    for m in re.finditer(r"\{\{\s*Infobox animanga/Manga", wt):
        i = m.start(); depth = 0; j = i
        while j < len(wt):
            if wt.startswith("{{", j):
                depth += 1; j += 2; continue
            if wt.startswith("}}", j):
                depth -= 1; j += 2
                if depth == 0:
                    break
                continue
            j += 1
        body = strip_markup(wt[m.end():j - 2])
        parts, buf, d1, d2, k = [], "", 0, 0, 0
        while k < len(body):
            if body.startswith("{{", k):
                d1 += 1; buf += "{{"; k += 2; continue
            if body.startswith("}}", k):
                d1 -= 1; buf += "}}"; k += 2; continue
            if body.startswith("[[", k):
                d2 += 1; buf += "[["; k += 2; continue
            if body.startswith("]]", k):
                d2 -= 1; buf += "]]"; k += 2; continue
            if body[k] == "|" and d1 == 0 and d2 == 0:
                parts.append(buf); buf = ""; k += 1; continue
            buf += body[k]; k += 1
        parts.append(buf)
        d = {}
        for p in parts:
            if "=" in p:
                a, b = p.split("=", 1); d[a.strip()] = b.strip()
        out.append(d)
    return out


def links(s):
    return [(m.group(1).strip(), (m.group(2) or m.group(1)).strip())
            for m in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]", s)]


def plain(s):
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return s


def first_mag(v):
    """掲載誌の値から 先頭の誌名(リンク先, 表示, 直後の語)。 移籍は「A→B」なので先頭=初出誌。"""
    v = strip_markup(v or "")
    v = re.sub(r"\{\{\s*(?:Plainlist|plainlist|Unbulleted list|ubl)\s*\|", "", v)
    segs = re.split(r"<br\s*/?>|→|&#8594;|\n\s*\*|、|，|,|／", v.strip().lstrip("*").strip())
    v = next((x for x in segs if x.strip()), "")
    if not v.strip():
        return None
    m = re.search(r"\[\[([^\]|#]+)(#[^\]|]*)?(?:\|([^\]]*))?\]\]([^\[<→\n、,/]{0,8})", v)
    if m:
        target, anchor, disp = m.group(1).strip(), m.group(2), (m.group(3) or m.group(1)).strip()
        if anchor and disp != target:
            target = disp          # 記事の節を指すリンク = 表示名の誌(増刊など)。 親誌に寄せない
        return (target, disp, m.group(4).strip())
    t = plain(v).strip().lstrip("*").strip()
    return (t, t, "") if t else None


def people(d):
    s = " ".join(d.get(k, "") for k in ("作者", "作画", "原作", "漫画", "著者", "キャラクター原案", "構成", "シナリオ"))
    names = [b for a, b in links(s)] + [a for a, b in links(s)]
    names += [x for x in re.split(r"[、,/・\s]|<br\s*/?>", plain(s)) if x]
    return {norm(x) for x in names if len(norm(x)) >= 2}


def years(d):
    s = " ".join(d.get(k, "") for k in ("開始号", "開始日", "発表期間", "発表号", "連載期間"))
    ys = [int(y) for y in re.findall(r"(19[4-9]\d|20[0-3]\d)", s)]
    return min(ys) if ys else 0


MAG = yaml.safe_load(open(os.path.join(ROOT, "data", "magazines.yml"), encoding="utf-8"))
WIKI2KEY = {norm(v["name"]): k for k, v in MAG.items()}
for a, k in {"ジャンプスクエア": "jump-sq", "ジャンプSQ.": "jump-sq", "週刊ビッグコミックスピリッツ": "big-comic-spirits",
             "LaLa": "lala", "ララ": "lala", "少女コミック": "shojo-comic-legacy", "Sho-Comi": "shojo-comic",
             "週刊少年チャンピオン": "champion", "ビッグコミックスピリッツ": "big-comic-spirits", "週刊モーニング": "morning",
             "月刊アフタヌーン": "afternoon", "コミックボンボン": "comic-bonbon", "月刊コミックボンボン": "comic-bonbon",
             "漫画アクション": "manga-action", "週刊漫画アクション": "manga-action", "月刊少年エース": "shonen-ace",
             "ヤングジャンプ": "weekly-young-jump", "ヤングマガジン": "weekly-young-magazine", "ヤングサンデー": "weekly-young-sunday",
             "少年ジャンプ+": "shonen-jump-plus", "少年ジャンププラス": "shonen-jump-plus", "ジャンプ+": "shonen-jump-plus",
             "月刊少年ガンガン": "gangan", "少年ガンガン": "gangan", "Gファンタジー": "gfantasy", "月刊Gファンタジー": "gfantasy",
             "電撃大王": "dengeki-daioh", "月刊コミック電撃大王": "dengeki-daioh", "コンプエース": "comp-ace",
             "ガンガンパワード": "gangan-powered", "月刊少年ガンガン増刊ガンガンパワード": "gangan-powered",
             "少年ガンガン増刊ガンガンパワード": "gangan-powered",
             "BE・LOVE": "be-love", "BE LOVE": "be-love", "サンデーGX": "monthly-sunday-gx", "月刊サンデーGX": "monthly-sunday-gx",
             "週刊少年サンデーS": "shonen-sunday-super", "少年サンデーS": "shonen-sunday-super",
             "最強ジャンプ": "saikyo-jump", "週刊少年ジャンプ増刊最強ジャンプ": "saikyo-jump", "Vジャンプ": "v-jump",
             "月刊少年ジャンプ": "monthly-shonen-jump", "別冊マーガレット": "betsuma", "週刊マーガレット": "margaret",
             "コミックREX": "comic-rex", "月刊ComicREX": "comic-rex", "ヤングキングアワーズ": "young-king-ours",
             "週刊漫画ゴラク": "weekly-manga-goraku", "漫画ゴラク": "weekly-manga-goraku", "ガンガンONLINE": "gangan-online",
             "マガジンポケット": "manga-pocket", "少年マガジンエッジ": "shonen-magazine-edge", "月刊ヤングマガジン": "monthly-young-magazine",
             "コミックバンバン": "comic-banban", "月刊コミックバンバン": "comic-banban", "ComicWalker": "comic-walker",
             "まんがタイムきらら": "manga-time-kirara", "月刊コミックブレイド": "comic-blade", "コミックブレイド": "comic-blade",
             "月刊ガンガンWING": "gangan-wing", "ガンガンWING": "gangan-wing", "月刊ガンガンJOKER": "gangan-joker", "ガンガンJOKER": "gangan-joker",
             "月刊ビッグガンガン": "big-gangan", "ビッグガンガン": "big-gangan", "月刊サンデージェネックス": "monthly-sunday-gx",
             "ヤングエースUP": "young-ace-up", "月刊アクション": "monthly-action", "となりのヤングジャンプ": "tonari-no-young-jump",
             "フレッシュジャンプ": "fresh-jump", "週刊少年キング": "shonen-king", "少年キング": "shonen-king",
             "マーガレット (雑誌)": "margaret", "Sho-Comi (雑誌)": "shojo-comic",
             "ガンガンウイング": "gangan-wing", "月刊ガンガンウイング": "gangan-wing"}.items():
    WIKI2KEY.setdefault(norm(a), k)


def mag_key(t):
    """first_mag の結果 → (master key or "", 誌名, 増刊等の注記)。 ★表示名を先に引く([[少女コミック|Sho-Comi]] は Sho-Comi)。"""
    if not t:
        return ("", "", "")
    target, disp, after = t
    note = after if re.match(r"(増刊|別冊|臨時|特別|大増刊|夏の増刊|.*増刊)", after or "") else ""
    for x in (disp, target, re.sub(r"\s*[（(][^)）]*[)）]$", "", target)):
        k = WIKI2KEY.get(norm(x))
        if k:
            return (k, disp, note)
    return ("", disp, note)


ALIAS_CANON = [("ちゅちゅ", "chuchu"), ("クッキー", "cookie"), ("ララ", "lala"), ("スペシャル", "special"), ("ゴールド", "gold"),
               ("エレガンス", "elegance"), ("ガールズジャンプ", "girlsjump"), ("ぼこぼこ", "ぽこぽこ"), ("プレコミックブンブン", "コミックブンブン"),
               ("（ミチャオ）", ""), ("(ミチャオ)", ""), ("デラックス", "dx"), ("プラス", "+")]


def canon(name):
    s = unicodedata.normalize("NFKC", name or "").lower()
    for a, b in ALIAS_CANON:
        s = s.replace(unicodedata.normalize("NFKC", a).lower(), b)
    s = re.sub(r"\s*\([^)]*\)$", "", s)            # 「Cookie (雑誌)」の曖昧さ回避
    s = TR.sub("", s)
    s = re.sub(r"^(月刊|週刊|隔週刊|季刊|隔月刊)", "", s)
    s = re.sub(r"(増刊号|増刊)$", "", s)
    return s


def ident(key_or_name):
    """master key ならそのまま、 誌名なら master に引けるか試し、 だめなら '?'+canon。"""
    if not key_or_name:
        return ""
    if key_or_name in MAG:
        return key_or_name
    if key_or_name.startswith("?"):
        key_or_name = key_or_name[1:]
    c = canon(key_or_name)
    for k, v in MAG.items():
        if canon(v["name"]) == c:
            return k
    for a, k in WIKI2KEY.items():
        if canon(a) == c:
            return k
    return "?" + c


def same(a, b):
    """同じ誌か = ident の結果が完全一致の時だけ。 ★部分一致は使わない(2026-11-04 実踏: 「別冊コロコロコミック」⊃「コロコロコミック」、
    「Cookie BOX」⊃「Cookie」= 別の誌(増刊)を同じ誌とみなして A=根拠2つ一致 に入れていた)。 表記ゆれは canon/ALIAS_CANON で吸収する。"""
    return bool(a) and bool(b) and a == b
