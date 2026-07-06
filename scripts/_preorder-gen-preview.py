#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約②③: 新作1巻のpreviewドラフトページ生成 (= 2026-07-06 B裁定=テスト先行)

classified.json の new1a(②作者既知)/new1b(③作者新規) を .preview-data/manga/ に生成する。
本番(data/manga.v2)には書かない。ユーザ確認後の本番化は別工程。

ゲート(fail-closed・不備は保留worklist):
  titleKana有 / author有 / 発売月(ym)有 / ISBN13 / slug衝突なし
ヨミ: 楽天titleKana/authorKanaで仮確定し、data/seeds/rakuten-kana-pending.jsonl(git追跡)へ
  積む=日次蒸留がNDL照合を試み、確定/不一致を裁く(A裁定=漏れない仕組み)。
slug: ヨミの機械ローマ字化(長音保持・を=o・促音・スペース=hyphen)。衝突は-年suffix。
demographic: 楽天サブジャンル写像(少年/少女/青年/レディース)。genreは空(捏造しない)。
使い方: python scripts/_preorder-gen-preview.py new1a|new1b|both [--limit N]
"""
import json, os, re, sys, datetime, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()
PEND = os.path.join(ROOT, "data", "seeds", "rakuten-kana-pending.jsonl")
TRIAGE = os.path.join(ROOT, "docs", "production-diagnostics", "preorder-triage.tsv")

WHICH = sys.argv[1] if len(sys.argv) > 1 else "both"
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**9

# --- カナ→ローマ字(ヘボン・決定的)。slug規則: 長音=母音連続(おう→ou相当はカナ由来でォ表現なし=ーは前母音重ね)/を=o/スペース=hyphen ---
_K2R = {
 "ア":"a","イ":"i","ウ":"u","エ":"e","オ":"o","カ":"ka","キ":"ki","ク":"ku","ケ":"ke","コ":"ko",
 "サ":"sa","シ":"shi","ス":"su","セ":"se","ソ":"so","タ":"ta","チ":"chi","ツ":"tsu","テ":"te","ト":"to",
 "ナ":"na","ニ":"ni","ヌ":"nu","ネ":"ne","ノ":"no","ハ":"ha","ヒ":"hi","フ":"fu","ヘ":"he","ホ":"ho",
 "マ":"ma","ミ":"mi","ム":"mu","メ":"me","モ":"mo","ヤ":"ya","ユ":"yu","ヨ":"yo",
 "ラ":"ra","リ":"ri","ル":"ru","レ":"re","ロ":"ro","ワ":"wa","ヲ":"o","ン":"n",
 "ガ":"ga","ギ":"gi","グ":"gu","ゲ":"ge","ゴ":"go","ザ":"za","ジ":"ji","ズ":"zu","ゼ":"ze","ゾ":"zo",
 "ダ":"da","ヂ":"ji","ヅ":"zu","デ":"de","ド":"do","バ":"ba","ビ":"bi","ブ":"bu","ベ":"be","ボ":"bo",
 "パ":"pa","ピ":"pi","プ":"pu","ペ":"pe","ポ":"po","ヴ":"vu",
 "キャ":"kya","キュ":"kyu","キョ":"kyo","シャ":"sha","シュ":"shu","ショ":"sho","チャ":"cha","チュ":"chu","チョ":"cho",
 "ニャ":"nya","ニュ":"nyu","ニョ":"nyo","ヒャ":"hya","ヒュ":"hyu","ヒョ":"hyo","ミャ":"mya","ミュ":"myu","ミョ":"myo",
 "リャ":"rya","リュ":"ryu","リョ":"ryo","ギャ":"gya","ギュ":"gyu","ギョ":"gyo","ジャ":"ja","ジュ":"ju","ジョ":"jo",
 "ビャ":"bya","ビュ":"byu","ビョ":"byo","ピャ":"pya","ピュ":"pyu","ピョ":"pyo",
 "ファ":"fa","フィ":"fi","フェ":"fe","フォ":"fo","ティ":"ti","ディ":"di","デュ":"dyu","ウィ":"wi","ウェ":"we","ウォ":"wo",
 "シェ":"she","ジェ":"je","チェ":"che","ツァ":"tsa","ツェ":"tse","ツォ":"tso","トゥ":"tu","ドゥ":"du","イェ":"ye","ヴァ":"va","ヴィ":"vi","ヴェ":"ve","ヴォ":"vo",
}
def kana2romaji(kana: str) -> str:
    s = unicodedata.normalize("NFKC", str(kana or ""))
    # ひら→カタ
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ん" else c for c in s)
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        two = s[i:i+2]
        if c == "ッ":
            # 促音: 次のローマ字の頭子音を重ねる
            nxt = _K2R.get(s[i+1:i+3]) or _K2R.get(s[i+1:i+2]) or ""
            out.append(nxt[0] if nxt and nxt[0] not in "aiueo" else "")
            i += 1
            continue
        if c == "ー":
            # 長音: 直前母音を重ねる(長音保持規則)
            prev = out[-1][-1] if out and out[-1] else ""
            out.append(prev if prev in "aiueo" else "")
            i += 1
            continue
        if two in _K2R:
            out.append(_K2R[two]); i += 2; continue
        if c in _K2R:
            out.append(_K2R[c]); i += 1; continue
        if re.match(r"[A-Za-z0-9]", c):
            out.append(c.lower()); i += 1; continue
        if c in " 　・=/:：〜~☆★!！?？、。,.'’\"-−–":
            out.append("-"); i += 1; continue
        out.append("-"); i += 1
    r = "".join(out)
    r = re.sub(r"-+", "-", r).strip("-")
    # ん+母音/ y → n のまま(簡易)。空なら失敗
    return r

# 既存slug集合(本番+preview)
existing = set()
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
si = idx["f"].index("slug")
for r in idx["d"]:
    existing.add(r[si])
import glob as _g
for p in _g.glob(f"{ROOT}/.preview-data/manga/*.yml"):
    existing.add(os.path.basename(p)[:-4])

DEMO = {"少年": "shonen", "少女": "shojo", "青年": "seinen", "レディース": "josei"}

def author_names(s):
    return [x.strip() for x in re.split(r"[/,、;；]", str(s or "")) if x.strip()]

cls = json.load(open(f"{ROOT}/.cache/preorders/classified.json", encoding="utf-8"))
targets = []
if WHICH in ("new1a", "both"):
    targets += [("new1a", r) for r in cls["new1a"]]
if WHICH in ("new1b", "both"):
    targets += [("new1b", r) for r in cls["new1b"]]
targets = targets[:LIMIT]

made = []
holds = []
pend_lines = []
VOLSTRIP = re.compile(r"[\s　]*(?:[（(]\s*\d{1,3}\s*[)）]|第\s*\d{1,3}\s*巻|\d{1,3})\s*$")
def strip_vol_disp(t):
    """表示題/ヨミから末尾の巻表記を除去(作品題に正規化)。全部消える場合は元のまま"""
    t2 = VOLSTRIP.sub("", str(t or "").strip())
    return t2 if t2 else str(t or "").strip()

for klass, r in targets:
    title = strip_vol_disp(r.get("title"))
    kana = strip_vol_disp(r.get("titleKana"))
    ym = r.get("ym")
    isbn = r.get("isbn")
    auths = author_names(r.get("author"))
    akanas = author_names(r.get("authorKana"))
    if not (title and kana and ym and isbn and len(isbn) == 13 and auths):
        holds.append((klass, isbn, title, "必須欠け(kana/author/ym)")); continue
    romaji = kana2romaji(kana)
    if not romaji or len(romaji) < 2:
        holds.append((klass, isbn, title, f"slug生成不可 kana={kana[:16]}")); continue
    slug = romaji[:70]
    if slug in existing:
        slug = f"{slug}-{ym[:4]}"
        if slug in existing:
            holds.append((klass, isbn, title, f"slug衝突 {slug}")); continue
    existing.add(slug)
    rd = ym + (f"-{r['day']:02d}" if r.get("day") else "")
    authors = []
    for i2, name in enumerate(auths):
        a = {"name": name}
        if i2 < len(akanas) and akanas[i2]:
            a["kana"] = akanas[i2]
        authors.append(a)
    doc = {
        "slug": slug,
        "title": title,
        "title_kana": kana.replace(" ", "").replace("　", ""),
        "title_romaji": romaji.replace("-", " "),
        "authors": authors,
        "year_started": int(ym[:4]),
        "status": "ongoing",
        "demographic": DEMO.get(r.get("subgenre")),
        "genres": [],
        "editions": [{
            "type": "standard", "label": "通常版", "publisher": r.get("publisher"), "imprint": r.get("seriesName") or "",
            "volumes": [{"number": r.get("_vol") or 1, "asin": None, "isbn13": isbn,
                         "cover_url": r.get("cover"), "release_date": rd}],
        }],
        "_preorder_draft": {"class": klass, "added_at": TODAY, "source": "rakuten-preorder",
                            "note": "予約②③previewドラフト。本番化はユーザ確認後。ヨミ=楽天仮(NDL照合待ち)"},
    }
    yaml.dump(doc, open(f"{ROOT}/.preview-data/manga/{slug}.yml", "w", encoding="utf-8"),
              allow_unicode=True, sort_keys=False, width=200)
    made.append(slug)
    pend_lines.append(json.dumps({"isbn": isbn, "slug": slug, "title": title, "title_kana": kana,
                                  "authors": auths, "author_kanas": akanas, "added_at": TODAY,
                                  "status": "pending"}, ensure_ascii=False))

with open(PEND, "a", encoding="utf-8") as f:
    for ln in pend_lines:
        f.write(ln + "\n")
with open(TRIAGE, "a", encoding="utf-8") as f:
    for klass, isbn, title, why in holds:
        f.write(f"{klass}_hold\t{isbn}\t\t{str(title)[:40]}\t\t\t{why}\n")
json.dump(made, open(f"{ROOT}/.cache/preorders/preview-made-{WHICH}.json", "w"))
print(f"{WHICH}: 生成{len(made)} / 保留{len(holds)} / NDL照合キュー+{len(pend_lines)}")
