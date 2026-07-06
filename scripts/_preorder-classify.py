#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約ハーベストの分類 (= 2026-07-06 ユーザ設計の3分類+例外)

入力: .cache/preorders/preorders-latest.jsonl
分類:
  skip     既にページに載っているISBN
  ①zokkan  続巻: 題base+著者が既存ページと一致 → 種4自動追加の対象
  ②new1a   新作1巻・作者は索引に既存 → previewページ生成対象
  ③new1b   新作1巻・作者も新規 → previewページ生成対象(著者ヨミも楽天から)
  ex_mid   例外: 巻番号2以上なのにページ無し(取りこぼし) → 全巻回収フロー対象
出力: .cache/preorders/classified.json + docs/production-diagnostics/preorder-triage.tsv
"""
import json, os, re, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」]", "", t).lower()


# ★scope外ゲート(2026-07-06 ユーザ指摘=特装版/アンソロ/N巻誤1巻化): これらは新作1巻(new1a/b)にしない
import re as _re
SCOPE_BAN = _re.compile(r"特装版|限定版|初回限定|豪華版|特別版|特典付|小冊子付|ドラマCD|CD付き?|DVD付|Blu-?ray|OAD|アンソロジ|総集編|選集|傑作|名作選|セレクション|新装版|愛蔵版|完全版|画集|イラスト集|ファンブック|設定資料|ガイドブック|公式ガイド|データブック|ビジュアルブック|原画|ぬりえ|ムック|フィギュア付|BOXセット|ボックス|スターターセット|スペシャルプライス|第?\s*[2-9２-９][0-9０-９]*\s*巻|第[二三四五六七八九十]+[集部]|(?:II|Ⅱ|III|Ⅲ|IV|Ⅳ|V|Ⅴ|VI|Ⅵ|VII|Ⅶ)\s*$|シーズン\s*[2-9]|[2-9]nd\s|3rd\s|第\d+号|別冊|【楽天ブックス限定特典】", _re.I)

VOLP = re.compile(r"[（(]\s*(\d{1,3})\s*[)）]\s*$|\s+(\d{1,3})\s*$|第\s*(\d{1,3})\s*巻\s*$")

from _preorder_title_lib import split_title as _split_title

def split_vol(title):
    """★分離器(2026-07-06): base正規化題と巻数。vol_suspect(直結数字)は巻2+扱いで安全側。"""
    r = _split_title(title)
    vol = r["vol"]
    if vol is None and r.get("vol_suspect") and r["vol_suspect"] >= 2:
        vol = r["vol_suspect"]  # ★安全側=巻扱い。真偽は同base他巻の存在(題名調査)で上流が判断可能
    if vol is None and r["part"] in ("中", "下"):
        vol = 2
    import unicodedata as _u, re as _re
    b = _u.normalize("NFKC", r["base"])
    b = _re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」]", "", b).lower()
    return b, vol

# 既存資産
iidx = json.load(open(f"{ROOT}/.cache/isbn-page-index.json", encoding="utf-8"))
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
f = idx["f"]
si, ti, ai = f.index("slug"), f.index("title"), f.index("authors")
page_by_title = {}
known_authors = set()
for r in idx["d"]:
    page_by_title.setdefault(norm(r[ti]), []).append(r)
    for a in (r[ai] or []):
        known_authors.add(norm(a.get("name")))

def author_names(s):
    return [x for x in re.split(r"[/,、;；]", str(s or "")) if x.strip()]

rows = [json.loads(l) for l in open(f"{ROOT}/.cache/preorders/preorders-latest.jsonl", encoding="utf-8")]
out = {"skip": [], "zokkan": [], "new1a": [], "new1b": [], "ex_mid": []}
for r in rows:
    if r["isbn"] in iidx:
        out["skip"].append(r); continue
    base, vol = split_vol(r["title"])
    r["_base"], r["_vol"] = base, vol
    cands = page_by_title.get(base) or []
    # 著者一致ゲート(題だけの同題別作を弾く)
    r_auth = {norm(a) for a in author_names(r.get("author"))}
    match = None
    for c in cands:
        p_auth = {norm(a.get("name")) for a in (c[ai] or [])}
        if r_auth & p_auth or not r_auth:
            match = c; break
    if match:
        r["_slug"] = match[si]
        out["zokkan"].append(r); continue
    if vol is not None and vol >= 2:
        out["ex_mid"].append(r); continue
    # ★裸数字N>=2末尾=続巻(2026-07-06 VOLSTRIP事故クラス): 題の一部数字(レベル99/U149=直前が英数字)は除く
    _bm = _re.search(r"[^A-Za-z0-9]\s*([2-9]|[1-9][0-9]{1,2})\s*$", str(r.get("title") or ""))  # 3桁対応(鬼平128漏れ 2026-07-06)
    if _bm:
        r["reason"] = f"裸数字末尾{_bm.group(1)}=続巻疑い(新作1巻にしない)"
        out["skip"].append(r); continue
    # ★巻表記が末尾以外に居る続巻の検出(2026-07-06 ユーザ発見=悪役令嬢99その六/アンゴルモア(13)博多編):
    #   題中間の(N) or ヨミ末尾ソノ漢数字/ダイNカン → 新作1巻にしない(skip=人判 or 次回title照合)
    _t_mid = _re.search(r"[（(]\s*([2-9]|[1-9][0-9])\s*[)）]", str(r.get("title") or ""))
    _k_end = _re.search(r"(ソノ(?:ニ|サン|ヨン|ゴ|ロク|ナナ|ハチ|キュウ|ジュウ)|ダイ[ニサンヨンゴロクナナハチキュウジュウ]+カン)\s*$", str(r.get("titleKana") or ""))
    if _t_mid or _k_end:
        r["reason"] = "巻表記が中間/ヨミのみ(続巻疑い=新作1巻にしない)"
        out["skip"].append(r); continue
    # ★コンビニ本レーベル(2026-07-06 ユーザ指摘): seriesName/レーベルで判定(題では分からない)
    _imp = str(r.get("seriesName") or "") + " " + str(r.get("label") or "")
    if _re.search(r"集英社リミックス|講談社プラチナコミックス|my\s*first\s*big|マイファーストビッグ|コンビニ|廉価|ジャンプ\s*リミックス|アンコール刊行|トップコミックスW|SPコミックスLEAD|(?:^|\s)Gコミックス", _imp, _re.I):
        r["reason"] = "コンビニ本レーベル"
        out["skip"].append(r); continue
    # ★scope外(特装版/アンソロ/セット/ガイド/N巻誤検出)は新作1巻にしない(2026-07-06)
    if SCOPE_BAN.search(str(r.get("title") or "")):
        r["reason"] = "scope外(特装/アンソロ/セット/再編/巻表記)"
        out["skip"].append(r); continue
    # 新作1巻(vol=1 or 単巻)
    if r_auth & known_authors:
        out["new1a"].append(r)
    else:
        out["new1b"].append(r)

json.dump(out, open(f"{ROOT}/.cache/preorders/classified.json", "w", encoding="utf-8"), ensure_ascii=False)
with open(f"{ROOT}/docs/production-diagnostics/preorder-triage.tsv", "w", encoding="utf-8") as fo:
    fo.write("class\tisbn\tym\ttitle\tauthor\tpublisher\tslug\n")
    for k, lst in out.items():
        for r in lst:
            if k == "skip":
                continue
            fo.write(f"{k}\t{r['isbn']}\t{r.get('ym')}\t{str(r['title'])[:40]}\t{str(r.get('author'))[:24]}\t{str(r.get('publisher'))[:16]}\t{r.get('_slug','')}\n")
print("分類:", {k: len(v) for k, v in out.items()})
print("→ .cache/preorders/classified.json + docs/production-diagnostics/preorder-triage.tsv")
