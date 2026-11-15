# -*- coding: utf-8 -*-
"""Wikipedia の情報欄(題・巻数)とサイトを突き合わせ、出ていない物を探す (2026-11-15 新設)。

きっかけ = 「9番目のムサシ」: Wikipedia の情報欄に シリーズ5本の題と巻数が並んでいて、
  ・レッドスクランブル(全12巻) = 頁が無い
  ・サイレントブラック(全15巻) = 頁は9巻まで
  ・本編(全21巻)             = 頁は23巻(続編の巻が混入)
が一目で分かった。 同じ照合を手元ダンプの漫画記事 全件に掛ける。

  python scripts/_audit-wiki-volume-gap.py            # 表を書く + 件数
  python scripts/_audit-wiki-volume-gap.py --title 9番目のムサシ   # 1記事だけ画面に出す(確認用)

入力(すべて手元・外部へは出ない・モデル不使用):
  .cache/jawiki-dump/manga-articles.jsonl   漫画の情報欄を持つ記事(_wiki_local.py が作る)
  data/manga-list-index.json                サイトの頁(題・著者・巻数)
  data/manga-alt-index.json                 別名
  .cache/isbn-title-map.json                楽天の題(ISBN→題)        ★無ければその証拠列は空
  .cache/isbn-page-index.json               ISBN→頁(★古いと「未掲載」が水増しになる = 先に _exists.py --build)
  .cache/db-v2.sqlite                       種2(題の有無だけ)
出力: docs/production-diagnostics/wiki-volume-gap.tsv

型:
  NOPAGE  Wikipedia に題と巻数が在るのに、サイトに頁が無い
  SHORT   頁は在るが、いちばん巻の多い版でも Wikipedia の巻数に届かない
  OVER    完結作なのに、頁の巻数が Wikipedia のどの巻数よりも多い(他作の巻の混入を疑う)
確度(rank):
  A = 楽天の題が一致する本が「どの頁にも載っていない」状態で手元に在る(= 足す本が特定できる)
  B = 同じ著者の頁に、題が包含関係の頁が在る(= 表記ゆれ/親頁に合流済みの見込み。 楽天の未掲載本は在る)
  C = 証拠は巻数の差だけ(NOPAGE の C = 楽天の題でも本が見つからない = 題の表記ゆれの見込みが高い)
  X = 題からみて掲載対象外の見込み(アンソロジー・小説など)
  ※NOPAGE の A は「未掲載の本が Wikipedia の巻数の半分以上・同じ著者の近い頁なし」まで絞ったもの
★この表は「候補」。 自動で足さない・消さない(Wikipedia の巻数は版の取り方が記事ごとに違う)。
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTS = os.path.join(ROOT, ".cache", "jawiki-dump", "manga-articles.jsonl")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "wiki-volume-gap.tsv")

# ---------- 正規化 ----------
_VAR = str.maketrans({"髙": "高", "﨑": "崎", "濵": "浜", "濱": "浜", "邊": "辺", "邉": "辺", "齋": "斎", "齊": "斉",
                      "澤": "沢", "廣": "広", "嶋": "島", "德": "徳", "惠": "恵", "眞": "真", "龍": "竜", "ヶ": "ケ",
                      "〜": "", "～": "", "―": "ー", "‐": "", "−": "", "–": "", "—": "ー"})


def norm(s):
    """題・人名の照合キー。 空白と記号を全部落とす(中黒・感嘆符・括弧の揺れを吸収)。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower().translate(_VAR)
    return "".join(ch for ch in s if unicodedata.category(ch)[0] in ("L", "N") or ch == "ー")


# ---------- wikitext ----------
_REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BR = re.compile(r"<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")
_LINK = re.compile(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]\]")
_RUBY = re.compile(r"\{\{\s*(?:ruby|読み仮名|読み仮名_ruby不使用)\s*\|([^|{}]*)\|[^{}]*\}\}", re.I)
_TMPL = re.compile(r"\{\{[^{}]*\}\}")


def clean(v):
    v = _COMMENT.sub("", _REF.sub("", v or ""))
    v = _BR.sub(" / ", v)
    v = _RUBY.sub(r"\1", v)
    for _ in range(3):
        v = _TMPL.sub("", v)
    v = _LINK.sub(r"\1", v)
    v = _TAG.sub("", v).replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", v).strip()


def templates(text, head):
    """text から `{{head …}}` を全部(入れ子を数えて)切り出す。"""
    out, low, i = [], text.lower(), 0
    h = "{{" + head.lower()
    while True:
        i = low.find(h, i)
        if i < 0:
            return out
        depth, j = 0, i
        while j < len(text) - 1:
            two = text[j:j + 2]
            if two == "{{":
                depth += 1; j += 2
            elif two == "}}":
                depth -= 1; j += 2
                if depth == 0:
                    break
            else:
                j += 1
        out.append(text[i + 2:j - 2])
        i = j


def params(body):
    """テンプレート本文 → {名前: 値}。 入れ子の {{ }} [[ ]] の中の | では切らない。"""
    parts, buf, d1, d2, k = [], [], 0, 0, 0
    while k < len(body):
        two = body[k:k + 2]
        if two == "{{":
            d1 += 1; buf.append(two); k += 2; continue
        if two == "}}":
            d1 -= 1; buf.append(two); k += 2; continue
        if two == "[[":
            d2 += 1; buf.append(two); k += 2; continue
        if two == "]]":
            d2 -= 1; buf.append(two); k += 2; continue
        ch = body[k]
        if ch == "|" and d1 <= 0 and d2 <= 0:
            parts.append("".join(buf)); buf = []
        else:
            buf.append(ch)
        k += 1
    parts.append("".join(buf))
    out = {}
    for p in parts[1:]:
        if "=" in p:
            a, b = p.split("=", 1)
            out[a.strip()] = b.strip()
    return out


_VOL = re.compile(r"(全|既刊|計)?\s*(\d{1,3})\s*巻")


def vol_numbers(raw):
    """巻数欄 → [(n, 完結か, その数字の手前の文言)]。 先頭が主(たいてい最初の単行本)。"""
    out, last = [], 0
    for m in _VOL.finditer(raw):
        label = raw[last:m.start()].strip(" /、,:：()（）・")
        tail = raw[m.end():m.end() + 8]
        if re.match(r"\s*(まで|から|収録|に収録|以降|発売時)", tail):   # 「3巻まで」「5巻収録」は巻数ではない
            last = m.end(); continue
        out.append((int(m.group(2)), m.group(1) == "全", label[-24:]))
        last = m.end()
    return out


_NAME_SPLIT = re.compile(r"\s*/\s*|、|,|，|→")
_PAREN = re.compile(r"[（(][^（）()]*[）)]")


def names(v):
    out = []
    for x in _NAME_SPLIT.split(_PAREN.sub("", clean(v))):
        x = re.sub(r"^(原作|作画|漫画|原案|作|画|キャラクター原案|脚本|構成|監修)\s*[:：・]?\s*", "", x.strip())
        if x and len(x) <= 20:
            out.append(x)
    return out


_DISAMBIG = re.compile(r"\s*[（(][^（）()]*[）)]\s*$")
_VOLTAIL = re.compile(
    r"(?:\s*[（(【\[]?\s*(?:第\s*)?(?:\d{1,3}|[上中下前後]|[IVX]{1,4})\s*(?:巻|集|冊)?\s*[）)】\]]?)\s*$")


def stem(title):
    """楽天の題 → 巻番号を落とした幹(「…レッドスクランブル（1）」→「…レッドスクランブル」)。"""
    t = unicodedata.normalize("NFKC", title or "").strip()
    for _ in range(2):
        t2 = _VOLTAIL.sub("", t).strip()
        if t2 == t or len(t2) < 2:
            break
        t = t2
    return t


OUT_OF_SCOPE = re.compile(r"アンソロジー|ガイドブック|ファンブック|公式ブック|設定資料|画集|イラスト集|小説|ノベライズ|ノベル|"
                          r"フィルムコミック|アニメコミック|傑作選|総集編|ベストセレクション")


def load_boxes(only=None):
    """記事ごとに [(記事名, 題, 著者名[], 出版社, レーベル, 巻数欄の原文, その他欄, 主箱か)]。"""
    with open(ARTS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            art = d["title"]
            if only and art != only:
                continue
            text = d.get("text") or ""
            heads = templates(text, "Infobox animanga/Header")
            htitle = clean(params(heads[0]).get("タイトル", "")) if heads else ""
            htitle = htitle.split(" / ")[0].strip() or _DISAMBIG.sub("", art)
            seen = set()
            for bi, body in enumerate(templates(text, "Infobox animanga/Manga")):
                p = params(body)
                t = clean(p.get("タイトル", "")).split(" / ")[0].strip() or htitle
                raw = clean(p.get("巻数", ""))
                if not raw or norm(t) in seen:
                    continue
                seen.add(norm(t))
                au = []
                for k in ("作者", "原作", "作画", "原案", "原作・原案など"):
                    au += names(p.get(k, ""))
                yield (art, t, au, clean(p.get("出版社", "")), clean(p.get("レーベル", "")),
                       raw, clean(p.get("その他", "")), not p.get("タイトル"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", help="この記事だけ画面に出す(確認用。表は書かない)")
    a = ap.parse_args()

    # --- サイト ---
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {k: i for i, k in enumerate(idx["f"])}
    rows = idx["d"]
    by_title, by_author = defaultdict(list), defaultdict(list)
    for r in rows:
        keys = {norm(r[F["title"]])}
        if r[F["subtitle"]]:
            keys.add(norm(f'{r[F["title"]]}{r[F["subtitle"]]}'))
        for k in keys:
            if k:
                by_title[k].append(r)
        for au in (r[F["authors"]] or []) + (r[F["original_authors"]] or []):
            by_author[norm(au.split("\t")[0])].append(r)
    slug_row = {r[0]: r for r in rows}
    try:
        for slug, alts in json.load(open(os.path.join(ROOT, "data", "manga-alt-index.json"), encoding="utf-8")).items():
            for alt in alts or []:
                k = norm(alt)
                if k and slug in slug_row and slug_row[slug] not in by_title[k]:
                    by_title[k].append(slug_row[slug])
    except Exception:
        pass

    # --- 楽天の題(巻番号を落とした幹 → ISBN) と ISBN→頁 ---
    stems, on_page = defaultdict(set), {}
    try:
        on_page = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
        for isbn, t in json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8")).items():
            if isinstance(t, str):
                stems[norm(stem(t))].add(isbn)
    except Exception as e:
        print(f"(楽天の題/ISBN索引が読めない = その証拠列は空: {e})")

    stem_keys = sorted(stems)

    def stem_isbns(key):
        """題キー → (ISBN集合, 前方一致で拾ったか)。 完全一致が無く題が5字以上なら、楽天の題が「この題で始まる」本を拾う
        (楽天の題に副題が付く作品: 「しょせん他人事ですから ～とある弁護士の…～」)。"""
        if key in stems:
            return stems[key], False
        if len(key) < 5:
            return set(), False
        import bisect
        got, i = set(), bisect.bisect_left(stem_keys, key)
        while i < len(stem_keys) and stem_keys[i].startswith(key) and len(got) < 400:
            got |= stems[stem_keys[i]]; i += 1
        return got, bool(got)

    # --- 種2 の題 ---
    seed2 = defaultdict(int)
    try:
        con = sqlite3.connect(f"file:{os.path.join(ROOT, '.cache', 'db-v2.sqlite')}?mode=ro", uri=True)
        for (t,) in con.execute("select title from series"):
            seed2[norm(t)] += 1
    except Exception as e:
        print(f"(種2が読めない = その列は空: {e})")

    # --- 非掲載の裁定済み(題が載っていれば印だけ付ける) ---
    try:
        dropped = norm(open(os.path.join(ROOT, "data", "seeds", "non-manga-drop.yml"), encoding="utf-8").read())
    except Exception:
        dropped = ""

    def author_ok(wiki_au, r):
        site = {norm(x.split("\t")[0]) for x in (r[F["authors"]] or []) + (r[F["original_authors"]] or [])}
        w = {norm(x) for x in wiki_au}
        if not w or not site:
            return None                      # 判定不能
        return bool(w & site) or any(x in y or y in x for x in w for y in site if len(x) >= 2 and len(y) >= 2)

    out, n_box, n_match = [], 0, 0
    for art, t, au, pub, label, raw, other, is_main in load_boxes(a.title):
        nums = vol_numbers(raw)
        if not nums:
            continue
        n_box += 1
        n, complete, _ = nums[0]
        all_n = [x[0] for x in nums] + [x[0] for x in vol_numbers(other)]
        key = norm(t)
        books, loose = stem_isbns(key)
        unl = sorted(i for i in books if not on_page.get(i))
        cands = by_title.get(key, [])
        hit = [r for r in cands if author_ok(au, r) is not False]
        via = ""
        if not hit:
            # ★題が当たらない時は ISBN で頁を突き止める: 楽天の題がこの題と一致する本が、どの頁に載っているか。
            #   (サイトの題が「Silent Black」、Wikipedia が「サイレントブラック」のような表記ゆれを吸収する)
            tally = defaultdict(int)
            for i in books:
                for sl in on_page.get(i) or ():
                    tally[sl] += 1
            best = sorted(tally.items(), key=lambda kv: -kv[1])
            if best and best[0][0] in slug_row and best[0][1] >= max(1, min(n, len(books)) // 2):
                hit, via = [slug_row[best[0][0]]], f"ISBNで特定({best[0][1]}冊がこの頁{'・題は前方一致' if loose else ''})"
        base = {"記事": art, "題": t, "著者": "・".join(au[:3]), "出版社": pub, "レーベル": label,
                "Wiki巻数欄": raw + (f" ｜その他: {other}" if other and vol_numbers(other) else ""),
                "Wiki巻数": n, "完結": "完結" if complete else "既刊",
                "楽天未掲載冊": len(unl), "楽天未掲載ISBN例": ",".join(unl[:3]),
                "種2に題": seed2.get(key, 0)}
        if hit:
            n_match += 1
            r = max(hit, key=lambda x: x[F["max_edition_volumes"]] or 0)
            mx, tot = r[F["max_edition_volumes"]] or 0, r[F["total_volumes"]] or 0
            row = dict(base, slug=r[0], 頁の最多版=mx, 頁の全巻=tot)
            if mx < n:
                row.update(型="SHORT", 差=n - mx, 確度="A" if unl else "C",
                           メモ=" / ".join(x for x in (via, "頁の巻数が Wiki の別の版の巻数と一致" if mx in all_n else "") if x))
                out.append(row)
            elif complete and mx > max(all_n) and not via:      # ISBNで特定した頁は親頁のことが多い = 多い判定に使わない
                row.update(型="OVER", 差=mx - max(all_n), 確度="C",
                           メモ=" / ".join(x for x in (via, "頁は連載中の扱い" if r[F["status"]] != "completed" else "") if x))
                out.append(row)
            continue
        # 頁が無い
        near = []
        for x in au:
            for r in by_author.get(norm(x), []):
                k2 = norm(r[F["title"]])
                if len(k2) >= 3 and (k2 in key or key in k2) and r[0] not in near:
                    near.append(r[0])
        memo = []
        if cands:
            memo.append("同じ題の頁は在るが著者が違う: " + ",".join(r[0] for r in cands[:2]))
        if key and key in dropped:
            memo.append("non-manga-drop に題あり(非掲載の裁定済みか)")
        if not is_main:
            memo.append("記事内の2本目以降(続編/別作)")
        if loose and unl:
            memo.append("楽天の題は前方一致で拾った")
        scope = OUT_OF_SCOPE.search(t)
        if scope:
            memo.append(f"掲載対象外の見込み(題に「{scope.group(0)}」)")
        # A = 未掲載の本が Wiki の巻数の半分以上・近い頁なし / B = 未掲載の本は在るが一部だけ、または近い頁あり / C = 本が見つからない
        strong = len(unl) >= max(1, (n + 1) // 2) and not near and not loose
        out.append(dict(base, 型="NOPAGE", slug="", 頁の最多版="", 頁の全巻="", 差=n,
                        確度="X" if scope else ("A" if strong else "B") if unl else "C",
                        近い頁=",".join(near[:3]), メモ=" / ".join(memo)))

    cols = ["型", "確度", "記事", "題", "著者", "出版社", "レーベル", "Wiki巻数欄", "Wiki巻数", "完結", "slug",
            "頁の最多版", "頁の全巻", "差", "楽天未掲載冊", "楽天未掲載ISBN例", "種2に題", "近い頁", "メモ"]
    order = {"NOPAGE": 0, "SHORT": 1, "OVER": 2}   # 確度 X = 掲載対象外の見込み(末尾に並ぶ)
    out.sort(key=lambda r: (order[r["型"]], r["確度"], r["記事"], r["題"]))
    if a.title:
        for r in out:
            print({k: r.get(k, "") for k in cols if r.get(k, "") != ""})
        print(f"(情報欄 {n_box} / 頁に当たった {n_match} / 候補 {len(out)})")
        return
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(cols) + "\n")
        for r in out:
            f.write("\t".join(str(r.get(k, "")).replace("\t", " ") for k in cols) + "\n")
    cnt = defaultdict(int)
    for r in out:
        cnt[(r["型"], r["確度"])] += 1
    print(f"情報欄(巻数つき) {n_box:,} / 頁に当たった {n_match:,} / 候補 {len(out):,} → {OUT}")
    for k in sorted(cnt):
        print(f"  {k[0]:7} {k[1]}: {cnt[k]:,}")


if __name__ == "__main__":
    main()
