#!/usr/bin/env python3
"""画集 step6 通し検証 (= 機械検査)。 read-only。

前提: 画集161は実データ(本番data/art-books/)。 漫画は本checkoutでは42サンプル
(data/manga/)なので「この作家の画集」は logic + サンプル範囲の確認。
"""
import glob
import re
import sys
from pathlib import Path

import yaml

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
ART_DIR = ROOT / "data" / "art-books"
MANGA_DIR = ROOT / "data" / "manga"
EXCLUDE_YML = ROOT / "data" / "seeds" / "art-book-exclude-isbn.yml"
REGISTRY = ROOT / "data" / "seeds" / "art-books.yml"


def norm_isbn(s):
    return re.sub(r"[^0-9]", "", str(s or ""))


def load_dir(d):
    out = []
    for f in sorted(glob.glob(str(d / "*.yml"))):
        out.append((Path(f).name, yaml.safe_load(open(f, encoding="utf-8"))))
    return out


def main():
    arts = load_dir(ART_DIR)
    mangas = load_dir(MANGA_DIR)
    fails = []
    warns = []

    def check(cond, ok, ng, warn=False):
        (warns if warn else fails).append(ng) if not cond else None
        print(f"  {'✅' if cond else ('⚠️ ' if warn else '❌')} {ok if cond else ng}")

    print("=== 1. 構造的混在ゼロ ===")
    excl = {norm_isbn(e["isbn13"]) for e in (yaml.safe_load(EXCLUDE_YML.read_text(encoding='utf-8')) or {}).get("exclude_isbn", [])}
    # 漫画(本番)の巻ISBNに画集混在ISBNが残っていないか
    leak = []
    for name, m in mangas:
        for ed in (m.get("editions") or []):
            for v in (ed.get("volumes") or []):
                if norm_isbn(v.get("isbn13")) in excl:
                    leak.append(f"{name}:{v.get('isbn13')}")
    check(not leak, "漫画本番に画集混在ISBN 0件", f"漫画に画集ISBN残存: {leak}")
    # slug衝突
    art_slugs = [a.get("slug") for _, a in arts]
    manga_slugs = {m.get("slug") for _, m in mangas}
    inter = set(art_slugs) & manga_slugs
    check(not inter, "漫画slugと画集slug 衝突0", f"slug衝突: {inter}")

    print("=== 2. adult除外 ===")
    adult = [a.get("title") for _, a in arts if a.get("adult")]
    check(not adult, "本番画集にadult:true 0件", f"adult混入: {adult}")

    print("=== 3. データ整合 ===")
    check(len(art_slugs) == len(set(art_slugs)), f"slug全一意 ({len(art_slugs)}件)", "slug重複あり")
    no_kana = [a.get("title") for _, a in arts if not (a.get("title_kana") or "").strip()]
    check(not no_kana, "kana全件あり", f"kana空: {no_kana}")
    no_title = [n for n, a in arts if not (a.get("title") or "").strip() or not (a.get("artist") or "").strip()]
    check(not no_title, "title/artist全件あり", f"title/artist空: {no_title}")
    bad_cat = [a.get("title") for _, a in arts if a.get("category") != "画集"]
    check(not bad_cat, "category=画集 全件", f"category異常: {bad_cat}")
    # 外国版ISBN(非9784)
    foreign = []
    for _, a in arts:
        for v in (a.get("volumes") or []):
            ib = norm_isbn(v.get("isbn13"))
            if ib and not ib.startswith("9784"):
                foreign.append(f"{a.get('title')}:{ib}")
    check(not foreign, "外国版ISBN(非9784) 0件", f"外国版ISBN: {foreign}", warn=True)

    print("=== 4. 購入リンク健全性 ===")
    no_buy_anchor = []  # ISBN/ASINが無くタイトル検索fallbackになる画集
    no_vol = []
    for _, a in arts:
        vols = a.get("volumes") or []
        if not vols:
            no_vol.append(a.get("title")); continue
        v0 = vols[0]
        if not (norm_isbn(v0.get("isbn13")) or (v0.get("asin") or "").strip()):
            no_buy_anchor.append(a.get("title"))
    check(not no_vol, "全画集に巻あり(min1)", f"巻ゼロ: {no_vol}")
    check(not no_buy_anchor, "全画集の購入リンクがISBN/ASIN直", f"ISBN/ASIN無→題検索fallback: {len(no_buy_anchor)}件", warn=True)

    print("=== 5. この作家の画集 紐付け(サンプル範囲) ===")
    art_artists = {}
    for _, a in arts:
        art_artists.setdefault(a.get("artist"), []).append(a.get("title"))
    match_cnt = 0
    orig_only_link = []  # 原作者一致だが作画者でない=出てはいけない
    for name, m in mangas:
        anames = {x["name"] for x in (m.get("authors") or [])}
        onames = {x["name"] for x in (m.get("original_authors") or [])}
        hit = anames & set(art_artists)
        if hit:
            match_cnt += 1
        # 原作者のみ一致(作画者でない)で画集作家に居る→誤って出る危険の検出
        for oa in (onames - anames):
            if oa in art_artists:
                orig_only_link.append(f"{m.get('title')} 原作者={oa}")
    print(f"  ℹ️ サンプル漫画で枠が出る作品: {match_cnt}件 (作画者一致)")
    check(not orig_only_link, "原作者のみ一致での紐付け 0(原作者には出さない)",
          f"原作者一致が画集作家に存在(要確認): {orig_only_link}", warn=True)

    print()
    print(f"=== 結果: 失敗 {len(fails)} / 警告 {len(warns)} ===")
    if fails:
        print("❌ FAIL:")
        for f in fails:
            print(f"   - {f}")
    if warns:
        print("⚠️  WARN(要確認・致命でない):")
        for w in warns:
            print(f"   - {w}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
