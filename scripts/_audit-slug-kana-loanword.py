# -*- coding: utf-8 -*-
"""カタカナ外来語がヘボン転写のまま公開されている slug を検出する(2026-09-05 新設)。

★きっかけ: ユーザ指摘「猫と紳士のティールーム = ティールームがヘボン」
  公開slug `neko-to-shinshi-no-teiiruumu` / 現行の slug 装置は `neko-to-shinshi-no-tea-room` を出す。
  = **装置(2026-07-06)より前に作られた古い世代の slug** が残っている。

CLAUDE.md slug規則4: カタカナ外来語は元の外国語綴り(明白な辞書英単語のみ)。
辞書 = data/seeds/katakana-english.yml の mappings。

★2層を見る:
  層1 DEAD_OVERRIDE = slug-overrides.yml に**平坦形(トップレベル `old: new`)**で書かれた是正。
       promote の `_slug_override` は `doc["overrides"]` 配下の **入れ子dict(slugキー付き)しか読まない**ので、
       平坦形は**永久に効かない死にエントリ**。書いた人は直したつもりでいる = 最も危険。
       ([[katakana_dict_dead_entry_trap]] と同じ型が slug 側にも在った)
  層2 DEVICE_DIFF  = 台帳に何も書かれていないが、現行装置なら英語綴りを出す頁。

出力: docs/production-diagnostics/slug-kana-loanword.tsv
  layer / pub_slug(現公開) / suggest(装置or台帳の案) / title / hit(根拠のカタカナ語→英語) / note

★自動適用はしない。公開URLの改名は user 裁定 + 旧slugの301 が要る(CLAUDE.md「slug rename は必ず user 確認」)。
"""
import io
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

from _slug_kana_lib import make_slug as dev, kana2romaji, DIC, KEYS   # noqa: E402

TITLE_OF = {}
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "slug-kana-loanword.tsv")


def tokens(slug):
    return set(str(slug or "").split("-"))


def run_fully_covered(title, k):
    """★語 k を含む**カタカナ連**が、辞書語だけで丸ごと覆えるか(2026-09-05)。
    覆えない = 辞書が長い外来語の頭だけを食っている(ディアナ->ディア+ナ / マリーン->マリー+ン /
    メトロノーム->メトロ+ノーム)。この形で英語に差し替えると別語になるので CLEAR にしない。
    """
    t = str(title or "")
    runs = re.findall(r"[\u30a1-\u30f6\u30fc]+", t)
    runs = [r for r in runs if k in r]
    if not runs:
        return False
    for run in runs:
        i = 0
        while i < len(run):
            for key in KEYS:                 # KEYS は長い順=最長一致
                if key and run.startswith(key, i):
                    i += len(key)
                    break
            else:
                return False                 # 辞書で覆えない断片が残る
    return True

def tier_of(pub, cand, hits):
    """★明白な層(CLEAR)の判定(2026-09-05)。
    装置案の**英語だけをカナのローマ字へ逆置換**して現公開slugに戻れば、2つの差は
    「外来語の綴り」だけ = 機械適用してよい。戻らなければ語境界の解釈が変わっている
    (choujin-locke->choujin-rock / short-arabesque->show-to-arabesuku 型)ので人が裁く。

    2通り認める:
      (a) トークン単位: 公開slugのトークンが丸ごと辞書語のローマ字で、そこだけ英語に化ける
          (mimoza-kan-de-tsukamaete -> mimosa-kan-de-tsukamaete)
      (b) 全体一致: 逆置換した文字列がハイフンを除いて公開slugと完全一致
          (rosutowaarudo -> lost-world / shoufumarii -> shoufu-mary)
    """
    if not all(run_fully_covered(TITLE_OF.get(pub, ""), k) for k in hits):
        return "REVIEW"                  # ★長い外来語の頭だけを食っている
    ptok = str(pub).split("-")
    ctok = str(cand).split("-")
    if len(ptok) == len(ctok):
        diff = [(p, c) for p, c in zip(ptok, ctok) if p != c]
        if diff and all(any(DIC.get(k) == c and kana2romaji(k) == p for k in hits)
                        for p, c in diff):
            return "CLEAR"
    back = cand
    for k in sorted(hits, key=lambda x: -len(DIC.get(x, "") or "")):
        e = DIC.get(k)
        if e:
            back = back.replace(e, kana2romaji(k))
    # ★日本語側の区切りを変える案は CLEAR にしない(himitsu-de-naito -> hi-mitsude-night 型)。
    #   公開slugにハイフンが在るならハイフン込みで一致を要求する。1トークンなら保存しようが
    #   無いのでハイフンを除いて比べる。
    if "-" in str(pub):
        return "CLEAR" if back == str(pub) else "REVIEW"
    if back.replace("-", "") == str(pub):
        return "CLEAR"
    return "REVIEW"


def main():
    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {n: i for i, n in enumerate(idx["f"])}
    rows = idx["d"]
    pub2title = {r[F["slug"]]: r[F["title"]] for r in rows}
    TITLE_OF.update(pub2title)
    published = set(pub2title)

    # ---- 層1: slug-overrides.yml の平坦形(死にエントリ) ----
    sop = os.path.join(ROOT, "data", "seeds", "slug-overrides.yml")
    flat = {}
    live_keys = set()
    if os.path.exists(sop):
        doc = yaml.safe_load(io.open(sop, encoding="utf-8")) or {}
        for k, v in doc.items():
            if k == "overrides":
                for ok, ov in (v or {}).items():
                    if isinstance(ov, dict) and ov.get("slug"):
                        live_keys.add(ok)          # ちゃんと効く形
                    else:
                        flat[ok] = ov if isinstance(ov, str) else None   # 入れ子だがstr=これも死ぬ
            elif isinstance(v, str):
                flat[k] = v                        # トップレベル平坦形=死ぬ

    ENG = {str(v) for v in DIC.values() if v and "-" not in str(v)}   # 辞書の英語側(トークン照合用)
    out = []
    for old, new in sorted(flat.items()):
        if not new:
            continue
        if old in published:                       # 旧slugがまだ公開中=是正が効いていない
            out.append(("DEAD_OVERRIDE", old, new, pub2title.get(old, ""), "", "台帳に是正が書かれているが平坦形のため promote が読まない"))

    # ---- 層2: 装置なら英語綴りを出す頁(台帳に無いもの) ----
    known = {o for _, o, _, _, _, _ in out}
    for r in rows:
        pub, title = r[F["slug"]], r[F["title"]]
        if pub in known or pub in live_keys:
            continue
        # 題に辞書見出し語(3字以上)が在り、その英語が slug に無い、という粗ふるい(装置を回す前に絞る)
        hits = [k for k in KEYS if len(k) >= 3 and k in str(title or "")]
        hits = [k for k in hits if DIC[k] not in tokens(pub) and DIC[k] not in str(pub)]
        if not hits:
            continue
        try:
            cand = dev(title)
        except Exception:
            continue
        cand = re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]+", "-", str(cand).lower())).strip("-")
        if not cand or cand == pub:
            continue
        # 装置案に英語綴りが入っていて、現公開slugに入っていない語だけを根拠にする
        ev = [f"{k}->{DIC[k]}" for k in hits if DIC[k] in tokens(cand)]
        if not ev:
            continue
        # ★現公開slugが**既に英語化されている**なら触らない(2026-09-05 精度是正)。
        #   装置は語境界を取り違えて「現状より悪い案」を出すことがある:
        #     hit-and-run -> hitto-end-ran / yasashisa-endless -> yasashisa-en-dress /
        #     high-teen-boogie -> high-tea-n-bugi / choujin-locke -> choujin-rock
        #   公開slugのトークンに辞書の**英語側**が1つでも入っていれば「もう英語綴り」とみなして除外する。
        if tokens(pub) & ENG:
            continue
        # ★装置案の方がカナ転写を増やす(英語トークンが減る)なら劣化=除外
        if len(tokens(cand) & ENG) <= len(tokens(pub) & ENG):
            continue
        note = "装置案が既存slugと衝突" if cand in published else ""
        _t = "REVIEW" if note else tier_of(pub, cand, hits)
        out.append(("DEVICE_DIFF_" + _t, pub, cand, title, ",".join(ev[:4]), note))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("layer\tpub_slug\tsuggest\ttitle\thit\tnote\n")
        for row in out:
            f.write("\t".join(str(x) for x in row) + "\n")

    from collections import Counter
    c = Counter(x[0] for x in out)
    print(f"公開 {len(published)}頁 / 検出 {len(out)}件  {dict(c)}")
    print(f"  うち装置案が既存slugと衝突: {sum(1 for x in out if x[5])}件(=そのままrename不可)")
    print(f"出力: {OUT}")
    print("★自動適用はしない。改名は user 裁定 + 旧slugの301 + 既存リダイレクトの張り替えがセット。")


if __name__ == "__main__":
    main()
