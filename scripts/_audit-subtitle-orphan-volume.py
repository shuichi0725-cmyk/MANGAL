#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sugar&Spice型 = 楽天の副題/題が「<既存頁の題> <巻番号>」を名乗るのに、そのISBNが本番に無い巻を検出する。

★なぜ要るか (= 2026-09-03 ユーザ発見「sugar-spice 完結してるが抜けているし足りない」から型化)
  各巻が固有の巻題を持つシリーズ(Sugar & Spice = 全巻ジャズ曲題)で、MADBが 17/19/20巻を
  巻題「Somethin' stupid」「Rose & beast」「Over the rainbow」を**題として**別IDで登録し、
  種2のクラスタキー(著者+題)がそれらを別sid(number=0/1, is_extra=1)に落とした。
  本編sid(1-16,18)と結線されず、頁は「17巻欠け+18巻で終わり」に見えた(実際は全20巻完結)。
  ★既存監査の死角: 孤児sidは単巻・未頁化なので solo-truncated(孤立**頁**)の対象外、
    巻抜け仮想は 1-16,18 の内側(17)しか見えず、末尾の 19/20 は「無い」ことが分からない。
  ★唯一の機械信号は楽天側にある: subTitle「Suger ＆ Spice 17」/ title「Rose＆Beast Sugar＆Spice19」。

判定(候補列挙であって自動適用ではない):
  信号   = SUBTITLE(副題が親題+番号) / TITLE_TAIL(題末尾が番号) / TITLE_MID(題中に親題+番号+副題)
  巻状態 = MISSING_TAIL(番号 > 頁の最大巻 = 末尾欠け) / MISSING_GAP(内側の穴) /
           OTHER_ISBN(同番号が別ISBNで既在 = 別版/特装/新装 = 概ね無害・版違い候補)
  種2   = SPLIT(種2に在るが頁と別sid = 種4結線 or merge) / SAME_SID(頁と同sidなのに未表示 =
           promoteのフィルタ/除外を疑う) / ABSENT(種2に無い = 真のMADB取込もれ = 種4)
  tier  = A(著者一致) / B(著者不一致 or 頁著者無し = 同名別作品の可能性)
  除外seed = ISBNが drop/exclude 系seedに載っている(意図的な非掲載 = 偽陽性)

  ★芯 = MISSING × tierA × EXACT × 疑なし × 除外seed外 (初回 2026-09-03: 1,365巻/809頁 = ABSENT 1,134 / SPLIT 172 / SAME_SID 59)

第2部(楽天非依存): edition-overrides.json で巻を固定した頁に、種2同sidの続巻が来ているのに出ていない巻
  → docs/production-diagnostics/overrides-frozen-tail.tsv (初回 25巻/10頁。フェルマーの料理8巻 2026-06 等)

出力: docs/production-diagnostics/subtitle-orphan-volume.tsv
使い方:
  python scripts/_exists.py --build            # 先にISBN索引を最新化
  python scripts/_audit-subtitle-orphan-volume.py [--signal SUBTITLE] [--min-title 4]
"""
import argparse
import collections
import glob
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from _idx_authors import au_names  # noqa: E402

ISBN_IDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")
LIST_IDX = os.path.join(ROOT, "data", "manga-list-index.json")
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
SOURCES = [os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"),
           os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl")]
V2_DIR = os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "subtitle-orphan-volume.tsv")

COLS = ["巻状態", "種2", "tier", "信号", "一致", "残差", "疑", "slug", "頁題", "頁著者", "頁最大巻", "頁巻数",
        "isbn", "楽天題", "楽天副題", "抽出親題", "抽出巻", "楽天著者", "出版社", "レーベル",
        "発売日", "種2sid", "種2題", "種2巻", "除外seed"]

_PUNCT = re.compile(r"[\s　〜~！!?？・:：（）()【】\[\]「」『』\-‐−―。、．.=＆&＋+'’\"“”,，/／|｜]")
_ISBN13 = re.compile(r"97[89]\d{10}")

# 末尾番号: 「Sugar & Spice 17」「Sugar＆Spice19」「xxx 第3巻」「xxx vol.4」「xxx(5)」「xxx #6」
#   ★番号は数字境界必須(2000-2009 の「200」/ 大問題('04) の年号を巻に誤読しない)
_TAIL = re.compile(
    r"^(?P<p>.+?)[\s　]*(?:第|vol\.?|volume|#|その)?[\s　]*[(（]?(?<!\d)(?P<n>\d{1,3})(?!\d)[)）]?[\s　]*(?:巻|集)?$",
    re.I)
# 題中: 「Sugar & Spice20〜Over the Rainbow〜」「xxx 3 (副題)」= 親題+番号のあとに区切りが続く
_MID = re.compile(
    r"^(?P<p>.+?)[\s　]*(?:第|vol\.?)?[\s　]*(?<!\d)(?P<n>\d{1,3})(?!\d)[\s　]*(?:巻)?[\s　]*[〜~\-−―:：「『(（【].+$",
    re.I)

# 疑(偽陽性の型)。候補から落とさず列に立てる = 人が裁く材料
_RX_EDITION = re.compile(
    r"完全版|新装版|文庫|愛蔵版|ワイド版|wide|pocket|ポケット|傑作集|傑作選|総集編|大全集|全集|選集|"
    r"デラックス|dx|コンビニ|廉価|セレクション|selection|remix|リミックス|新版|改訂|合本|分冊|"
    r"カラー版|限定版|特装版|通常版|豪華版|決定版|保存版|復刻|再録|ベスト|best", re.I)
_RX_SPINOFF = re.compile(
    r"外伝|番外|スピンオフ|another|side|アナザー|エピソード|episode|前日譚|後日譚|アンソロジー|anthology|"
    r"公式|ガイド|ファンブック|イラスト|画集|illustration|設定|資料|データ|ノベル|novel|小説", re.I)
_RX_LABEL = re.compile(r"傑作集|全集|選集|コレクション|作家編|シリーズ|library|ライブラリ", re.I)
_RX_DROPIMP = re.compile(r"my first big|コンビニ|増刊|同人|remix|リミックス|bilingual|novels?\b", re.I)


def norm(t: str) -> str:
    s = unicodedata.normalize("NFKC", str(t or "")).lower()
    return _PUNCT.sub("", s)


def jp_registrant(isbn13: str) -> str:
    """978-4(日本) の出版者記号を桁数表(2〜7桁)で切り出す。先頭N桁固定だと2桁社(KADOKAWA=04/講談社=06)で
    題番号の1桁目まで含んで別社扱いになる(魔法科よんこま編 9784048/9784049 で実踏)。"""
    s = str(isbn13 or "")
    if not s.startswith("9784") or len(s) != 13:
        return s[:8]
    body = s[4:]  # 出版者記号+書名記号+チェック
    n = int(body[:2])
    if n <= 19:
        ln = 2
    elif int(body[:3]) <= 699:
        ln = 3
    elif int(body[:4]) <= 8499:
        ln = 4
    elif int(body[:5]) <= 89999:
        ln = 5
    elif int(body[:6]) <= 949999:
        ln = 6
    else:
        ln = 7
    return "9784" + body[:ln]


def norm_author(a: str) -> str:
    s = unicodedata.normalize("NFKC", str(a or ""))
    s = re.sub(r"[\[\(（【].*?[\]\)）】]", "", s)  # 役割注記 [原作] (著) 等
    s = re.sub(r"(原作|作画|漫画|著|作|画|監修|訳|編)$", "", s.strip())
    return _PUNCT.sub("", s.lower())


def _yearlike(t: str, m) -> bool:
    """'04 / 05 / 1989 型の年号を巻番号と誤読していないか。"""
    s, e = m.start("n"), m.end("n")
    raw = t[s:e]
    if len(raw) == 2 and raw[0] == "0":
        return True
    if s > 0 and t[s - 1] in "'’‘":
        return True
    return False


def candidates(text: str, signal: str):
    """文字列から (親題, 番号, 信号, 年号疑) を列挙。末尾番号を優先、無ければ題中型。"""
    t = unicodedata.normalize("NFKC", str(text or "")).strip()
    if not t:
        return
    m = _TAIL.match(t)
    if m:
        yield m.group("p").strip(" 　・:：-〜~"), int(m.group("n")), signal, _yearlike(t, m)
        return
    if signal == "TITLE_TAIL":
        m = _MID.match(t)
        if m:
            yield m.group("p").strip(" 　・:：-〜~"), int(m.group("n")), "TITLE_MID", _yearlike(t, m)


def page_numbers(slug_to_stem, slug):
    """頁ymlの巻番号集合(全版)。stem(ファイル名)が公開slugと違う頁も逆引き済みmapで読む。"""
    stem = slug_to_stem.get(slug, slug)
    p = os.path.join(V2_DIR, stem + ".yml")
    if not os.path.exists(p):
        return set()
    raw = io.open(p, encoding="utf-8", errors="replace").read()
    return {int(x) for x in re.findall(r"^\s+-? ?number: (\d+)\s*$", raw, re.M)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", choices=["SUBTITLE", "TITLE_TAIL", "TITLE_MID"], help="信号を絞る")
    ap.add_argument("--min-title", type=int, default=4, help="接尾/接頭一致に要る正規化題の最小長")
    ap.add_argument("--min-exact", type=int, default=2, help="完全一致に要る正規化題の最小長")
    a = ap.parse_args()

    if not os.path.exists(ISBN_IDX):
        print(f"★abort: {ISBN_IDX} が無い。先に python scripts/_exists.py --build")
        return 2
    idx = json.load(io.open(ISBN_IDX, encoding="utf-8"))
    print(f"ISBN索引 {len(idx)}件", flush=True)

    # 頁メタ
    li = json.load(io.open(LIST_IDX, encoding="utf-8"))
    f = {n: i for i, n in enumerate(li["f"])}
    meta = {}
    by_norm = collections.defaultdict(list)
    for r in li["d"]:
        slug = r[f["slug"]]
        title = r[f["title"]] or ""
        aus = au_names(r[f["authors"]]) + au_names(r[f["original_authors"]])
        meta[slug] = {"title": title, "authors": aus,
                      "au_norm": {norm_author(x) for x in aus if x},
                      "max": r[f["max_edition_volumes"]], "total": r[f["total_volumes"]]}
        nt = norm(title)
        if nt:
            by_norm[nt].append(slug)
    print(f"一覧索引 {len(meta)}頁 / 正規化題 {len(by_norm)}種", flush=True)

    # 公開slug → manga.v2 stem(改名頁の逆引き。[[pubslug_src_stem_generator_trap]])
    slug_to_stem = {}
    for p in glob.glob(os.path.join(V2_DIR, "*.yml")):
        stem = os.path.basename(p)[:-4]
        slug_to_stem.setdefault(stem, stem)
    # stem≠slug の頁: 一覧索引の slug がファイルに無ければ、ファイル先頭の slug: 行で逆引き
    missing = [s for s in meta if s not in slug_to_stem]
    if missing:
        want = set(missing)
        for p in glob.glob(os.path.join(V2_DIR, "*.yml")):
            stem = os.path.basename(p)[:-4]
            if stem in meta:
                continue
            try:
                head = io.open(p, encoding="utf-8", errors="replace").read(400)
            except Exception:
                continue
            m = re.search(r"^slug: (.+)$", head, re.M)
            if m:
                s = m.group(1).strip().strip("'\"")
                if s in want:
                    slug_to_stem[s] = stem
    print(f"改名頁の逆引き {len(missing)}件中 {sum(1 for s in missing if s in slug_to_stem)}件解決", flush=True)

    # 除外系seedに載るISBN(意図的非掲載)
    excl = set()
    for p in glob.glob(os.path.join(ROOT, "data", "seeds", "*")):
        b = os.path.basename(p).lower()
        if not (("exclude" in b or "drop" in b or "dedup" in b) and os.path.isfile(p)):
            continue
        try:
            excl |= set(_ISBN13.findall(io.open(p, encoding="utf-8", errors="replace").read()))
        except Exception:
            pass
    print(f"除外系seedのISBN {len(excl)}件", flush=True)
    # preview(予約ドラフト等)に既に居るISBN = 本番化待ち(二重作業防止のフラグ)
    preview_isbns = set()
    for p in glob.glob(os.path.join(ROOT, ".preview-data", "manga", "*.yml")):
        try:
            preview_isbns |= set(_ISBN13.findall(io.open(p, encoding="utf-8", errors="replace").read()))
        except Exception:
            pass
    print(f"preview頁のISBN {len(preview_isbns)}件", flush=True)

    # 種2: isbn→(sid, number, is_extra, edition type, release_date) / sid→title
    con = sqlite3.connect(DB)
    s2 = {}
    for isbn, sid, num, extra, etype, rd in con.execute(
            "SELECT v.isbn13, e.series_id, v.number, v.is_extra, e.type, v.release_date "
            "FROM volumes v JOIN editions e ON e.id=v.edition_id "
            "WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"):
        s2.setdefault(isbn.replace("-", ""), (sid, num, extra, etype, rd))
    s2title = dict(con.execute("SELECT id, title FROM series"))
    print(f"種2 ISBN {len(s2)}件", flush=True)
    # 頁→sid集合(頁のISBNから逆引き) / 頁→出版者記号集合(先頭7桁・8桁)
    page_sids = collections.defaultdict(set)
    page_prefix = collections.defaultdict(set)
    for isbn, slugs in idx.items():
        hit = s2.get(isbn)
        for s in (slugs if isinstance(slugs, list) else [slugs]):
            page_prefix[s].add(jp_registrant(isbn))
            if hit:
                page_sids[s].add(hit[0])

    def find_pages(parent: str):
        """正規化親題 → (頁slug群, 一致型, 残差)。完全一致 → 接尾一致(Rose&Beast Sugar&Spice →
        sugarspice、残差=巻題) → 接頭一致(xxx外伝/新装版 → xxx、残差=派生語)。"""
        np_ = norm(parent)
        if not np_:
            return [], "", ""
        if len(np_) >= a.min_exact and np_ in by_norm:
            return by_norm[np_], "EXACT", ""
        for k in range(1, len(np_) - a.min_title + 1):  # 長い接尾から
            suf = np_[k:]
            if suf in by_norm:
                return by_norm[suf], "SUFFIX", np_[:k]
        for k in range(len(np_) - 1, a.min_title - 1, -1):  # 長い接頭から
            pre = np_[:k]
            if pre in by_norm:
                return by_norm[pre], "PREFIX", np_[k:]
        return [], "", ""

    rows = []
    seen = set()
    nlines = 0
    for fn in SOURCES:
        if not os.path.exists(fn):
            continue
        n = 0
        for line in io.open(fn, encoding="utf-8", errors="replace"):
            n += 1
            try:
                o = json.loads(line)
            except Exception:
                continue
            isbn = (o.get("isbn") or "").replace("-", "")
            if not isbn or isbn in seen:
                continue
            it = o.get("item") or {}
            if not it:
                continue
            seen.add(isbn)
            if isbn in idx:
                continue  # 本番に在る = 対象外
            gid = str(it.get("booksGenreId") or "")
            if gid and not gid.startswith("001001"):
                continue  # 楽天ジャンル=コミック以外
            if not gid and (it.get("size") or "") != "コミック":
                continue
            title = it.get("title") or ""
            sub = it.get("subTitle") or ""
            cands = list(candidates(sub, "SUBTITLE")) + list(candidates(title, "TITLE_TAIL"))
            if not cands:
                continue
            r_au = {norm_author(x) for x in re.split(r"[/／,、]", it.get("author") or "") if x.strip()}
            r_au.discard("")
            emitted = False
            for parent, num, signal, yl in cands:
                if a.signal and signal != a.signal:
                    continue
                pages, mtype, resid = find_pages(parent)
                if not pages:
                    continue
                # 著者一致頁を優先。無ければ tier B で最大3頁
                amatch = [s for s in pages if meta[s]["au_norm"] and (meta[s]["au_norm"] & r_au)]
                if not amatch and r_au:
                    # 部分一致(姓名の空白/表記差): 片方がもう片方を含む
                    amatch = [s for s in pages if any(
                        (x and y and (x in y or y in x)) for x in meta[s]["au_norm"] for y in r_au)]
                tier = "A" if amatch else "B"
                targets = amatch or pages[:3]
                for slug in targets:
                    nums = page_numbers(slug_to_stem, slug)
                    mx = max(nums) if nums else 0
                    if num in nums:
                        state = "OTHER_ISBN"
                    elif num > mx:
                        state = "MISSING_TAIL"
                    else:
                        state = "MISSING_GAP"
                    hit = s2.get(isbn)
                    if hit:
                        sid, s2num = hit[0], hit[1]
                        s2state = "SAME_SID" if sid in page_sids.get(slug, ()) else "SPLIT"
                        s2t = s2title.get(sid, "")
                    else:
                        sid, s2num, s2state, s2t = "", "", "ABSENT", ""
                    m = meta[slug]
                    flags = []
                    if yl:
                        flags.append("YEARLIKE")
                    _probe = unicodedata.normalize(
                        "NFKC", f"{resid} {sub} {s2t} {title if signal != 'TITLE_TAIL' else ''}").lower()
                    if _RX_EDITION.search(_probe):
                        flags.append("EDITION")
                    if _RX_SPINOFF.search(_probe):
                        flags.append("SPINOFF")
                    if _RX_LABEL.search(unicodedata.normalize("NFKC", f"{resid} {s2t}")):
                        flags.append("LABEL")
                    # 種2題が「親題+同じ数字」= 続編題(リング2/トイ・ストーリー2)か番号入り巻題か、機械では割れない
                    if s2t and norm(s2t) == norm(parent) + str(num):
                        flags.append("SEQTITLE")
                    # promote が imprint で落とすレーベル(コンビニ本/増刊/同人/remix/novel)= 出ないのが正
                    if _RX_DROPIMP.search(unicodedata.normalize("NFKC", it.get("seriesName") or "")):
                        flags.append("DROPIMPRINT")
                    # 頁の既存ISBNと出版者記号が交差しない = 別版/別社の可能性(移籍は正当なので flag 止まり)
                    _pp = page_prefix.get(slug)
                    if _pp and jp_registrant(isbn) not in _pp:
                        flags.append("PUBMISMATCH")
                    if isbn in preview_isbns:
                        flags.append("PREVIEW")
                    rows.append([state, s2state, tier, signal, mtype, resid, "/".join(flags),
                                 slug, m["title"], "・".join(m["authors"]),
                                 mx, len(nums), isbn, title, sub, parent, num,
                                 it.get("author") or "", it.get("publisherName") or "",
                                 it.get("seriesName") or "", it.get("salesDate") or "",
                                 sid, s2t, s2num, "Y" if isbn in excl else ""])
                    emitted = True
                if emitted:
                    break  # 1ISBN=1信号(副題優先)
        nlines += n
        print(f"  {os.path.basename(fn)}: {n}行走査 / 累計 候補{len(rows)}件", flush=True)

    order = {"MISSING_TAIL": 0, "MISSING_GAP": 1, "OTHER_ISBN": 2}
    rows.sort(key=lambda r: (order.get(r[0], 9), r[2], r[1], r[7], r[16]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(COLS) + "\n")
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")

    print(f"\n候補 {len(rows)}件 / 頁 {len({r[7] for r in rows})}件 → {os.path.relpath(OUT, ROOT)}")
    c = collections.Counter((r[0], r[1], r[2]) for r in rows)
    print("巻状態 × 種2 × tier:")
    for (st, s2s, tier), n in sorted(c.items(), key=lambda kv: (order.get(kv[0][0], 9), kv[0][2], kv[0][1])):
        print(f"   {st:13s} {s2s:9s} {tier}: {n}")
    c2 = collections.Counter(r[3] for r in rows)
    print("信号:", dict(c2))
    c3 = collections.Counter((r[4], r[0]) for r in rows)
    print("一致型 × 巻状態:", dict(sorted(c3.items())))
    print("除外seed載り:", sum(1 for r in rows if r[-1] == "Y"))
    print("疑フラグ:", dict(collections.Counter(f for r in rows for f in r[6].split("/") if f)))
    core = [r for r in rows if r[0] != "OTHER_ISBN" and r[2] == "A" and r[4] == "EXACT"
            and not r[6] and r[-1] != "Y"]
    print(f"\n★芯(MISSING × tierA × EXACT × 疑なし × 除外seed外) {len(core)}件 / 頁{len({r[7] for r in core})}:",
          dict(collections.Counter(r[1] for r in core)))
    by_slug = collections.defaultdict(list)
    for r in core:
        if r[1] == "SPLIT":
            by_slug[r[7]].append(r)
    print(f"  SPLIT(別sidに眠る=Sugar&Spice型) {len(by_slug)}頁:")
    for slug, rs in sorted(by_slug.items()):
        nums = sorted({int(r[16]) for r in rs})
        s2ts = sorted({r[22] for r in rs})
        print(f"    {slug} max={rs[0][10]} 欠={nums} 種2題={s2ts}")
    print("★候補一覧であって自動適用しない。tier B は同名別作品、OTHER_ISBN は別版/特装が多い。")

    # ── 第2部: edition-overrides 固定頁の続巻取りこぼし(楽天非依存・種2駆動) ──────────
    # ★override は巻リストを固定するので、連載中の頁は続巻が種2に来ても永久に出ない
    #   (canonical 側は _check-edition-canonical.py 検査7 が見るが、overrides 側に番人が無かった。
    #    2026-09-03 フェルマーの料理8巻(2026-06)/聖女に嘘は通じない6巻/壁抜けバグ12巻(2026-07)で実踏)
    ovr_p = os.path.join(ROOT, "data", "seeds", "edition-overrides.json")
    if os.path.exists(ovr_p):
        try:
            ovr = json.load(io.open(ovr_p, encoding="utf-8"))
        except Exception:
            ovr = {}
        keep = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban", "deluxe"}
        by_sid = collections.defaultdict(list)
        for isbn, (sid, num, extra, etype, rd) in s2.items():
            by_sid[sid].append((isbn, num, extra, etype, rd))
        # 巻ラベルが抜粋本/アニメ物(うちの3姉妹「傑作選 17」型)は promote が落とすのが正 = 対象外
        _drop_label = {}
        for isbn, lab in con.execute("SELECT isbn13, volume_label FROM volumes WHERE volume_label IS NOT NULL"):
            if lab and re.search(r"傑作選|傑作集|総集編|選集|アニメ|ガイド|ファンブック", str(lab)):
                _drop_label[str(isbn).replace("-", "")] = lab
        ohits = []
        for slug in (ovr.keys() if isinstance(ovr, dict) else []):
            m = meta.get(slug)
            if not m:
                continue
            pmax = m["max"] or 0
            for sid in page_sids.get(slug, ()):
                for isbn, num, extra, etype, rd in by_sid.get(sid, ()):
                    if isbn in idx or etype not in keep or not num or extra or isbn in _drop_label:
                        continue
                    if num > pmax:
                        ohits.append((slug, m["title"], pmax, num, isbn, rd or "", s2title.get(sid, "")))
        ohits.sort()
        out2 = os.path.join(os.path.dirname(OUT), "overrides-frozen-tail.tsv")
        with io.open(out2, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("slug\t頁題\t頁最大巻\t種2巻\tisbn\t種2発売日\t種2題\n")
            for h in ohits:
                fh.write("\t".join(str(x) for x in h) + "\n")
        print(f"\n★第2部 edition-overrides固定頁の続巻取りこぼし: {len(ohits)}巻 / {len({h[0] for h in ohits})}頁"
              f" → {os.path.relpath(out2, ROOT)}")
        for h in ohits[:12]:
            print(f"    {h[0]} max={h[2]} → 種2に{h[3]}巻 {h[4]} {h[5]}")
        if len(ohits) > 12:
            print(f"    … 他{len(ohits) - 12}巻")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
