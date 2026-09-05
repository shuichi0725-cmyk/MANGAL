# -*- coding: utf-8 -*-
"""slug/ヨミ系の診断簿を掃除する(2026-09-05 新設)。

背景: 下の3本は**追記専用で一度も掃除されていない**ため膨らみ続け、
      「簿に出ているのに誰も読まない」状態になっていた(skill daily-distill 自身が
      警告している形骸化の型)。実測 2026-09-05: 677行のうち **約94%が残骸**で、
      本当に裁定が要るのは数十行だった。

掃除する簿と規則:
  docs/production-diagnostics/kana-mismatch.tsv        (slug,isbn,title,rakuten_kana,ndl_kana)
  docs/production-diagnostics/slug-gate-pending.tsv    (slug,title,kana)
  docs/production-diagnostics/slug-katakana-pending.tsv(katakana,title,slug)

共通: 重複除去 / ★**そのslugが本番索引に無い行**を除去(改名済み・drop済みの残骸)
個別:
  kana-mismatch        : 頁ヨミとNDLヨミが今は一致 / NDL側にだけ巻数読みが付く /
                         どちらかがもう一方の接頭辞(=副題の有無差) → 既知の偽陽性なので除去。
                         ★比較は助詞ゆらぎ(ハ=ワ / ヲ=オ / ヘ=エ)を潰してから行う
                         (NDLは表音表記なので「実は」が ジツワ になる)。
  slug-gate-pending    : ★**今のゲートを通る行**を除去(辞書追加や装置修正で解決済み)。
  slug-katakana-pending: 語が katakana-english.yml に入った行を除去。

★実修正が要る行は**残す**。消すのは「もう存在しない」「既知の偽陽性」「解決済み」だけ。
"""
import argparse
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

from _preorder_draft_lib import slug_kana_gate            # noqa: E402
from _slug_kana_lib import DIC                            # noqa: E402

D = os.path.join(ROOT, "docs", "production-diagnostics")
LF = chr(10)
VOLREAD = re.compile(r"^(イチ|ニ|サン|ヨン|ゴ|ロク|ナナ|ハチ|キュウ|ジュウ|ゼロ|ジョウ|ゲ|チュウ)+$")


def kata(s):
    """カタカナだけ取り出し、助詞ゆらぎを潰す(NDLは表音表記=「実は」がジツワになる)。"""
    t = re.sub(r"[^ァ-ヶー]", "", str(s or ""))
    return t.replace("ワ", "ハ").replace("オ", "ヲ").replace("エ", "ヘ")


def load_pub():
    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {n: i for i, n in enumerate(idx["f"])}
    return {r[F["slug"]]: r[F["title_kana"]] for r in idx["d"]}


def prune(path, slug_col, keep_fn, pub):
    if not os.path.exists(path):
        return None
    raw = io.open(path, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in raw else LF
    lines = raw.replace(eol, LF).split(LF)
    head = [l for l in lines[:1] if l.startswith("slug\t")]      # ヘッダ行が在る簿だけ温存
    body = [l for l in lines[len(head):] if l.strip()]
    seen, kept, drop = set(), [], {"dup": 0, "gone": 0, "resolved": 0}
    for l in body:
        if l in seen:
            drop["dup"] += 1
            continue
        seen.add(l)
        c = l.split("\t")
        s = c[slug_col] if len(c) > slug_col else ""
        if s not in pub:
            drop["gone"] += 1
            continue
        if not keep_fn(c, pub):
            drop["resolved"] += 1
            continue
        kept.append(l)
    return head, kept, drop, len(body), eol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    pub = load_pub()

    def keep_mismatch(c, pub):
        # c = slug,isbn,title,rakuten_kana,ndl_kana
        if len(c) < 5:
            return True
        page, ndl = kata(pub.get(c[0])), kata(c[4])
        if not page or not ndl:
            return True                       # 頁にヨミが無い=実修正の候補として残す
        if page == ndl:
            return False                      # 解決済み
        if ndl.startswith(page) and VOLREAD.match(ndl[len(page):]):
            return False                      # NDL側にだけ巻数読み=既知の偽陽性
        if page.startswith(ndl) or ndl.startswith(page):
            return False                      # 副題の有無差=既知の偽陽性
        return True

    def keep_gate(c, pub):
        # c = slug,title,kana
        if len(c) < 3:
            return True
        try:
            return not slug_kana_gate(c[1], c[2], c[0], out_tsv=os.devnull)
        except Exception:
            return True

    def keep_kata(c, pub):
        # c = katakana,title,slug
        return not (len(c) >= 1 and c[0] in DIC)

    jobs = [("kana-mismatch.tsv", 0, keep_mismatch),
            ("slug-gate-pending.tsv", 0, keep_gate),
            ("slug-katakana-pending.tsv", 2, keep_kata)]
    for name, col, fn in jobs:
        p = os.path.join(D, name)
        r = prune(p, col, fn, pub)
        if r is None:
            print("  (無し) " + name)
            continue
        head, kept, drop, before, eol = r
        print("  %-30s %4d → %3d 行  (重複%d / 本番に無い%d / 解決済・偽陽性%d)"
              % (name, before, len(kept), drop["dup"], drop["gone"], drop["resolved"]))
        if a.apply:
            io.open(p, "w", encoding="utf-8", newline="").write(
                LF.join(head + kept).replace(LF, eol) + eol)
    if not a.apply:
        print(LF + "(dry-run。適用は --apply)")


if __name__ == "__main__":
    main()
